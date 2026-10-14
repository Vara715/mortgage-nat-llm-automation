"""
source.py
=========
Pydantic schemas for regulatory sources and ingestion jobs.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class SourceRegistryItem(BaseModel):
    source_id: str
    source_name: str
    source_url: str
    source_type: str
    jurisdiction: str
    issuing_authority: str
    publication_date: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    checksum: str
    document_version: Optional[str] = None
    license_or_usage_notes: Optional[str] = None
    ingestion_status: str
    extraction_quality: float = 1.0
    error_message: Optional[str] = None


class IngestionJobResponse(BaseModel):
    id: str
    source_id: str
    status: str
    total_chunks: int
    extracted_pages: int
    progress_percent: float
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_details: Optional[str] = None


class RegulatoryChunkResponse(BaseModel):
    id: str
    source_id: str
    document_title: str
    page_number: int
    section_code: str
    text: str
    category: str
    jurisdiction: str
    relevance_score: Optional[float] = None
    citation: Optional[str] = None
