"""
loader.py
=========
Idempotent ingestion service for authentic HMDA records (Section 6.4).
"""

import csv
import hashlib
from pathlib import Path
from sqlalchemy.orm import Session
from backend.app.models.entities import HMDARecord, HMDADatasetImport, AuditEvent
from backend.app.schemas.hmda import HMDAImportResponse


class HMDALoaderService:
    def __init__(self, db: Session):
        self.db = db

    def import_csv(self, file_path: str | Path) -> HMDAImportResponse:
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"HMDA file not found: {path}")

        # Compute SHA-256
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        checksum = h.hexdigest()

        # Idempotent check
        existing_import = self.db.query(HMDADatasetImport).filter(HMDADatasetImport.source_checksum == checksum).first()
        if existing_import:
            count = self.db.query(HMDARecord).count()
            return HMDAImportResponse(
                import_id=existing_import.id,
                filename=existing_import.filename,
                total_records_imported=count,
                imported_at=existing_import.imported_at,
                checksum=checksum,
            )

        # Ingest rows
        records_to_insert = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    loan_amt = float(row.get("loan_amount", 0.0))
                    rate = float(row.get("interest_rate")) if row.get("interest_rate") else None
                    spread = float(row.get("rate_spread")) if row.get("rate_spread") else None
                    prop_val = float(row.get("property_value")) if row.get("property_value") else None
                    ltv = float(row.get("loan_to_value_ratio")) if row.get("loan_to_value_ratio") else None

                    rec = HMDARecord(
                        activity_year=row.get("activity_year", "2023"),
                        lei=row.get("lei", "UNKNOWN"),
                        uli=row.get("uli"),
                        loan_type=row.get("loan_type", "Conventional"),
                        loan_purpose=row.get("loan_purpose", "Home Purchase"),
                        occupancy_type=row.get("occupancy_type", "Principal Residence"),
                        loan_amount=loan_amt,
                        action_taken=row.get("action_taken", "Loan Originated"),
                        action_taken_date=row.get("action_taken_date"),
                        state_code=row.get("state_code", "IL"),
                        county_code=row.get("county_code", "17031"),
                        interest_rate=rate,
                        rate_spread=spread,
                        property_value=prop_val,
                        loan_to_value_ratio=ltv,
                    )
                    records_to_insert.append(rec)
                except Exception:
                    continue

        if records_to_insert:
            self.db.bulk_save_objects(records_to_insert)

        import_rec = HMDADatasetImport(
            filename=path.name,
            total_records=len(records_to_insert),
            source_checksum=checksum,
        )
        self.db.add(import_rec)
        self.db.commit()

        return HMDAImportResponse(
            import_id=import_rec.id,
            filename=import_rec.filename,
            total_records_imported=len(records_to_insert),
            imported_at=import_rec.imported_at,
            checksum=checksum,
        )
