"""
admin.py
========
Administrative POV API Router for MortgageGuard AI / TCS Mortgage Loan Compliance System.
Provides system diagnostics, agent telemetry, review queue oversight, and audit governance.
"""

import json
import os
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agent.orchestrator import orchestrator
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.entities import AuditEvent, ReviewTask, RegulatorySource, User
from backend.app.services.compliance.budget_optimizer import optimizer

router = APIRouter(prefix="/admin", tags=["Administration & Governance"])
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class AdminOverviewResponse(BaseModel):
    system_name: str
    version: str
    environment: str
    uptime_seconds: float
    platform_os: str
    python_version: str
    llm_provider: str
    default_model: str
    database_connected: bool
    total_sources_ingested: int
    total_pending_reviews: int
    registered_agents_count: int
    optimizer_telemetry: Dict[str, Any]


class AdminAgentInfo(BaseModel):
    name: str
    role: str
    capabilities: List[str]
    invocations: int
    health_status: str


class AdminOverrideRequest(BaseModel):
    decision: str = Field(..., description="'APPROVED', 'REJECTED', or 'WAIVED'")
    admin_notes: str = Field(..., description="Justification for administrative override")
    admin_username: str = Field(default="admin", description="Admin user performing override")


_START_TIME = time.time()


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(db: Session = Depends(get_db)):
    """Provides high-level system diagnostics and platform telemetry."""
    try:
        source_count = db.query(RegulatorySource).count()
        pending_reviews = db.query(ReviewTask).filter(ReviewTask.status == "PENDING").count()
        db_ok = True
    except Exception:
        source_count = 0
        pending_reviews = 0
        db_ok = False

    agents = orchestrator.get_registered_agents()

    return AdminOverviewResponse(
        system_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        uptime_seconds=round(time.time() - _START_TIME, 2),
        platform_os=platform.platform(),
        python_version=platform.python_version(),
        llm_provider=settings.LLM_PROVIDER,
        default_model=settings.DEFAULT_LLM_MODEL,
        database_connected=db_ok,
        total_sources_ingested=source_count,
        total_pending_reviews=pending_reviews,
        registered_agents_count=len(agents),
        optimizer_telemetry=optimizer.get_telemetry(),
    )


@router.get("/agents", response_model=List[AdminAgentInfo])
def get_agent_telemetry():
    """Lists all registered specialized agents, their capabilities, and execution metrics."""
    agents_data = orchestrator.get_registered_agents()
    result = []
    for name, data in agents_data.items():
        result.append(
            AdminAgentInfo(
                name=name,
                role=data["role"],
                capabilities=data["capabilities"],
                invocations=data["invocations"],
                health_status="HEALTHY",
            )
        )
    return result


@router.get("/reviews/pending")
def get_admin_pending_reviews(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Administrative oversight of pending Human-in-the-Loop review tasks."""
    tasks = db.query(ReviewTask).filter(ReviewTask.status == "PENDING").order_by(ReviewTask.created_at.desc()).limit(limit).all()
    return [
        {
            "id": t.id,
            "finding_id": t.finding_id,
            "status": t.status,
            "assigned_to": t.assigned_to,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]


@router.post("/reviews/{task_id}/override")
def admin_review_override(
    task_id: str,
    payload: AdminOverrideRequest,
    db: Session = Depends(get_db),
):
    """Permits compliance administrators to override or sign off on flagged loan analyses."""
    task = db.query(ReviewTask).filter(ReviewTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Review task {task_id} not found.")

    task.status = "COMPLETED"
    db.commit()

    # Record administrative audit trail event
    audit_evt = AuditEvent(
        event_type="ADMIN_OVERRIDE",
        actor_id=payload.admin_username,
        resource_type="ReviewTask",
        resource_id=task_id,
        details={
            "previous_status": "PENDING",
            "new_decision": payload.decision,
            "justification": payload.admin_notes,
        },
    )
    db.add(audit_evt)
    db.commit()

    return {
        "status": "SUCCESS",
        "message": f"Review task {task_id} administratively overridden to {payload.decision}",
        "task_id": task_id,
        "decision": payload.decision,
    }


@router.post("/cache/clear")
def clear_optimizer_cache():
    """Flushes prompt and reasoning cache to ensure fresh LLM evaluations."""
    previous_entries = len(optimizer._cache)
    optimizer._cache.clear()
    return {
        "status": "SUCCESS",
        "message": f"Cleared {previous_entries} cached reasoning entries.",
        "cache_size_now": 0,
    }


@router.get("/audit-trail")
def get_audit_trail(
    limit: int = Query(default=30, ge=1, le=100),
    agent_filter: Optional[str] = Query(default=None),
):
    """Streams recent structured tool and agent execution audit entries from logs/audit_log.jsonl."""
    log_file = ROOT_DIR / "logs" / "audit_log.jsonl"
    if not log_file.exists():
        return {"total_events": 0, "events": []}

    events = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if agent_filter and agent_filter.lower() not in str(data.get("tool_name", "")).lower():
                    continue
                events.append(data)
            except json.JSONDecodeError:
                continue

    # Return latest events first
    recent = list(reversed(events))[:limit]
    return {
        "total_events_in_log": len(events),
        "returned_events": len(recent),
        "events": recent,
    }
