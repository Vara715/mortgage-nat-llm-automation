"""
test_retrieval.py
=================
Tests for Hybrid Lexical (BM25) + Cosine Vector Retrieval and strict jurisdiction isolation.
"""

from backend.app.db.session import SessionLocal
from backend.app.services.retrieval.hybrid_search import HybridSearchService


def test_hybrid_search_jurisdiction_isolation():
    db = SessionLocal()
    try:
        searcher = HybridSearchService(db)

        # 1. US query should ONLY return US regulatory documents (e.g. 12 CFR Part 1026)
        us_results = searcher.search(
            query="prepayment penalty qualified mortgage points fees",
            jurisdiction="US",
            top_k=3,
        )
        assert len(us_results) > 0
        for item in us_results:
            assert "1026" in item.citation or "CFPB" in item.source_name or "Regulation Z" in item.source_name
            assert "RBI" not in item.source_name

        # 2. Indian query should ONLY return Indian regulatory documents (e.g. RBI circulars, Indian banking agreements)
        in_results = searcher.search(
            query="foreclosure charges floating rate housing loans individual borrower",
            jurisdiction="IN",
            top_k=3,
        )
        assert len(in_results) > 0
        for item in in_results:
            assert any(term in item.source_name.lower() or term in item.citation.lower() for term in ["rbi", "reserve bank", "india", "term loan", "circular", "housing"])
            assert "12 CFR" not in item.citation
    finally:
        db.close()
