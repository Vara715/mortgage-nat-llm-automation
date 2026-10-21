"""
pdf_extractor.py
================
Implements the PDF EXTRACTION pipeline from Slide 3 of the TCS Mortgage Loan architecture:
- Read PDF with pdfplumber (with pypdf fallback)
- Parallel/structured extraction of:
    * Text (preserving reading order and layout)
    * Tables (table grid extraction)
    * Images (image counts, bounding boxes, stream metadata)
    * Metadata (producer, creation date, page count, dimensions)
    * Visual Debugging info (layout blocks, bbox coordinates, density metrics)
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import re
from pydantic import BaseModel, Field

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import pytesseract
    from PIL import Image
    HAS_PYTESSERACT = True
except ImportError:
    HAS_PYTESSERACT = False


class VisualDebugInfo(BaseModel):
    page_number: int
    char_count: int
    word_count: int
    table_count: int
    image_count: int
    layout_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    has_text: bool = True
    page_dimensions: Dict[str, float] = Field(default_factory=dict)
    ocr_applied: bool = False
    extraction_quality_score: float = 1.0  # 0.0 to 1.0
    quality_assessment: str = "HIGH"  # 'HIGH', 'ACCEPTABLE', 'DEGRADED_SCANNED'
    requires_human_verification: bool = False
    ocr_notes: Optional[str] = None


class ExtractedTable(BaseModel):
    page_number: int
    table_index: int
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    raw_table: List[List[Optional[str]]] = Field(default_factory=list)


class ExtractedImageMeta(BaseModel):
    page_number: int
    image_index: int
    x0: Optional[float] = None
    top: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class ExtractedPage(BaseModel):
    page_number: int
    text: str
    tables: List[ExtractedTable] = Field(default_factory=list)
    images: List[ExtractedImageMeta] = Field(default_factory=list)
    visual_debug: VisualDebugInfo

    @property
    def ocr_applied(self) -> bool:
        return self.visual_debug.ocr_applied

    @property
    def extraction_quality_score(self) -> float:
        return self.visual_debug.extraction_quality_score


class ExtractedDocument(BaseModel):
    source_file: str
    total_pages: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    pages: List[ExtractedPage] = Field(default_factory=list)
    overall_quality_score: float = 1.0
    overall_quality_status: str = "HIGH"  # 'HIGH', 'ACCEPTABLE', 'DEGRADED'
    scanned_pages_count: int = 0
    requires_hitl_review: bool = False

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)


class PDFExtractor:
    """
    High-performance PDF extractor utilizing pdfplumber with full metadata,
    table, image, and visual debugging support as defined in Slide 3.
    """

    def __init__(self, enable_visual_debugging: bool = True):
        self.enable_visual_debugging = enable_visual_debugging

    def extract(self, file_path: str | Path) -> ExtractedDocument:
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, "rb") as f:
            magic = f.read(5)
            if not magic.startswith(b"%PDF"):
                raise ValueError(f"{path.name} is not a valid PDF file (starts with {magic})")

        if HAS_PDFPLUMBER:
            return self._extract_with_pdfplumber(path)
        elif HAS_PYPDF:
            return self._extract_with_pypdf(path)
        else:
            raise RuntimeError("Neither pdfplumber nor pypdf is installed.")

    def _assess_page_quality(self, text: str, image_count: int, ocr_applied: bool) -> tuple[float, str, bool]:
        clean_text = text.strip()
        char_count = len(clean_text)
        words = clean_text.split()
        word_count = len(words)

        # Baseline text assessment
        if char_count >= 200 and word_count >= 30:
            return 1.0, "HIGH", False
        elif char_count >= 80:
            return 0.85, "ACCEPTABLE", False
        elif ocr_applied and char_count >= 50:
            return 0.80, "ACCEPTABLE", False
        elif image_count > 0 and char_count < 80:
            # Scanned or image-heavy page with insufficient digital text
            return 0.35, "DEGRADED_SCANNED", True
        elif char_count == 0:
            return 0.10, "DEGRADED_EMPTY", True
        else:
            return 0.60, "ACCEPTABLE", False

    def _extract_with_pdfplumber(self, path: Path) -> ExtractedDocument:
        pages: List[ExtractedPage] = []
        doc_metadata: Dict[str, Any] = {}

        with pdfplumber.open(path) as pdf:
            doc_metadata = {
                "producer": pdf.metadata.get("Producer", "") if pdf.metadata else "",
                "creator": pdf.metadata.get("Creator", "") if pdf.metadata else "",
                "creation_date": pdf.metadata.get("CreationDate", "") if pdf.metadata else "",
                "total_pages": len(pdf.pages),
                "file_size_bytes": path.stat().st_size,
            }

            scanned_pages = 0

            for p_idx, page in enumerate(pdf.pages):
                page_num = p_idx + 1

                # 1. Extract text
                page_text = page.extract_text(layout=False) or ""

                # 2. Extract tables
                extracted_tables: List[ExtractedTable] = []
                raw_tables = page.extract_tables() or []
                for t_idx, raw_t in enumerate(raw_tables):
                    if not raw_t:
                        continue
                    clean_rows = []
                    for row in raw_t:
                        clean_rows.append([str(c or "").strip() for c in row])
                    headers = clean_rows[0] if clean_rows else []
                    data_rows = clean_rows[1:] if len(clean_rows) > 1 else []
                    extracted_tables.append(
                        ExtractedTable(
                            page_number=page_num,
                            table_index=t_idx,
                            headers=headers,
                            rows=data_rows,
                            raw_table=raw_t,
                        )
                    )

                # 3. Extract images metadata
                extracted_images: List[ExtractedImageMeta] = []
                for i_idx, img in enumerate(page.images):
                    extracted_images.append(
                        ExtractedImageMeta(
                            page_number=page_num,
                            image_index=i_idx,
                            x0=float(img.get("x0", 0.0)),
                            top=float(img.get("top", 0.0)),
                            width=float(img.get("width", 0.0)),
                            height=float(img.get("height", 0.0)),
                        )
                    )

                # 4. OCR Fallback for low-density / scanned pages (Slide 9 Limitation)
                ocr_applied = False
                ocr_notes = None
                if len(page_text.strip()) < 80 and len(extracted_images) > 0:
                    if HAS_PYTESSERACT:
                        try:
                            # Render page image for OCR
                            p_img = page.to_image(resolution=200).original
                            ocr_text = pytesseract.image_to_string(p_img)
                            if ocr_text and len(ocr_text.strip()) > len(page_text.strip()):
                                page_text = ocr_text
                                ocr_applied = True
                                ocr_notes = "OCR successfully extracted scanned text."
                        except Exception as e:
                            ocr_notes = f"OCR fallback attempted but failed: {e}"
                    else:
                        ocr_notes = "Scanned/image content detected; pytesseract unavailable."

                quality_score, quality_assessment, req_hitl = self._assess_page_quality(
                    page_text, len(extracted_images), ocr_applied
                )
                if req_hitl:
                    scanned_pages += 1

                # 5. Visual Debugging info (Slide 3)
                layout_blocks = []
                if self.enable_visual_debugging:
                    words = page.extract_words()
                    for w in words[:15]:
                        layout_blocks.append({
                            "text": w.get("text"),
                            "x0": round(float(w.get("x0", 0)), 1),
                            "top": round(float(w.get("top", 0)), 1),
                            "bottom": round(float(w.get("bottom", 0)), 1),
                        })

                v_debug = VisualDebugInfo(
                    page_number=page_num,
                    char_count=len(page_text),
                    word_count=len(page_text.split()),
                    table_count=len(extracted_tables),
                    image_count=len(extracted_images),
                    layout_blocks=layout_blocks,
                    has_text=bool(page_text.strip()),
                    page_dimensions={"width": float(page.width), "height": float(page.height)},
                    ocr_applied=ocr_applied,
                    extraction_quality_score=quality_score,
                    quality_assessment=quality_assessment,
                    requires_human_verification=req_hitl,
                    ocr_notes=ocr_notes,
                )

                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text=page_text,
                        tables=extracted_tables,
                        images=extracted_images,
                        visual_debug=v_debug,
                    )
                )

        avg_score = round(sum(p.extraction_quality_score for p in pages) / max(len(pages), 1), 3)
        overall_status = "HIGH" if avg_score >= 0.85 else ("ACCEPTABLE" if avg_score >= 0.65 else "DEGRADED")
        requires_hitl = overall_status == "DEGRADED" or scanned_pages > 0

        return ExtractedDocument(
            source_file=path.name,
            total_pages=len(pages),
            metadata=doc_metadata,
            pages=pages,
            overall_quality_score=avg_score,
            overall_quality_status=overall_status,
            scanned_pages_count=scanned_pages,
            requires_hitl_review=requires_hitl,
        )

    def _extract_with_pypdf(self, path: Path) -> ExtractedDocument:
        pages: List[ExtractedPage] = []
        reader = pypdf.PdfReader(str(path))
        doc_metadata = {
            "total_pages": len(reader.pages),
            "file_size_bytes": path.stat().st_size,
        }

        scanned_pages = 0
        for p_idx, page in enumerate(reader.pages):
            page_num = p_idx + 1
            txt = page.extract_text() or ""
            q_score, q_status, req_hitl = self._assess_page_quality(txt, len(page.images), False)
            if req_hitl:
                scanned_pages += 1
            v_debug = VisualDebugInfo(
                page_number=page_num,
                char_count=len(txt),
                word_count=len(txt.split()),
                table_count=0,
                image_count=len(page.images),
                has_text=bool(txt.strip()),
                extraction_quality_score=q_score,
                quality_assessment=q_status,
                requires_human_verification=req_hitl,
            )
            pages.append(
                ExtractedPage(
                    page_number=page_num,
                    text=txt,
                    tables=[],
                    images=[],
                    visual_debug=v_debug,
                )
            )

        avg_score = round(sum(p.extraction_quality_score for p in pages) / max(len(pages), 1), 3)
        overall_status = "HIGH" if avg_score >= 0.85 else ("ACCEPTABLE" if avg_score >= 0.65 else "DEGRADED")
        requires_hitl = overall_status == "DEGRADED" or scanned_pages > 0

        return ExtractedDocument(
            source_file=path.name,
            total_pages=len(pages),
            metadata=doc_metadata,
            pages=pages,
            overall_quality_score=avg_score,
            overall_quality_status=overall_status,
            scanned_pages_count=scanned_pages,
            requires_hitl_review=requires_hitl,
        )
