"""
reports.py
==========
API endpoints for compliance PDF report generation and download.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.entities import ComplianceAnalysis
from backend.app.api.routes.compliance import _build_analysis_response
from backend.app.services.reporting.report_generator import ComplianceReportGenerator
from backend.app.services.audit.audit_service import AuditService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/{analysis_id}/pdf")
def download_pdf_report(analysis_id: str, db: Session = Depends(get_db)):
    analysis = db.query(ComplianceAnalysis).filter(ComplianceAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Compliance analysis not found")

    analysis_response = _build_analysis_response(analysis, db)
    pdf_bytes = ComplianceReportGenerator.generate_pdf(analysis_response)

    AuditService.log(
        db=db,
        event_type="COMPLIANCE_REPORT_DOWNLOADED",
        entity_type="ComplianceAnalysis",
        entity_id=analysis_id,
        payload={"filename": f"Mortgage_Assistant_Report_{analysis_id[:8]}.pdf"},
    )

    filename = f"Mortgage_Assistant_Report_{analysis_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{analysis_id}/summary")
def get_report_summary(analysis_id: str, db: Session = Depends(get_db)):
    analysis = db.query(ComplianceAnalysis).filter(ComplianceAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Compliance analysis not found")
    return _build_analysis_response(analysis, db)
