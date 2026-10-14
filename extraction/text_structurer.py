"""
text_structurer.py
==================
Implements Text Cleaning & Structuring from Slide 7 & Slide 3:
- Remove headers / footers / repeated artifacts / boilerplate
- Maintain section hierarchy (e.g. "Section 3.2 – Terms and Conditions", "Para 2.1 – Statutory Restrictions")
- Split into chunks within 500–1000 tokens (or ~300–600 words)
- Record Chunking Reasoning for each chunk
"""

import re
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

from extraction.pdf_extractor import ExtractedDocument, ExtractedPage


class DocumentChunk(BaseModel):
    chunk_id: str
    source_file: str
    page_number: int
    section_id: str
    section_title: str
    text: str
    token_count_approx: int
    category: str
    chunking_reasoning: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TextStructurer:
    """
    Cleans extracted text, recognizes regulatory section structures,
    and segments into 500-1000 token chunks with traceability metadata.
    """

    def __init__(
        self,
        min_tokens: int = 150,
        target_tokens: int = 600,
        max_tokens: int = 1000,
    ):
        self.min_tokens = min_tokens
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens

    # Regex patterns for section headings commonly found in RBI & loan agreements
    SECTION_PATTERNS = [
        re.compile(r"^(?:Section|Para(?:graph)?|Clause)\s+([0-9]+(?:\.[0-9]+)*)[:\.\-\s]+(.*)$", re.IGNORECASE),
        re.compile(r"^([0-9]+\.[0-9]+(?:\.[0-9]+)*)\s+([A-Z].*)$"),
        re.compile(r"^(ANNEXURE|SCHEDULE)\s+([A-Z0-9]+)[:\.\-\s]*(.*)$", re.IGNORECASE),
        re.compile(r"^([A-Z][A-Za-z\s]{3,35})\s*:\s*$"),
    ]

    # Regex for common headers/footers to strip
    HEADER_FOOTER_PATTERNS = [
        re.compile(r"^\s*Page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
        re.compile(r"^\s*-\s*\d+\s*-\s*$"),
        re.compile(r"^\s*RBI/\d{4}-\d{2}/\d+\s*$", re.IGNORECASE),
        re.compile(r"^\s*Confidential\s*$", re.IGNORECASE),
        re.compile(r"^\s*\d{1,2}\s*$"),  # Lone page numbers
    ]

    def clean_page_text(self, raw_text: str) -> str:
        """Removes headers, footers, trailing noise, and normalizes whitespaces."""
        if not raw_text:
            return ""

        lines = raw_text.splitlines()
        clean_lines = []

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue

            # Check if line matches header/footer noise
            is_noise = False
            for pat in self.HEADER_FOOTER_PATTERNS:
                if pat.match(line_str):
                    is_noise = True
                    break

            if not is_noise:
                clean_lines.append(line_str)

        return "\n".join(clean_lines)

    def detect_category(self, text: str) -> str:
        """
        Categorizes chunks into regulatory categories specified in Slide 10:
        Eligibility, Loan Terms, Regulatory Penalties, Prepayment/Foreclosure,
        LTV & Margins, NRI Financing, Definitions, Fair Practices.
        """
        text_lower = text.lower()
        if any(w in text_lower for w in ["prepayment", "pre-payment", "foreclosure", "fore-closure"]):
            return "Prepayment & Foreclosure"
        elif any(w in text_lower for w in ["penal charge", "penal interest", "penalty", "default charge", "overdue"]):
            return "Regulatory Penalties"
        elif any(w in text_lower for w in ["non-resident", "nri", "housing intermediary"]):
            return "NRI Financing"
        elif any(w in text_lower for w in ["ltv", "loan-to-value", "margin", "quantum of loan"]):
            return "LTV & Margin Norms"
        elif any(w in text_lower for w in ["eligible", "eligibility", "cibil", "income", "foir", "applicant"]):
            return "Eligibility"
        elif any(w in text_lower for w in ["definition", "means", "shall have the meaning"]):
            return "Definitions"
        elif any(w in text_lower for w in ["fair practice", "kfs", "key facts", "recovery agent", "grievance"]):
            return "Fair Practices Code"
        elif any(w in text_lower for w in ["interest rate", "tenure", "instalment", "repayment", "facility"]):
            return "Loan Terms"
        else:
            return "Regulatory Guidelines"

    def estimate_tokens(self, text: str) -> int:
        """Rough token count approximation: 1 token ~= 0.75 words."""
        words = len(text.split())
        return int(words * 1.33)

    def structure_and_chunk(self, doc: ExtractedDocument) -> List[DocumentChunk]:
        """
        Processes ExtractedDocument into structured chunks maintaining sections,
        within 500-1000 tokens budget, and recording chunking reasoning.
        """
        all_chunks: List[DocumentChunk] = []
        current_section_id = "General"
        current_section_title = "Overview"

        for page in doc.pages:
            cleaned_text = self.clean_page_text(page.text)
            if not cleaned_text:
                continue

            # Split into paragraphs while tracking section headers
            raw_paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
            
            # If paragraphs didn't split (single newline formatting), split by double lines or section starts
            if len(raw_paragraphs) <= 1:
                lines = cleaned_text.splitlines()
                buffer: List[str] = []
                paras: List[str] = []
                for l in lines:
                    is_sec = any(p.match(l) for p in self.SECTION_PATTERNS)
                    if is_sec and buffer:
                        paras.append(" ".join(buffer))
                        buffer = [l]
                    else:
                        buffer.append(l)
                if buffer:
                    paras.append(" ".join(buffer))
                raw_paragraphs = paras

            current_chunk_paragraphs: List[str] = []
            current_tokens = 0
            page_chunk_idx = 0

            for para in raw_paragraphs:
                # Detect section header
                for pat in self.SECTION_PATTERNS:
                    m = pat.match(para.splitlines()[0] if "\n" in para else para)
                    if m:
                        current_section_id = m.group(1).strip()
                        current_section_title = m.group(2).strip() if len(m.groups()) > 1 else current_section_id
                        break

                para_tokens = self.estimate_tokens(para)

                # Check if adding this paragraph exceeds maximum token limit (Slide 7: 500-1000 tokens)
                if current_tokens + para_tokens > self.max_tokens and current_tokens >= self.min_tokens:
                    chunk_text = "\n\n".join(current_chunk_paragraphs)
                    chunk_id = f"{page.page_number}_{page_chunk_idx}"
                    category = self.detect_category(chunk_text)
                    reasoning = (
                        f"Boundary formed at {current_tokens} tokens to prevent token overflow. "
                        f"Maintained section '{current_section_id}: {current_section_title}' context."
                    )

                    all_chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            source_file=doc.source_file,
                            page_number=page.page_number,
                            section_id=current_section_id,
                            section_title=current_section_title,
                            text=chunk_text,
                            token_count_approx=current_tokens,
                            category=category,
                            chunking_reasoning=reasoning,
                            metadata={
                                "tables_on_page": len(page.tables),
                                "images_on_page": len(page.images),
                            },
                        )
                    )
                    page_chunk_idx += 1
                    current_chunk_paragraphs = [para]
                    current_tokens = para_tokens
                else:
                    current_chunk_paragraphs.append(para)
                    current_tokens += para_tokens

            # Flush remaining paragraphs on the page
            if current_chunk_paragraphs:
                chunk_text = "\n\n".join(current_chunk_paragraphs)
                chunk_id = f"{page.page_number}_{page_chunk_idx}"
                category = self.detect_category(chunk_text)
                reasoning = (
                    f"Final chunk of page {page.page_number} ({current_tokens} tokens). "
                    f"Section: '{current_section_id}: {current_section_title}'."
                )

                all_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        source_file=doc.source_file,
                        page_number=page.page_number,
                        section_id=current_section_id,
                        section_title=current_section_title,
                        text=chunk_text,
                        token_count_approx=current_tokens,
                        category=category,
                        chunking_reasoning=reasoning,
                        metadata={
                            "tables_on_page": len(page.tables),
                            "images_on_page": len(page.images),
                        },
                    )
                )

        return all_chunks
