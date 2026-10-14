"""
audit.py
========
API endpoints for inspecting the immutable compliance audit trail.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.review import AuditEventResponse
from backend.app.services.audit.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get("/events", response_model=List[AuditEventResponse])
def get_audit_trail(
    limit: int = Query(50, ge=1, le=200),
    entity_id: Optional[str] = None,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return AuditService.get_events(db=db, limit=limit, entity_id=entity_id, event_type=event_type)
