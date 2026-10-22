"""
automate_pipeline.py
====================
End-to-End Automated Loan Ingestion & Compliance Audit Pipeline for mortgage_assistant.
Implements the fully automated vision from Slides 2, 3, 7, 8, & 10:

"Auto Trigger -> New PDF scraped/uploaded -> Conversion & Audit runs automatically"

Features:
1. Single-Command Mode: Point to ANY loan PDF/TXT -> Complete audit executed automatically.
2. Watch Folder Mode: Continuously monitors an incoming directory (e.g. data/incoming/)
   and processes documents the instant they are dropped in.
3. Automatically triggers:
   - Ingestion & OCR Quality Scoring (Slide 3)
   - Layout & Structured Term Extraction (Slide 7)
   - Hybrid Vector DB Regulatory Retrieval (Slide 8)
   - Statutory Rule Checking & LLM Reasoning (Slide 8)
   - Human Review Queue (HITL) Escalation (if non-compliant or missing terms)
   - Official PDF Report Generation in data/reports/
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal, init_db
from backend.app.models.entities import LoanDocument, ExtractedLoanField
from backend.app.services.extraction.pdf_service import PDFExtractionService
from backend.app.services.loan_extraction.term_extractor import LoanTermExtractor
from backend.app.services.compliance.analyzer import ComplianceAnalyzerService
from backend.app.services.reporting.report_generator import ComplianceReportGenerator
from backend.app.services.audit.audit_service import AuditService
from extraction.pdf_extractor import PDFExtractor


def print_banner(msg: str):
    print("\n" + "=" * 80)
    print(f"  {msg.upper()}")
    print("=" * 80)


def process_document_automated(file_path: Path, jurisdiction_override: str = None) -> dict:
    """
    Executes the 100% automated pipeline on a given document file.
    """
    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return {"status": "ERROR", "message": f"File not found: {file_path}"}

    print_banner(f"AUTOMATED PIPELINE TRIGGERED: {file_path.name}")
    start_time = time.time()
    db = SessionLocal()

    try:
        # [Step 1/5] Ingest & Assess OCR Quality
        print("[1/5] Ingesting document & evaluating OCR extraction quality...")
        is_pdf = file_path.suffix.lower() == ".pdf"
        file_bytes = file_path.read_bytes()

        if is_pdf:
            extractor = PDFExtractor(enable_visual_debugging=True)
            doc_struct = extractor.extract(file_path)
            full_text = doc_struct.full_text
            ocr_quality = doc_struct.overall_quality_score
            quality_status = doc_struct.overall_quality_status
            total_pages = doc_struct.total_pages
            print(f"      -> Extracted {total_pages} page(s) | Quality: {ocr_quality} ({quality_status})")
        else:
            full_text = file_path.read_text(encoding="utf-8", errors="replace")
            ocr_quality = 1.0
            quality_status = "HIGH"
            total_pages = 1
            print(f"      -> Read text file | Quality: {ocr_quality} ({quality_status})")

        # [Step 2/5] Extract Structured Terms & Classify Document
        print("[2/5] Parsing legal clauses & extracting structured loan parameters...")
        term_extractor = LoanTermExtractor()
        extraction_result = term_extractor.extract_terms(full_text, document_name=file_path.name)
        jurisdiction = (jurisdiction_override or extraction_result.jurisdiction).upper()

        print(f"      -> Classified Type : {extraction_result.doc_type}")
        print(f"      -> Jurisdiction    : {jurisdiction}")
        print(f"      -> Extracted Terms : {len(extraction_result.fields)} contractual variables")

        # Save to Database
        loan_doc = LoanDocument(
            filename=file_path.name,
            file_type=file_path.suffix.lstrip(".").lower() or "pdf",
            file_size=len(file_bytes),
            jurisdiction=jurisdiction,
            doc_type=extraction_result.doc_type,
            status="PARSED",
            file_path=str(file_path.resolve()),
        )
        db.add(loan_doc)
        db.flush()

        for field_name, f_rec in extraction_result.fields.items():
            field_obj = ExtractedLoanField(
                loan_document_id=loan_doc.id,
                field_name=field_name,
                field_value_str=f_rec.value_str,
                field_value_num=f_rec.value_num,
                source_page=f_rec.source_page,
                source_excerpt=f_rec.source_excerpt,
                confidence=f_rec.confidence,
                is_verified=False,
            )
            db.add(field_obj)
        db.commit()

        # [Step 3/5] Regulatory Compliance Audit & Live Hybrid Search
        print("[3/5] Auditing against statutory regulations & querying vector knowledge base...")
        analyzer = ComplianceAnalyzerService(db)
        analysis_res = analyzer.analyze_document(loan_doc.id)

        print(f"      -> Overall Audit Status : [{analysis_res.overall_status}]")
        print(f"      -> Evaluated Findings   : {len(analysis_res.findings)} statutory checks")

        violations = [f for f in analysis_res.findings if f.status == "POTENTIAL_ISSUE"]
        reviews = [f for f in analysis_res.findings if f.status == "NEEDS_REVIEW"]
        compliant = [f for f in analysis_res.findings if f.status == "NO_ISSUE_IDENTIFIED"]

        print(f"      -> Passed Checks        : {len(compliant)}")
        print(f"      -> Non-Compliant Rules  : {len(violations)}")
        print(f"      -> Review Items         : {len(reviews)}")

        # [Step 4/5] Human-in-the-Loop Review Escalation
        print("[4/5] Checking Human-in-the-Loop (HITL) escalation gates...")
        if violations or reviews or quality_status == "DEGRADED":
            print("      -> [ESCALATED] Automatically routed to Underwriter Review Queue (/api/reviews/queue)")
        else:
            print("      -> [CLEAN] All checks verified compliant. Automated green sanction approved.")

        # [Step 5/5] Generate Official PDF Compliance Report
        print("[5/5] Compiling official PDF Compliance Audit Report...")
        reports_dir = ROOT_DIR / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        pdf_report_path = reports_dir / f"Audit_Report_{file_path.stem}_{analysis_res.analysis_id[:8]}.pdf"

        report_gen = ComplianceReportGenerator()
        report_bytes = report_gen.generate_pdf(analysis_res)
        pdf_report_path.write_bytes(report_bytes)
        print(f"      -> Wrote PDF Audit Report: {pdf_report_path.resolve()}")

        elapsed = time.time() - start_time
        print("\n" + "-" * 80)
        print(f"  AUTOMATION SUMMARY: [{analysis_res.overall_status}] (Completed in {elapsed:.2f}s)")
        print("-" * 80)
        print(f"  Document Name  : {file_path.name}")
        print(f"  Audit ID       : {analysis_res.analysis_id}")
        print(f"  Executive Brief: {analysis_res.summary[:200]}...")
        print(f"  PDF Report     : {pdf_report_path.name}")
        print("=" * 80 + "\n")

        return {
            "status": "SUCCESS",
            "audit_status": analysis_res.overall_status,
            "document_id": loan_doc.id,
            "analysis_id": analysis_res.analysis_id,
            "pdf_report": str(pdf_report_path),
            "elapsed_seconds": round(elapsed, 2),
        }

    except Exception as e:
        print(f"\n[FATAL ERROR] Automated pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "FAILED", "error": str(e)}
    finally:
        db.close()


def watch_incoming_folder(watch_dir: Path, poll_interval: int = 3):
    """
    Watches an incoming directory for new PDF/TXT loan uploads and
    triggers the pipeline automatically the moment a file appears.
    """
    watch_dir = Path(watch_dir)
    watch_dir.mkdir(parents=True, exist_ok=True)
    processed_dir = watch_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    print_banner(f"WATCH FOLDER DAEMON ACTIVE: {watch_dir.resolve()}")
    print(f"  Drop ANY loan PDF or agreement into this directory.")
    print(f"  The system will automatically detect, extract, audit, and generate reports.")
    print(f"  Polling every {poll_interval}s. Press Ctrl+C to stop.\n")

    seen_files = set()

    try:
        while True:
            for p in watch_dir.iterdir():
                if p.is_file() and p.suffix.lower() in [".pdf", ".txt"] and p.name not in seen_files:
                    seen_files.add(p.name)
                    print(f"\n[EVENT] New loan document detected: {p.name}")
                    res = process_document_automated(p)
                    # Move to processed subdirectory
                    dest = processed_dir / p.name
                    shutil.move(str(p), str(dest))
                    print(f"[ARCHIVE] Moved processed file to: {dest.name}")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[STOPPED] Watch folder daemon terminated by user.")


def main():
    parser = argparse.ArgumentParser(description="mortgage_assistant Automated Pipeline Runner")
    parser.add_argument("--file", type=str, help="Path to loan contract to audit automatically")
    parser.add_argument("--jurisdiction", type=str, default=None, help="Jurisdiction override ('IN' or 'US')")
    parser.add_argument("--watch-dir", type=str, help="Folder to continuously monitor for automated uploads")

    args = parser.parse_args()

    init_db()

    if args.watch_dir:
        watch_incoming_folder(Path(args.watch_dir))
    elif args.file:
        process_document_automated(Path(args.file), args.jurisdiction)
    else:
        print("Please specify --file <path> or --watch-dir <folder_path>.")
        print("Example: python scripts/automate_pipeline.py --file data/raw/sample_loans/bnpp_term_loan_agreement_india.pdf")


if __name__ == "__main__":
    main()
