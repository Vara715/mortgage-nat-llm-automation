"""
datasets.py
===========
REST API endpoints for dataset-agnostic management and ingestion.
Allows users to register, list, and ingest custom datasets via manifests.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
import json

from backend.app.db.session import get_db
from backend.app.schemas.dataset import DatasetManifest, DatasetResponse, ProcessingJobResponse
from backend.app.models.entities import Dataset, ProcessingJob, utc_now
from backend.app.services.ingestion.manifest_loader import DatasetIngestionEngine

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post("", response_model=DatasetResponse, status_code=201)
def register_dataset(manifest: DatasetManifest, db: Session = Depends(get_db)):
    """Register a new dataset manifest into the platform."""
    existing = db.query(Dataset).filter(Dataset.id == manifest.dataset_id).first()
    if existing:
        existing.name = manifest.dataset_name
        existing.description = manifest.description
        existing.source_location = manifest.source_location
        existing.manifest_config = json.dumps(manifest.model_dump(), default=str)
        db.commit()
        db.refresh(existing)
        return existing

    ds = Dataset(
        id=manifest.dataset_id,
        name=manifest.dataset_name,
        description=manifest.description,
        source_type=manifest.source_type,
        source_location=manifest.source_location,
        file_format=manifest.file_format,
        jurisdiction=manifest.jurisdiction,
        version=manifest.version,
        manifest_config=json.dumps(manifest.model_dump(), default=str),
        status="ACTIVE",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


@router.get("", response_model=List[DatasetResponse])
def list_datasets(
    jurisdiction: Optional[str] = Query(None, description="'US' or 'IN'"),
    db: Session = Depends(get_db),
):
    """List all registered datasets with optional jurisdiction filter."""
    q = db.query(Dataset)
    if jurisdiction:
        q = q.filter(Dataset.jurisdiction == jurisdiction)
    return q.all()


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a specific registered dataset."""
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return ds


@router.post("/{dataset_id}/ingest")
def trigger_dataset_ingestion(
    dataset_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger ingestion for a dataset.
    Creates an asynchronous processing job and returns the job ID immediately.
    """
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")

    engine = DatasetIngestionEngine(db)
    job = engine.create_job("INGESTION", dataset_id)

    # Ingest directly or in background
    manifest_data = json.loads(ds.manifest_config) if ds.manifest_config else {
        "dataset_id": ds.id,
        "dataset_name": ds.name,
        "source_type": ds.source_type,
        "source_location": ds.source_location,
        "file_format": ds.file_format,
        "jurisdiction": ds.jurisdiction,
        "version": ds.version,
    }
    manifest = DatasetManifest(**manifest_data)

    try:
        result = engine.ingest_manifest(manifest, job_id=job.id)
        return {
            "status": "COMPLETED",
            "job_id": job.id,
            "dataset_id": dataset_id,
            "details": result,
        }
    except Exception as e:
        db.rollback()
        return {
            "status": "FAILED",
            "job_id": job.id,
            "dataset_id": dataset_id,
            "error": str(e),
        }


@router.get("/{dataset_id}/jobs", response_model=List[ProcessingJobResponse])
def get_dataset_jobs(dataset_id: str, db: Session = Depends(get_db)):
    """List all ingestion and processing jobs for a dataset."""
    jobs = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.target_id == dataset_id)
        .order_by(ProcessingJob.started_at.desc())
        .all()
    )
    return jobs
