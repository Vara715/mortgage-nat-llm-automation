"""
audit_loan.py
=============
End-to-end Compliance Audit CLI for any mortgage or loan agreement PDF/TXT.
Executes:
1. PDF/Text Parsing & Document Classification
2. Structured Loan Term Extraction with page provenance
3. Strict Jurisdiction Isolation (US CFPB vs IN RBI)
4. Deterministic Statutory Rule Evaluation
5. Live LLM Reasoning & Reviewer Inquiry Generation (Groq / OpenAI)
6. Human Review Queue routing & ReportLab PDF generation

Usage:
    python scripts/audit_loan.py data/raw/sample_loans/bnpp_term_loan_agreement_india.pdf
    python scripts/audit_loan.py data/raw/sample_loans/ireda_mortgage_loan_agreement.pdf
    python scripts/audit_loan.py data/raw/sample_loans/us_compliant_qm_note.txt
"""

import sys
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.db.session import SessionLocal, init_db
from backend.app.models.entities import LoanDocument
from backend.app.services.compliance.analyzer import ComplianceAnalyzerService


def audit(file_path: str):
    p = Path(file_path)
    if not p.exists():
        print(f"[ERROR] File not found: {p}")
        sys.exit(1)

    print("\n" + "=" * 85)
    print(f"  MORTGAGE COMPLIANCE AUDIT PIPELINE: {p.name}")
    print("=" * 85)

    db = SessionLocal()
    init_db()

    # 1. Register or find loan document
    file_bytes = p.read_bytes()
    loan_doc = db.query(LoanDocument).filter(LoanDocument.filename == p.name).first()
    if not loan_doc:
        loan_doc = LoanDocument(
            filename=p.name,
            file_type=p.suffix.replace(".", "").lower(),
            file_size=len(file_bytes),
            file_path=str(p.resolve()),
            status="UPLOADED",
        )
        db.add(loan_doc)
        db.commit()
        db.refresh(loan_doc)

    print(f"[1/4] Registered loan document: {loan_doc.id}")
    print(f"[2/4] Parsing document layout and extracting structured loan terms...")

    # 2. Run Compliance Analysis
    analyzer = ComplianceAnalyzerService(db)
    res = analyzer.analyze_document(loan_doc.id)

    print(f"[3/4] Evaluated deterministic statutory rules and retrieved legal evidence...")
    print(f"[4/4] Live LLM reasoned over findings and generated reviewer questions.\n")

    # Display results
    print("=" * 85)
    print(f"  AUDIT SUMMARY: {res.overall_status}")
    print(f"  Jurisdiction: {res.jurisdiction}  |  Document: {res.document_name}  |  Analysis ID: {res.analysis_id}")
    print("=" * 85)
    print(f"  {res.summary}\n")

    print("-" * 85)
    print("  STATUTORY COMPLIANCE FINDINGS")
    print("-" * 85)

    for i, f in enumerate(res.findings, 1):
        status_tag = f"[{f.status}]"
        print(f"\n  #{i} Rule: {f.rule_id} ({f.category}) - Severity: {f.severity}")
        print(f"     Status: {status_tag}")
        print(f"     Contract Term Evaluated: {f.loan_term.field} = {f.loan_term.value}")
        print(f"     Page Provenance: Page {f.loan_term.source_page} | Excerpt: \"{f.loan_term.source_excerpt[:90]}...\"")
        print(f"     Legal Reasoning:\n     {f.reasoning}")
        if f.regulatory_evidence:
            for ev in f.regulatory_evidence:
                print(f"     Evidence Citation: {ev.citation} ({ev.source_name})")
        if f.missing_information:
            print(f"     Reviewer Inquiries: {f.missing_information}")

    print("\n" + "=" * 85)
    disclaimer = getattr(res, "disclaimer", "morgage-loan-automation is an evidence-grounded decision-support platform and does not constitute formal legal advice.")
    print(f"  DISCLAIMER: {disclaimer}")
    print("=" * 85 + "\n")
    db.close()


def main():
    parser = argparse.ArgumentParser(description="Run complete compliance audit on a mortgage or loan document.")
    parser.add_argument("pos_file", nargs="?", default=None, help="Path to loan PDF or TXT file")
    parser.add_argument("--file", "-f", default=None, help="Path to loan PDF or TXT file")
    args = parser.parse_args()

    target = args.file or args.pos_file
    if not target:
        parser.error("Please provide a file path via positional argument or --file.")
    audit(target)


if __name__ == "__main__":
    main()
