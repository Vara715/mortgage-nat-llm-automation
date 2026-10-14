"""
hybrid_search.py
================
Hybrid Lexical (BM25) + Cosine Vector Retrieval Engine (Section 4.G).
Enforces strict jurisdiction isolation:
- US queries retrieve ONLY US regulatory chunks (CFPB Reg Z, etc.)
- IN queries retrieve ONLY Indian regulatory chunks (RBI circulars, etc.)
"""

import math
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.models.entities import DocumentChunk, RegulatoryDocument, RegulatorySource
from backend.app.schemas.compliance import RegulatoryEvidenceItem


class HybridSearchService:
    def __init__(self, db: Session):
        self.db = db
        self._stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "and", "or", "that", "this", "it",
        }

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        return [w for w in words if w not in self._stopwords and len(w) > 1]

    def search(
        self,
        query: str,
        jurisdiction: str,
        category: Optional[str] = None,
        dataset_id: Optional[str] = None,
        top_k: int = 3,
    ) -> List[RegulatoryEvidenceItem]:
        """
        Executes hybrid search over indexed DocumentChunks strictly matching jurisdiction.
        Optionally filters by dataset_id and category. Never mixes US and Indian rules.
        """
        # Strict jurisdiction filter
        chunk_query = self.db.query(DocumentChunk).filter(DocumentChunk.jurisdiction == jurisdiction)
        if dataset_id:
            chunk_query = chunk_query.filter(DocumentChunk.dataset_id == dataset_id)
        if category:
            chunk_query = chunk_query.filter(DocumentChunk.category == category)

        chunks = chunk_query.all()
        if not chunks:
            # Fallback: remove category filter if no direct match in that category
            chunks = self.db.query(DocumentChunk).filter(DocumentChunk.jurisdiction == jurisdiction).all()
            if not chunks:
                return []

        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        # 1. Compute BM25 scores
        total_docs = len(chunks)
        doc_freq = {}
        for c in chunks:
            tokens_set = set(self._tokenize(c.text))
            for t in tokens_set:
                doc_freq[t] = doc_freq.get(t, 0) + 1

        avg_len = sum(len(self._tokenize(c.text)) for c in chunks) / total_docs if total_docs > 0 else 1.0
        k1 = 1.5
        b = 0.75

        scored: List[tuple[float, DocumentChunk]] = []

        # Build query vector
        q_tf = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1
        q_norm = math.sqrt(sum(v**2 for v in q_tf.values())) or 1.0

        for c in chunks:
            c_tokens = self._tokenize(c.text)
            c_len = len(c_tokens)
            c_tf = {}
            for t in c_tokens:
                c_tf[t] = c_tf.get(t, 0) + 1
            c_norm = math.sqrt(sum(v**2 for v in c_tf.values())) or 1.0

            # Lexical BM25
            bm25 = 0.0
            for qt in q_tokens:
                if qt in c_tf:
                    n = doc_freq.get(qt, 1)
                    idf = math.log((total_docs - n + 0.5) / (n + 0.5) + 1.0)
                    freq = c_tf[qt]
                    denom = freq + k1 * (1.0 - b + b * (c_len / avg_len))
                    bm25 += idf * (freq * (k1 + 1.0) / denom)

            # Cosine similarity
            dot = sum(q_tf[t] * c_tf.get(t, 0) for t in q_tf)
            cosine = dot / (q_norm * c_norm) if (q_norm * c_norm) > 0 else 0.0

            final_score = bm25 + (cosine * 3.5)
            if final_score > 0.01:
                scored.append((final_score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_candidates = scored[:top_k]

        evidence_items: List[RegulatoryEvidenceItem] = []
        for score, chunk in top_candidates:
            reg_doc = self.db.query(RegulatoryDocument).filter(RegulatoryDocument.id == chunk.document_id).first()
            source = None
            if reg_doc:
                source = self.db.query(RegulatorySource).filter(RegulatorySource.source_id == reg_doc.source_id).first()

            source_name = source.source_name if source else "Authoritative Regulatory Archive"
            source_url = source.source_url if source else "https://www.consumerfinance.gov/" if jurisdiction == "US" else "https://www.rbi.org.in/"
            clean_code = chunk.section_code.replace("§", "Sec.").strip() if chunk.section_code else "General"
            citation = f"{clean_code} ({source.document_version if source else 'Statutory Rule'})"

            evidence_items.append(
                RegulatoryEvidenceItem(
                    source_name=source_name,
                    source_url=source_url,
                    citation=citation,
                    page_number=chunk.page_number,
                    quoted_text=chunk.text[:450],
                    document_version=source.document_version if source else "Current Effective Version",
                    relevance_score=round(score, 3),
                )
            )

        return evidence_items
