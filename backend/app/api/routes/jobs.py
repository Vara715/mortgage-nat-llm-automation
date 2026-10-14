"""
jobs.py
=======
REST API endpoints for checking background processing and ingestion job status.
Used by n8n polling loops, Celery workers, and external callers.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.dataset import ProcessingJobResponse
from backend.app.models.entities import ProcessingJob

router = APIRouter(prefix="/jobs", tags=["Jobs & Operations"])


@router.get("/{job_id}", response_model=ProcessingJobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Retrieve current execution status and progress for a background job."""
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job
