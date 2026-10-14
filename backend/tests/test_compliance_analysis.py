"""
test_compliance_analysis.py
============================
End-to-end tests for ComplianceAnalyzerService orchestration.
"""

from backend.app.db.session import SessionLocal
from backend.app.models.entities import LoanDocument, ComplianceAnalysis, ReviewTask
from backend.app.services.compliance.analyzer import ComplianceAnalyzerService


def test_compliance_analysis_workflow():
    db = SessionLocal()
    try:
        # Fetch the seeded US non-compliant document
        doc = db.query(LoanDocument).filter(LoanDocument.filename == "us_non_compliant_highfee_note.txt").first()
        assert doc is not None

        analyzer = ComplianceAnalyzerService(db)
        res = analyzer.analyze_document(doc.id)

        assert res.loan_document_id == doc.id
        assert res.jurisdiction == "US"
        assert res.overall_status in ["POTENTIAL_ISSUE", "NEEDS_REVIEW"]
        assert len(res.findings) >= 3

        # Check evidence citations
        has_citations = any(len(f.regulatory_evidence) > 0 for f in res.findings)
        assert has_citations is True

        # Check that review tasks were registered for flagged findings
        tasks = db.query(ReviewTask).all()
        assert len(tasks) > 0
    finally:
        db.close()
