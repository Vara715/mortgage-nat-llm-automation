"""
retrieval.py
============
REST API endpoints for hybrid semantic and lexical retrieval (Section 9 & 13).
Supports filtering by dataset, source, jurisdiction, and category.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.db.session import get_db
from backend.app.services.retrieval.hybrid_search import HybridSearchService

router = APIRouter(prefix="/retrieval", tags=["Retrieval & Search"])


class RetrievalSearchRequest(BaseModel):
    query: str
    jurisdiction: str = "US"
    dataset_id: Optional[str] = None
    category: Optional[str] = None
    top_k: int = 5


@router.post("/search")
def search_hybrid(
    request: RetrievalSearchRequest,
    db: Session = Depends(get_db),
):
    """
    Execute hybrid BM25 lexical + dense vector search over indexed regulatory
    and document chunks. Returns source text, citations, and confidence scores.
    """
    search_service = HybridSearchService(db)
    results = search_service.search(
        query=request.query,
        jurisdiction=request.jurisdiction.upper(),
        category=request.category,
        dataset_id=request.dataset_id,
        top_k=request.top_k,
    )
    return {
        "query": request.query,
        "jurisdiction": request.jurisdiction.upper(),
        "dataset_id": request.dataset_id,
        "total_results": len(results),
        "results": results,
    }
