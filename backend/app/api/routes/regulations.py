"""
regulations.py
==============
API endpoints for searching regulatory clauses, inspecting chunks, and citation lookup.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.models.entities import DocumentChunk, RegulatoryDocument, RegulatorySource
from backend.app.schemas.source import RegulatoryChunkResponse
from backend.app.services.retrieval.hybrid_search import HybridSearchService

router = APIRouter(prefix="/regulations", tags=["Regulations"])


@router.get("/search")
def search_regulations(
    query: str = Query(..., description="Query keywords or clause phrase"),
    jurisdiction: str = Query("US", description="'US' or 'IN'"),
    category: Optional[str] = Query(None, description="Regulatory category"),
    top_k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    search_service = HybridSearchService(db)
    results = search_service.search(
        query=query,
        jurisdiction=jurisdiction.upper(),
        category=category,
        top_k=top_k,
    )
    return {
        "query": query,
        "jurisdiction": jurisdiction.upper(),
        "total_results": len(results),
        "results": results,
    }


@router.get("/chunks", response_model=List[RegulatoryChunkResponse])
def list_chunks(
    jurisdiction: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(DocumentChunk)
    if jurisdiction:
        q = q.filter(DocumentChunk.jurisdiction == jurisdiction.upper())
    if category:
        q = q.filter(DocumentChunk.category == category)
    chunks = q.limit(limit).all()

    resp = []
    for c in chunks:
        doc = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == c.document_id).first()
        doc_title = doc.title if doc else "Regulatory Section"
        resp.append(
            RegulatoryChunkResponse(
                id=c.id,
                source_id=c.document_id,
                document_title=doc_title,
                page_number=c.page_number,
                section_code=c.section_code or "Unknown Section",
                text=c.text,
                category=c.category,
                jurisdiction=c.jurisdiction,
                citation=c.section_code,
            )
        )
    return resp


@router.get("/chunks/{chunk_id}", response_model=RegulatoryChunkResponse)
def get_chunk(chunk_id: str, db: Session = Depends(get_db)):
    chunk = db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="Regulatory chunk not found")

    doc = db.query(RegulatoryDocument).filter(RegulatoryDocument.id == chunk.document_id).first()
    doc_title = doc.title if doc else "Regulatory Section"

    return RegulatoryChunkResponse(
        id=chunk.id,
        source_id=chunk.document_id,
        document_title=doc_title,
        page_number=chunk.page_number,
        section_code=chunk.section_code or "Unknown Section",
        text=chunk.text,
        category=chunk.category,
        jurisdiction=chunk.jurisdiction,
        citation=chunk.section_code,
    )


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    us_chunks = db.query(DocumentChunk).filter(DocumentChunk.jurisdiction == "US").count()
    in_chunks = db.query(DocumentChunk).filter(DocumentChunk.jurisdiction == "IN").count()
    total_sources = db.query(RegulatorySource).count()
    total_docs = db.query(RegulatoryDocument).count()

    return {
        "total_sources": total_sources,
        "total_documents": total_docs,
        "us_indexed_chunks": us_chunks,
        "in_indexed_chunks": in_chunks,
        "total_chunks": us_chunks + in_chunks,
    }
