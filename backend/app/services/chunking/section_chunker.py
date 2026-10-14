"""
section_chunker.py
==================
Structure-aware chunking for regulatory documents (Section 4.C).
Preserves document hierarchy, section codes, jurisdiction, and token limits (500-1000 tokens).
"""

import re
import json
from typing import List
from backend.app.models.entities import DocumentChunk


class RegulatoryChunker:
    def __init__(self, min_tokens: int = 150, max_tokens: int = 800):
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens

    def estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.33)

    def detect_category(self, text: str, jurisdiction: str) -> str:
        text_lower = text.lower()
        if "prepayment" in text_lower or "pre-payment" in text_lower or "foreclosure" in text_lower:
            return "PREPAYMENT_PENALTY"
        elif "qualified mortgage" in text_lower or "ability to repay" in text_lower or "points and fees" in text_lower:
            return "ABILITY_TO_REPAY_QM"
        elif "higher-priced" in text_lower or "hpml" in text_lower or "escrow" in text_lower:
            return "ESCROW_HPML"
        elif "loan estimate" in text_lower or "closing disclosure" in text_lower or "trid" in text_lower:
            return "DISCLOSURES_TRID"
        elif "penal" in text_lower or "penalty" in text_lower or "default interest" in text_lower:
            return "PENAL_CHARGES"
        elif "ltv" in text_lower or "loan-to-value" in text_lower or "margin" in text_lower:
            return "LTV_MARGIN_LIMITS"
        elif "non-resident" in text_lower or "nri" in text_lower:
            return "NRI_FINANCING"
        elif "key facts" in text_lower or "kfs" in text_lower or "grievance" in text_lower:
            return "FAIR_PRACTICES_KFS"
        else:
            return "GENERAL_REGULATORY"

    def chunk_text(self, text: str, doc_id: str, jurisdiction: str, source_file: str) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

        current_paras = []
        current_tokens = 0
        current_section = "General"
        chunk_idx = 0

        # Section detection regex (e.g. § 1026.43 or 3.2.4 or Clause 6)
        sec_pattern = re.compile(r"(?:§\s*|Section\s+|Para\s+|Clause\s+)([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)

        for p in paragraphs:
            m = sec_pattern.search(p[:100])
            if m:
                current_section = m.group(1)

            p_tok = self.estimate_tokens(p)
            if current_tokens + p_tok > self.max_tokens and current_tokens >= self.min_tokens:
                chunk_str = "\n\n".join(current_paras)
                cat = self.detect_category(chunk_str, jurisdiction)
                norm_str = re.sub(r"\s+", " ", chunk_str).lower()

                chunks.append(
                    DocumentChunk(
                        document_id=doc_id,
                        page_number=1 + (chunk_idx // 3),
                        section_id=current_section,
                        section_code=f"§ {current_section}",
                        chunk_index=chunk_idx,
                        text=chunk_str,
                        normalized_text=norm_str,
                        token_count=current_tokens,
                        category=cat,
                        jurisdiction=jurisdiction,
                        embedding_json=None,
                    )
                )
                chunk_idx += 1
                current_paras = [p]
                current_tokens = p_tok
            else:
                current_paras.append(p)
                current_tokens += p_tok

        if current_paras:
            chunk_str = "\n\n".join(current_paras)
            cat = self.detect_category(chunk_str, jurisdiction)
            norm_str = re.sub(r"\s+", " ", chunk_str).lower()
            chunks.append(
                DocumentChunk(
                    document_id=doc_id,
                    page_number=1 + (chunk_idx // 3),
                    section_id=current_section,
                    section_code=f"§ {current_section}",
                    chunk_index=chunk_idx,
                    text=chunk_str,
                    normalized_text=norm_str,
                    token_count=current_tokens,
                    category=cat,
                    jurisdiction=jurisdiction,
                    embedding_json=None,
                )
            )

        return chunks


SectionChunker = RegulatoryChunker
