"""
sources.py
==========
API endpoints for managing and querying the authentic data source registry.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.entities import RegulatorySource
from backend.app.schemas.source import SourceRegistryItem
from backend.app.services.source_registry.registry import SourceRegistryService

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("", response_model=List[SourceRegistryItem])
def list_sources(jurisdiction: str = None, db: Session = Depends(get_db)):
    query = db.query(RegulatorySource)
    if jurisdiction:
        query = query.filter(RegulatorySource.jurisdiction == jurisdiction.upper())
    sources = query.order_by(RegulatorySource.source_name).all()

    items = []
    for s in sources:
        items.append(
            SourceRegistryItem(
                source_id=s.source_id,
                source_name=s.source_name,
                source_url=s.source_url,
                source_type=s.source_type,
                jurisdiction=s.jurisdiction,
                issuing_authority=s.issuing_authority,
                publication_date=s.publication_date,
                effective_from=s.effective_from,
                effective_until=s.effective_until,
                retrieved_at=s.retrieved_at,
                checksum=s.checksum,
                document_version=s.document_version,
                license_or_usage_notes=s.license_or_usage_notes,
                ingestion_status=s.ingestion_status,
                extraction_quality=s.extraction_quality or 1.0,
                error_message=s.error_message,
            )
        )
    return items


@router.post("/sync")
def sync_sources(db: Session = Depends(get_db)):
    service = SourceRegistryService(db)
    result = service.ingest_regulatory_files()
    return {
        "status": "success",
        "message": "Regulatory source registry and document chunks synchronized.",
        "details": result,
    }
