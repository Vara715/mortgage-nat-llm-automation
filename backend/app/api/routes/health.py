"""
health.py
=========
System health, database connectivity, and readiness probes.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from backend.app.db.session import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check(db: Session = Depends(get_db)):
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "service": "morgage-loan-automation",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "jurisdictions_supported": ["US (CFPB)", "IN (RBI)"],
    }


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes / Docker readiness probe."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "service": "morgage-loan-automation",
            "ready": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "not_ready",
            "service": "morgage-loan-automation",
            "ready": False,
            "error": str(e),
        }
