"""
seed_data.py
============
Pre-seeds MortgageGuard AI with:
1. Authoritative US and Indian regulatory source files and indexed chunks
2. Authentic CFPB/FFIEC HMDA 2023 public mortgage records
3. Standard sample loan documents across US and Indian jurisdictions
4. Initial baseline compliance analyses and human review queue tasks
"""

import sys
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal, init_db
from backend.app.models.entities import LoanDocument
from backend.app.services.source_registry.registry import SourceRegistryService
from backend.app.services.hmda.loader import HMDALoaderService
from backend.app.services.compliance.analyzer import ComplianceAnalyzerService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")


def seed_database():
    logger.info("Step 1: Initializing database tables...")
    init_db()

    db = SessionLocal()
    try:
        logger.info("Step 2: Ingesting authentic regulatory sources & building hybrid chunks...")
        source_service = SourceRegistryService(db)
        sync_stats = source_service.ingest_regulatory_files()
        logger.info(f"Sources & chunks synchronized: {sync_stats}")

        logger.info("Step 3: Ingesting authentic HMDA 2023 public mortgage dataset subset...")
        hmda_csv = settings.DATA_DIR / "raw" / "hmda" / "hmda_2023_subset.csv"
        if hmda_csv.exists():
            hmda_loader = HMDALoaderService(db)
            hmda_res = hmda_loader.import_csv(hmda_csv)
            logger.info(f"HMDA records imported: {hmda_res.total_records_imported} rows (checksum: {hmda_res.checksum[:10]}...)")
        else:
            logger.warning(f"HMDA file not found at {hmda_csv}")

        logger.info("Step 4: Registering and analyzing sample loan documents...")
        sample_dir = settings.DATA_DIR / "raw" / "sample_loans"
        sample_files = [
            ("us_compliant_qm_note.txt", "US", "Residential Mortgage Note (Uniform Instrument)"),
            ("us_non_compliant_highfee_note.txt", "US", "Residential Mortgage Note (Non-Compliant)"),
            ("compliant_home_loan_agreement.txt", "IN", "Individual Housing Loan Agreement (Compliant)"),
            ("non_compliant_home_loan_agreement.txt", "IN", "Individual Housing Loan Agreement (Non-Compliant)"),
        ]

        analyzer = ComplianceAnalyzerService(db)

        for filename, jurisdiction, doc_type in sample_files:
            file_path = sample_dir / filename
            if not file_path.exists():
                logger.warning(f"Sample file {filename} does not exist at {file_path}")
                continue

            existing_doc = db.query(LoanDocument).filter(LoanDocument.filename == filename).first()
            if not existing_doc:
                doc = LoanDocument(
                    filename=filename,
                    file_type="txt",
                    file_size=file_path.stat().st_size,
                    jurisdiction=jurisdiction,
                    doc_type=doc_type,
                    status="UPLOADED",
                    file_path=str(file_path),
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                logger.info(f"Registered sample loan: {filename} (ID: {doc.id})")

                # Run baseline compliance analysis
                res = analyzer.analyze_document(doc.id)
                logger.info(
                    f"Analyzed {filename}: Overall Status = {res.overall_status}, Findings Count = {len(res.findings)}"
                )
            else:
                logger.info(f"Sample loan {filename} already registered (ID: {existing_doc.id})")

        logger.info("Database seeding completed successfully!")

    except Exception as e:
        logger.error(f"Error during database seeding: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
