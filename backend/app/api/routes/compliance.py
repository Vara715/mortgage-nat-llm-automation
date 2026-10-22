"""
compliance.py
=============
API endpoints for running statutory compliance analyses, retrieving findings,
and inspecting grounded evidence citations.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timezone

from backend.app.db.session import get_db
from backend.app.models.entities import (
    ComplianceAnalysis,
    ComplianceFinding,
    FindingEvidence,
    LoanDocument,
    ExtractedLoanField,
)
from backend.app.schemas.compliance import (
    ComplianceAnalysisResponse,
    ComplianceFindingSchema,
    LoanTermEvidence,
    RegulatoryEvidenceItem,
)
from backend.app.services.compliance.analyzer import ComplianceAnalyzerService

router = APIRouter(prefix="/compliance", tags=["Compliance Analysis"])


def _build_analysis_response(analysis: ComplianceAnalysis, db: Session) -> ComplianceAnalysisResponse:
    loan_doc = db.query(LoanDocument).filter(LoanDocument.id == analysis.loan_document_id).first()
    doc_name = loan_doc.filename if loan_doc else "Loan Document"

    finding_schemas = []
    for f in analysis.findings:
        evidence_items = []
        for ev in f.evidence:
            evidence_items.append(
                RegulatoryEvidenceItem(
                    source_name=ev.source_name,
                    source_url=ev.source_url,
                    citation=ev.citation,
                    page_number=ev.page_number,
                    quoted_text=ev.quoted_text,
                    relevance_score=ev.score or 1.0,
                )
            )

        # Retrieve source page & excerpt from extracted field if available
        field_rec = (
            db.query(ExtractedLoanField)
            .filter(
                ExtractedLoanField.loan_document_id == analysis.loan_document_id,
                ExtractedLoanField.field_name == f.loan_field,
            )
            .first()
        )
        src_page = field_rec.source_page if field_rec else 1
        src_excerpt = field_rec.source_excerpt if field_rec else "Referenced in contractual terms"

        finding_schemas.append(
            ComplianceFindingSchema(
                finding_id=f.id,
                rule_id=f.rule_id,
                category=f.category,
                severity=f.severity,
                status=f.status,
                loan_term=LoanTermEvidence(
                    field=f.loan_field,
                    value=f.extracted_value,
                    source_page=src_page,
                    source_excerpt=src_excerpt,
                ),
                regulatory_evidence=evidence_items,
                reasoning=f.reasoning,
                missing_information=[],
                recommended_action=f.recommended_action or "Review contractual term",
                review_status=f.review_status,
            )
        )

    return ComplianceAnalysisResponse(
        analysis_id=analysis.id,
        loan_document_id=analysis.loan_document_id,
        document_name=doc_name,
        jurisdiction=analysis.jurisdiction,
        overall_status=analysis.overall_status,
        summary=analysis.summary,
        findings=finding_schemas,
        limitations=[
            "mortgage_assistant is an automated decision-support system and does not provide legal advice.",
            "Absence of an issue does not guarantee regulatory compliance under unevaluated rules.",
            "All findings must be confirmed by a certified compliance officer or legal counsel.",
        ],
        generated_at=analysis.generated_at.isoformat() if analysis.generated_at else "",
    )


@router.post("/analyze", response_model=ComplianceAnalysisResponse)
def analyze_compliance_post(payload: dict, db: Session = Depends(get_db)):
    """Run compliance analysis accepting document_id in JSON payload."""
    doc_id = payload.get("document_id")
    if not doc_id:
        raise HTTPException(status_code=400, detail="Missing document_id in request body")
    service = ComplianceAnalyzerService(db)
    try:
        return service.analyze_document(doc_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze/{doc_id}", response_model=ComplianceAnalysisResponse)
def run_compliance_analysis(doc_id: str, db: Session = Depends(get_db)):
    service = ComplianceAnalyzerService(db)
    try:
        response = service.analyze_document(doc_id)
        return response
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/analyses", response_model=List[ComplianceAnalysisResponse])
def list_analyses(jurisdiction: str = None, db: Session = Depends(get_db)):
    query = db.query(ComplianceAnalysis)
    if jurisdiction:
        query = query.filter(ComplianceAnalysis.jurisdiction == jurisdiction.upper())
    analyses = query.order_by(ComplianceAnalysis.generated_at.desc()).limit(50).all()
    return [_build_analysis_response(a, db) for a in analyses]


@router.get("/analyses/{analysis_id}", response_model=ComplianceAnalysisResponse)
def get_analysis(analysis_id: str, db: Session = Depends(get_db)):
    analysis = db.query(ComplianceAnalysis).filter(ComplianceAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Compliance analysis not found")
    return _build_analysis_response(analysis, db)


@router.get("/analyses/{analysis_id}/findings", response_model=List[ComplianceFindingSchema])
def get_analysis_findings(analysis_id: str, db: Session = Depends(get_db)):
    """Retrieve detailed findings and evidence for a specific compliance analysis."""
    analysis = db.query(ComplianceAnalysis).filter(ComplianceAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Compliance analysis not found")
    res = _build_analysis_response(analysis, db)
    return res.findings
