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


class VisualDebugInfo(BaseModel):
    page_number: int
    char_count: int
    word_count: int
    table_count: int
    image_count: int
    layout_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    has_text: bool = True
    page_dimensions: Dict[str, float] = Field(default_factory=dict)


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


class ExtractedDocument(BaseModel):
    source_file: str
    total_pages: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    pages: List[ExtractedPage] = Field(default_factory=list)

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

                # 4. Visual Debugging info (Slide 3)
                layout_blocks = []
                if self.enable_visual_debugging:
                    # Capture text blocks or layout clusters
                    words = page.extract_words()
                    # Sample up to 10 block anchors for debug inspection without bloat
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

        return ExtractedDocument(
            source_file=path.name,
            total_pages=len(pages),
            metadata=doc_metadata,
            pages=pages,
        )

    def _extract_with_pypdf(self, path: Path) -> ExtractedDocument:
        pages: List[ExtractedPage] = []
        reader = pypdf.PdfReader(str(path))
        doc_metadata = {
            "total_pages": len(reader.pages),
            "file_size_bytes": path.stat().st_size,
        }

        for p_idx, page in enumerate(reader.pages):
            page_num = p_idx + 1
            txt = page.extract_text() or ""
            v_debug = VisualDebugInfo(
                page_number=page_num,
                char_count=len(txt),
                word_count=len(txt.split()),
                table_count=0,
                image_count=len(page.images),
                has_text=bool(txt.strip()),
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

        return ExtractedDocument(
            source_file=path.name,
            total_pages=len(pages),
            metadata=doc_metadata,
            pages=pages,
        )
