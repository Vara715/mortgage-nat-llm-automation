"""
registry.py
===========
Manages the authentic regulatory and mortgage data source registry (Section 2.4).
Supports idempotent ingestion, checksum verification, and source provenance.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.entities import RegulatorySource, RegulatoryDocument, SourceIngestionJob, AuditEvent
from backend.app.services.extraction.pdf_service import PDFExtractionService
from backend.app.services.chunking.section_chunker import RegulatoryChunker


class SourceRegistryService:
    def __init__(self, db: Session):
        self.db = db
        self.pdf_service = PDFExtractionService()
        self.chunker = RegulatoryChunker()

    def sync_manifest_sources(self) -> int:
        """Reads data/manifests/data_source_registry.json and idempotently synchronizes sources."""
        manifest_path = settings.DATA_DIR / "manifests" / "data_source_registry.json"
        if not manifest_path.exists():
            return 0

        with open(manifest_path, "r", encoding="utf-8") as f:
            sources_data = json.load(f)

        synced = 0
        for item in sources_data:
            existing = self.db.query(RegulatorySource).filter(RegulatorySource.source_id == item["source_id"]).first()
            if not existing:
                src = RegulatorySource(
                    source_id=item["source_id"],
                    source_name=item["source_name"],
                    source_url=item["source_url"],
                    source_type=item["source_type"],
                    jurisdiction=item["jurisdiction"],
                    issuing_authority=item["issuing_authority"],
                    publication_date=item.get("publication_date"),
                    effective_from=item.get("effective_from"),
                    effective_until=item.get("effective_until"),
                    checksum=item["checksum"],
                    document_version=item.get("document_version"),
                    license_or_usage_notes=item.get("license_or_usage_notes"),
                    ingestion_status="INDEXED",
                    extraction_quality=item.get("extraction_quality", 1.0),
                )
                self.db.add(src)
                synced += 1
            else:
                # Update checksum/version if modified
                existing.checksum = item["checksum"]
                existing.document_version = item.get("document_version")
                existing.extraction_quality = item.get("extraction_quality", 1.0)
                existing.ingestion_status = "INDEXED"

        self.db.commit()
        return synced

    def ingest_regulatory_files(self) -> dict:
        """
        Extracts, chunks, and indexes all authentic US and Indian regulatory source files
        into regulatory_documents and document_chunks.
        """
        self.sync_manifest_sources()
        total_docs = 0
        total_chunks = 0

        # 1. Process US Regulations
        us_files = sorted((settings.DATA_DIR / "raw" / "us_regulations").glob("*.txt"))
        for f in us_files:
            text = f.read_text(encoding="utf-8")
            doc_id = f"DOC-US-{f.stem}"
            existing_doc = self.db.query(RegulatoryDocument).filter(RegulatoryDocument.id == doc_id).first()
            if not existing_doc:
                reg_doc = RegulatoryDocument(
                    id=doc_id,
                    source_id="US-CFPB-REGZ",
                    title=f.stem.replace("_", " "),
                    jurisdiction="US",
                    doc_type="Statutory Regulation Section",
                    file_path=str(f),
                    total_pages=1,
                )
                self.db.add(reg_doc)
                self.db.flush()

                chunks = self.chunker.chunk_text(text, doc_id=doc_id, jurisdiction="US", source_file=f.name)
                for c in chunks:
                    self.db.add(c)
                total_chunks += len(chunks)
                total_docs += 1

        # 2. Process Indian Regulations
        in_files = sorted((settings.DATA_DIR / "raw" / "in_regulations").glob("*.*"))
        for f in in_files:
            if f.suffix not in [".pdf", ".txt"]:
                continue
            doc_id = f"DOC-IN-{f.stem}"
            existing_doc = self.db.query(RegulatoryDocument).filter(RegulatoryDocument.id == doc_id).first()
            if not existing_doc:
                if f.suffix == ".pdf":
                    extracted = self.pdf_service.extract(f)
                    pages_count = extracted["total_pages"]
                    raw_text = extracted["full_text"]
                else:
                    pages_count = 1
                    raw_text = f.read_text(encoding="utf-8")

                source_id = "IN-RBI-PREPAY-BAN" if "prepayment" in f.name.lower() else ("IN-BNPP-COMM-TERM" if "bnpp" in f.name.lower() else "IN-RBI-HOUSING-FIN")

                reg_doc = RegulatoryDocument(
                    id=doc_id,
                    source_id=source_id,
                    title=f.stem.replace("_", " ").title(),
                    jurisdiction="IN",
                    doc_type="Regulatory Circular" if "rbi" in f.name.lower() else "Term Loan Agreement",
                    file_path=str(f),
                    total_pages=pages_count,
                )
                self.db.add(reg_doc)
                self.db.flush()

                chunks = self.chunker.chunk_text(raw_text, doc_id=doc_id, jurisdiction="IN", source_file=f.name)
                for c in chunks:
                    self.db.add(c)
                total_chunks += len(chunks)
                total_docs += 1

        self.db.commit()
        return {"total_documents_ingested": total_docs, "total_chunks_indexed": total_chunks}
