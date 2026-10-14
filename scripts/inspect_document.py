"""
inspect_document.py
===================
CLI tool to inspect, classify, and extract loan terms with provenance
from any PDF or text mortgage document.

Usage:
    python scripts/inspect_document.py --file data/raw/sample_loans/us_compliant_qm_note.txt
    python scripts/inspect_document.py --file data/raw/sample_loans/compliant_home_loan_agreement.txt
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.services.extraction.pdf_service import PDFExtractionService
from backend.app.services.classification.classifier import DocumentClassifier
from backend.app.services.loan_extraction.term_extractor import LoanTermExtractor


def _col(text: str, width: int) -> str:
    return str(text)[:width].ljust(width)


def inspect(file_path: str):
    p = Path(file_path)
    if not p.exists():
        print(f"[ERROR] File not found: {p}")
        sys.exit(1)

    print(f"\n=================================================================================")
    print(f"  DOCUMENT INSPECTION REPORT: {p.name}")
    print(f"=================================================================================")

    # 1. Text Extraction
    if p.suffix.lower() == ".pdf":
        pdf_svc = PDFExtractionService()
        parsed = pdf_svc.extract(p)
        text = parsed["full_text"]
        pages = parsed["total_pages"]
        print(f"  Format: PDF  |  Pages: {pages}  |  Tables: {parsed['tables_extracted']}")
    else:
        text = p.read_text(encoding="utf-8", errors="replace")
        pages = 1
        print(f"  Format: Plain Text  |  Pages: 1  |  Characters: {len(text):,}")

    # 2. Classification
    classifier = DocumentClassifier()
    cls_res = classifier.classify(text, filename=p.name)
    print(f"\n  [DOCUMENT CLASSIFICATION]")
    print(f"  Predicted Category : {cls_res.predicted_category}")
    print(f"  Calibrated Score   : {cls_res.confidence * 100:.1f}%")
    print(f"  Review Status      : {cls_res.review_status}")
    print(f"  Cues Detected      : {', '.join(cls_res.supporting_features) if cls_res.supporting_features else 'General text cues'}")

    # 3. Loan Term Extraction
    extractor = LoanTermExtractor()
    ext_res = extractor.extract_terms(text, document_name=p.name)
    print(f"\n  [EXTRACTED LOAN TERMS & PROVENANCE]")
    print(f"  Jurisdiction Detected : {ext_res.jurisdiction}")
    print(f"  Borrower Type         : {ext_res.borrower_type}")
    print(f"  -------------------------------------------------------------------------------")
    hdr = _col("FIELD NAME", 28) + _col("VALUE", 20) + _col("EXCERPT", 30)
    print(f"  {hdr}")
    print(f"  {'-' * 78}")

    for fname, rec in ext_res.fields.items():
        val_str = rec.value_str or str(rec.value)
        exc_str = (rec.source_excerpt or "").replace("\n", " ")[:28]
        row = _col(fname, 28) + _col(val_str, 20) + _col(exc_str, 30)
        print(f"  {row}")

    if ext_res.missing_fields:
        print(f"\n  [MISSING MANDATORY FIELDS]")
        for mf in ext_res.missing_fields:
            print(f"  - {mf} (NOT PROVIDED IN DOCUMENT)")

    print(f"=================================================================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect and extract terms from mortgage loan documents.")
    parser.add_argument("pos_file", nargs="?", default=None, help="Path to loan PDF or TXT file")
    parser.add_argument("--file", "-f", default=None, help="Path to loan PDF or TXT file")
    args = parser.parse_args()
    target_file = args.file or args.pos_file
    if not target_file:
        parser.error("Please provide a file path via --file <path> or as a positional argument.")
    inspect(target_file)
