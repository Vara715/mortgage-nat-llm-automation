"""
reviews.py
==========
API endpoints for the Human-in-the-Loop (HITL) compliance review queue and decision logging.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from backend.app.db.session import get_db
from backend.app.models.entities import (
    ReviewTask,
    ReviewDecision,
    ComplianceFinding,
    FindingEvidence,
    ComplianceAnalysis,
    ExtractedLoanField,
)
from backend.app.schemas.review import (
    ReviewTaskResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from backend.app.schemas.compliance import (
    ComplianceFindingSchema,
    LoanTermEvidence,
    RegulatoryEvidenceItem,
)
from backend.app.services.audit.audit_service import AuditService

router = APIRouter(prefix="/reviews", tags=["Human Review"])


def _to_finding_schema(f: ComplianceFinding, db: Session) -> ComplianceFindingSchema:
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

    field_rec = (
        db.query(ExtractedLoanField)
        .join(ComplianceAnalysis, ComplianceAnalysis.loan_document_id == ExtractedLoanField.loan_document_id)
        .filter(
            ComplianceAnalysis.id == f.analysis_id,
            ExtractedLoanField.field_name == f.loan_field,
        )
        .first()
    )
    src_page = field_rec.source_page if field_rec else 1
    src_excerpt = field_rec.source_excerpt if field_rec else "Contractual clause"

    return ComplianceFindingSchema(
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


@router.get("/queue", response_model=List[ReviewTaskResponse])
def get_review_queue(db: Session = Depends(get_db)):
    """Retrieve pending review queue tasks for human analysts."""
    return list_tasks(status="PENDING", db=db)


@router.get("/tasks", response_model=List[ReviewTaskResponse])
def list_tasks(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(ReviewTask)
    if status:
        query = query.filter(ReviewTask.status == status.upper())
    tasks = query.order_by(ReviewTask.created_at.desc()).all()

    result = []
    for t in tasks:
        finding = db.query(ComplianceFinding).filter(ComplianceFinding.id == t.finding_id).first()
        if not finding:
            continue
        result.append(
            ReviewTaskResponse(
                id=t.id,
                finding_id=t.finding_id,
                status=t.status,
                assigned_to=t.assigned_to,
                created_at=t.created_at,
                finding=_to_finding_schema(finding, db),
            )
        )
    return result


@router.get("/tasks/{task_id}", response_model=ReviewTaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")
    finding = db.query(ComplianceFinding).filter(ComplianceFinding.id == task.finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Associated finding not found")

    return ReviewTaskResponse(
        id=task.id,
        finding_id=task.finding_id,
        status=task.status,
        assigned_to=task.assigned_to,
        created_at=task.created_at,
        finding=_to_finding_schema(finding, db),
    )


@router.post("/tasks/{task_id}/decision", response_model=ReviewDecisionResponse)
def submit_decision(
    task_id: str,
    payload: ReviewDecisionRequest,
    reviewer_id: str = "compliance_officer",
    db: Session = Depends(get_db),
):
    task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found")

    finding = db.query(ComplianceFinding).filter(ComplianceFinding.id == task.finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    orig_status = finding.status
    finding.status = payload.new_status
    finding.review_status = payload.decision
    if payload.corrected_loan_value:
        finding.extracted_value = payload.corrected_loan_value

    task.status = "RESOLVED"

    decision = ReviewDecision(
        review_task_id=task.id,
        reviewer_id=reviewer_id,
        decision=payload.decision,
        original_status=orig_status,
        new_status=payload.new_status,
        comments=payload.comments,
    )
    db.add(decision)

    # Re-evaluate parent analysis overall_status
    analysis = db.query(ComplianceAnalysis).filter(ComplianceAnalysis.id == finding.analysis_id).first()
    if analysis:
        all_findings = db.query(ComplianceFinding).filter(ComplianceFinding.analysis_id == analysis.id).all()
        has_issue = any(f.status == "POTENTIAL_ISSUE" for f in all_findings)
        has_unresolved = any(f.status == "NEEDS_REVIEW" for f in all_findings)
        if has_issue:
            analysis.overall_status = "POTENTIAL_ISSUE"
        elif has_unresolved:
            analysis.overall_status = "NEEDS_REVIEW"
        else:
            analysis.overall_status = "NO_ISSUE_IDENTIFIED"

    db.commit()
    db.refresh(decision)

    AuditService.log(
        db=db,
        event_type="REVIEW_DECISION_RECORDED",
        actor=reviewer_id,
        entity_type="ReviewTask",
        entity_id=task.id,
        payload={
            "finding_id": finding.id,
            "decision": payload.decision,
            "original_status": orig_status,
            "new_status": payload.new_status,
            "comments": payload.comments,
        },
    )

    return ReviewDecisionResponse(
        id=decision.id,
        review_task_id=decision.review_task_id,
        reviewer_id=decision.reviewer_id,
        decision=decision.decision,
        original_status=decision.original_status,
        new_status=decision.new_status,
        comments=decision.comments,
        decided_at=decision.decided_at,
    )
