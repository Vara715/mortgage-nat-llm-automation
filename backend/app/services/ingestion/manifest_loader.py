"""
manifest_loader.py
==================
Dataset-agnostic ingestion engine for morgage-loan-automation.
Reads, validates, and executes ingestion for arbitrary datasets according to their manifest.
Supports both document (PDF/TXT) and tabular (CSV/JSON/Parquet) ingestion paths.
Tracks background jobs and preserves cryptographic provenance.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.core.config import settings, BASE_DIR
from backend.app.schemas.dataset import DatasetManifest
from backend.app.models.entities import (
    Dataset,
    DatasetVersion,
    ProcessingJob,
    DocumentChunk,
    RegulatoryDocument,
    RegulatorySource,
    HMDARecord,
    HMDADatasetImport,
    utc_now,
    gen_uuid,
)
from backend.app.connectors import (
    LocalFileConnector,
    URLSourceConnector,
    APISourceConnector,
    CSVSourceConnector,
    JSONSourceConnector,
    JSONLSourceConnector,
    ParquetSourceConnector,
)
from backend.app.services.chunking.section_chunker import SectionChunker
from backend.app.services.extraction.pdf_service import PDFService

logger = logging.getLogger("morgage-loan-automation.ingestion")


class DatasetIngestionEngine:
    """
    Orchestrates dataset-agnostic ingestion according to a validated manifest.
    Maintains provenance, executes tabular vs document paths, and updates jobs.
    """

    def __init__(self, db: Session):
        self.db = db
        self.pdf_service = PDFService()
        self.chunker = SectionChunker()

    def get_connector(self, manifest: DatasetManifest):
        """Instantiate the appropriate connector according to the manifest source_type."""
        st = manifest.source_type.upper()
        sid = manifest.dataset_id
        loc = manifest.source_location

        # Resolve relative file paths to project root
        if not loc.startswith("http") and not Path(loc).is_absolute():
            loc = str(BASE_DIR / loc)

        if st == "LOCAL_FILE":
            return LocalFileConnector(sid, loc, name=manifest.dataset_name, jurisdiction=manifest.jurisdiction)
        elif st == "URL":
            return URLSourceConnector(sid, loc, name=manifest.dataset_name, jurisdiction=manifest.jurisdiction)
        elif st == "API":
            return APISourceConnector(sid, loc, name=manifest.dataset_name, jurisdiction=manifest.jurisdiction)
        elif st == "CSV":
            return CSVSourceConnector(sid, loc, name=manifest.dataset_name, jurisdiction=manifest.jurisdiction)
        elif st == "JSON":
            return JSONSourceConnector(sid, loc, name=manifest.dataset_name, jurisdiction=manifest.jurisdiction)
        elif st == "JSONL":
            return JSONLSourceConnector(sid, loc, name=manifest.dataset_name, jurisdiction=manifest.jurisdiction)
        elif st == "PARQUET":
            return ParquetSourceConnector(sid, loc, name=manifest.dataset_name, jurisdiction=manifest.jurisdiction)
        else:
            raise ValueError(f"Unsupported connector source_type: {st}")

    def register_or_get_dataset(self, manifest: DatasetManifest) -> Dataset:
        """Register or retrieve the dataset record in the database."""
        ds = self.db.query(Dataset).filter(Dataset.id == manifest.dataset_id).first()
        if not ds:
            ds = Dataset(
                id=manifest.dataset_id,
                name=manifest.dataset_name,
                description=manifest.description,
                source_type=manifest.source_type,
                source_location=manifest.source_location,
                file_format=manifest.file_format,
                jurisdiction=manifest.jurisdiction,
                version=manifest.version,
                manifest_config=json.dumps(manifest.model_dump(), default=str),
                status="ACTIVE",
            )
            self.db.add(ds)
            self.db.commit()
            self.db.refresh(ds)
        return ds

    def create_job(self, job_type: str, target_id: str) -> ProcessingJob:
        """Create a new tracked background processing job."""
        job = ProcessingJob(
            id=gen_uuid(),
            job_type=job_type,
            target_id=target_id,
            status="Pending",
            progress_percent=0.0,
            started_at=utc_now(),
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_job(self, job_id: str, status: str, progress: float, error: Optional[str] = None):
        """Update job progress and completion status."""
        job = self.db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            job.status = status
            job.progress_percent = progress
            if error:
                job.error_details = error
            if status in ["Completed", "Failed"]:
                job.completed_at = utc_now()
            self.db.commit()

    def ingest_manifest(self, manifest: DatasetManifest, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute full dataset ingestion according to the manifest.
        Dispatches to tabular or document path based on file_format.
        """
        if not job_id:
            job = self.create_job("INGESTION", manifest.dataset_id)
            job_id = job.id

        try:
            self.update_job(job_id, "Downloading", 10.0)
            connector = self.get_connector(manifest)
            
            raw_bytes = connector.fetch()
            checksum = connector.compute_checksum(raw_bytes)

            ds = self.register_or_get_dataset(manifest)
            ds.checksum = checksum
            self.db.commit()

            # Record version
            ver = DatasetVersion(
                id=gen_uuid(),
                dataset_id=ds.id,
                version_tag=manifest.version,
                checksum=checksum,
                created_at=utc_now(),
                changelog=f"Ingested via {manifest.source_type} connector.",
            )
            self.db.add(ver)
            self.db.commit()

            fmt = manifest.file_format.lower()
            if fmt in ["csv", "parquet", "jsonl"]:
                # Tabular path
                result = self._ingest_tabular(manifest, connector, checksum, job_id)
            else:
                # Document path (PDF/TXT)
                result = self._ingest_document(manifest, raw_bytes, checksum, job_id)

            self.update_job(job_id, "Completed", 100.0)
            result["job_id"] = job_id
            result["dataset_id"] = manifest.dataset_id
            result["checksum"] = checksum
            return result

        except Exception as e:
            logger.error(f"Ingestion failed for dataset {manifest.dataset_id}: {e}", exc_info=True)
            self.update_job(job_id, "Failed", 0.0, error=str(e))
            raise

    def _ingest_tabular(self, manifest: DatasetManifest, connector: Any, checksum: str, job_id: str) -> Dict[str, Any]:
        """Ingest tabular records (e.g. CSV HMDA dataset) with validation."""
        self.update_job(job_id, "Extracting", 40.0)
        records = connector.read_records(limit=500)
        self.update_job(job_id, "Indexing", 70.0)

        ingested_count = 0
        for row in records:
            # If HMDA format, map to HMDARecord
            if "loan_amount" in row or "loan_type" in row:
                try:
                    rec = HMDARecord(
                        activity_year=str(row.get("activity_year", "2023")),
                        lei=str(row.get("lei", "UNKNOWN")),
                        uli=str(row.get("uli", "")),
                        loan_type=str(row.get("loan_type", "Conventional")),
                        loan_purpose=str(row.get("loan_purpose", "Home Purchase")),
                        occupancy_type=str(row.get("occupancy_type", "Principal Residence")),
                        loan_amount=float(str(row.get("loan_amount", 0)).replace(",", "") or 0),
                        action_taken=str(row.get("action_taken", "Loan Originated")),
                        state_code=str(row.get("state_code", "IL")),
                        county_code=str(row.get("county_code", "")),
                        interest_rate=float(row.get("interest_rate")) if row.get("interest_rate") and row.get("interest_rate") != "NA" else None,
                        property_value=float(row.get("property_value")) if row.get("property_value") and row.get("property_value") != "NA" else None,
                        loan_to_value_ratio=float(row.get("loan_to_value_ratio")) if row.get("loan_to_value_ratio") and row.get("loan_to_value_ratio") != "NA" else None,
                    )
                    self.db.add(rec)
                    ingested_count += 1
                except Exception:
                    pass

        import_rec = HMDADatasetImport(
            filename=manifest.source_location,
            total_records=ingested_count,
            source_checksum=checksum,
        )
        self.db.add(import_rec)
        self.db.commit()

        return {
            "type": "tabular",
            "records_ingested": ingested_count,
            "columns": list(records[0].keys()) if records else [],
        }

    def _ingest_document(self, manifest: DatasetManifest, raw_bytes: bytes, checksum: str, job_id: str) -> Dict[str, Any]:
        """Ingest document (PDF/TXT), chunk text, index in DB with dataset provenance."""
        self.update_job(job_id, "Extracting", 30.0)

        fmt = manifest.file_format.lower()
        if fmt == "pdf":
            parsed = self.pdf_service.extract(manifest.source_location)
            text = parsed["full_text"]
            total_pages = parsed["total_pages"]
        else:
            text = raw_bytes.decode("utf-8", errors="replace")
            total_pages = 1

        self.update_job(job_id, "Indexing", 60.0)

        # Ensure parent RegulatorySource exists for foreign key integrity
        reg_source = self.db.query(RegulatorySource).filter(RegulatorySource.source_id == manifest.dataset_id).first()
        if not reg_source:
            reg_source = RegulatorySource(
                source_id=manifest.dataset_id,
                source_name=manifest.dataset_name,
                source_url=manifest.source_location,
                source_type="REGULATORY_STATUTE",
                jurisdiction=manifest.jurisdiction or "US",
                issuing_authority="Consumer Financial Protection Bureau" if manifest.jurisdiction == "US" else "Reserve Bank of India",
                checksum=checksum,
                document_version=manifest.version,
                ingestion_status="INDEXED",
            )
            self.db.add(reg_source)
            self.db.commit()

        # Register document
        doc = RegulatoryDocument(
            id=gen_uuid(),
            source_id=manifest.dataset_id,
            title=manifest.dataset_name,
            jurisdiction=manifest.jurisdiction or "US",
            doc_type="REGULATORY_STATUTE",
            file_path=manifest.source_location,
            total_pages=total_pages,
            created_at=utc_now(),
        )
        self.db.add(doc)
        self.db.commit()

        # Chunk content
        chunks = self.chunker.chunk_text(
            text=text,
            doc_id=doc.id,
            jurisdiction=manifest.jurisdiction or "US",
            source_file=manifest.source_location,
        )

        indexed_chunks = 0
        for chunk_obj in chunks:
            chunk_obj.dataset_id = manifest.dataset_id
            self.db.add(chunk_obj)
            indexed_chunks += 1

        self.db.commit()

        return {
            "type": "document",
            "document_id": doc.id,
            "total_pages": total_pages,
            "total_chunks_indexed": indexed_chunks,
        }
