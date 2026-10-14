"""
qa.py
=====
REST API endpoints for structured Question-Answer generation and retrieval (Section 6).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.db.session import get_db
from backend.app.models.entities import GeneratedQA, DocumentChunk
from backend.app.services.qa.qa_generator import QAGenerator, QAItem

router = APIRouter(prefix="/qa", tags=["Structured Q&A"])


class QAGenerateRequest(BaseModel):
    chunk_id: Optional[str] = None
    dataset_id: Optional[str] = None
    limit: int = 5


@router.post("/generate", response_model=List[QAItem])
def generate_qa_pairs(
    request: QAGenerateRequest,
    db: Session = Depends(get_db),
):
    """
    Generate structured Q&A pairs grounded in regulatory text chunks.
    Validates output schema and links back to exact page and chunk citations.
    """
    generator = QAGenerator(db=db)
    generated_items: List[QAItem] = []

    if request.chunk_id:
        chunk = db.query(DocumentChunk).filter(DocumentChunk.id == request.chunk_id).first()
        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk not found")
        generated_items.extend(generator.generate_from_chunk(chunk, dataset_id=request.dataset_id))
    else:
        q = db.query(DocumentChunk)
        if request.dataset_id:
            q = q.filter(DocumentChunk.dataset_id == request.dataset_id)
        chunks = q.limit(request.limit).all()
        for c in chunks:
            items = generator.generate_from_chunk(c, dataset_id=request.dataset_id)
            generated_items.extend(items)

    return generated_items


@router.get("", response_model=List[QAItem])
def list_qa_pairs(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
    validation_status: Optional[str] = Query(None, description="'machine_generated' or 'verified'"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List stored structured Q&A pairs with source citations and page provenance."""
    q = db.query(GeneratedQA)
    if dataset_id:
        q = q.filter(GeneratedQA.dataset_id == dataset_id)
    if validation_status:
        q = q.filter(GeneratedQA.validation_status == validation_status)

    records = q.order_by(GeneratedQA.generation_timestamp.desc()).limit(limit).all()

    return [
        QAItem(
            question=r.question,
            answer=r.answer,
            dataset_id=r.dataset_id,
            source_document=r.source_document,
            section_identifier=r.section_identifier,
            page_number=r.page_number,
            chunk_id=r.chunk_id,
            citation=r.citation,
            generation_model=r.generation_model,
            generation_timestamp=r.generation_timestamp.isoformat() if r.generation_timestamp else "",
            validation_status=r.validation_status,
        )
        for r in records
    ]
