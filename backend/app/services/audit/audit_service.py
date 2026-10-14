"""
audit_service.py
================
Immutable audit logging service for regulatory compliance tracking and HITL actions.
"""

import json
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from backend.app.models.entities import AuditEvent
from backend.app.schemas.review import AuditEventResponse


class AuditService:
    @staticmethod
    def log(
        db: Session,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: Dict[str, Any],
        actor: str = "compliance_analyst",
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            actor=actor,
            entity_type=entity_type,
            entity_id=str(entity_id),
            payload=json.dumps(payload, default=str),
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_events(
        db: Session,
        limit: int = 100,
        entity_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[AuditEventResponse]:
        query = db.query(AuditEvent)
        if entity_id:
            query = query.filter(AuditEvent.entity_id == entity_id)
        if event_type:
            query = query.filter(AuditEvent.event_type == event_type)
        events = query.order_by(AuditEvent.timestamp.desc()).limit(limit).all()

        results = []
        for e in events:
            try:
                parsed_payload = json.loads(e.payload) if e.payload else {}
            except Exception:
                parsed_payload = {"raw": e.payload}
            results.append(
                AuditEventResponse(
                    id=e.id,
                    event_type=e.event_type,
                    actor=e.actor,
                    entity_type=e.entity_type,
                    entity_id=e.entity_id,
                    payload=parsed_payload,
                    timestamp=e.timestamp,
                )
            )
        return results
