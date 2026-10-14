"""
review.py
=========
Pydantic schemas for human review tasks, decisions, and audit events.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel
from backend.app.schemas.compliance import ComplianceFindingSchema


class ReviewTaskResponse(BaseModel):
    id: str
    finding_id: str
    status: str
    assigned_to: Optional[str] = None
    created_at: datetime
    finding: ComplianceFindingSchema


class ReviewDecisionRequest(BaseModel):
    decision: str  # 'ACCEPTED', 'REJECTED', 'MODIFIED'
    new_status: str  # 'POTENTIAL_ISSUE', 'NO_ISSUE_IDENTIFIED', 'NEEDS_REVIEW'
    comments: Optional[str] = None
    corrected_loan_value: Optional[str] = None


class ReviewDecisionResponse(BaseModel):
    id: str
    review_task_id: str
    reviewer_id: str
    decision: str
    original_status: str
    new_status: str
    comments: Optional[str] = None
    decided_at: datetime


class AuditEventResponse(BaseModel):
    id: str
    event_type: str
    actor: str
    entity_type: str
    entity_id: str
    payload: Dict[str, Any]
    timestamp: datetime
