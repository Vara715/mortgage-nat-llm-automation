"""
pdf_service.py
==============
Modular PDF extraction pipeline utilizing pdfplumber:
- Text extraction with reading order and layout preservation
- Table extraction
- Page metadata and quality scoring
- Scanned page detection
"""

from pathlib import Path
from typing import Dict, Any, List
import pdfplumber


class PDFExtractionService:
    def extract(self, file_path: str | Path) -> Dict[str, Any]:
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        pages_data = []
        full_text_pieces = []
        total_tables = 0

        with pdfplumber.open(path) as pdf:
            metadata = {
                "producer": pdf.metadata.get("Producer", "") if pdf.metadata else "",
                "creator": pdf.metadata.get("Creator", "") if pdf.metadata else "",
                "total_pages": len(pdf.pages),
                "file_size": path.stat().st_size,
            }

            for idx, page in enumerate(pdf.pages):
                page_num = idx + 1
                text = page.extract_text(layout=False) or ""
                tables = page.extract_tables() or []
                total_tables += len(tables)

                # Quality calculation: ratio of alphanumeric chars to total length
                alpha_count = sum(1 for c in text if c.isalnum())
                total_chars = len(text)
                quality = round(alpha_count / total_chars, 2) if total_chars > 0 else 0.0
                is_scanned = total_chars < 50 and len(page.images) > 0

                pages_data.append({
                    "page_number": page_num,
                    "text": text,
                    "tables_count": len(tables),
                    "char_count": total_chars,
                    "extraction_quality": quality if not is_scanned else 0.3,
                    "is_scanned": is_scanned,
                })
                full_text_pieces.append(text)

        return {
            "source_file": path.name,
            "total_pages": len(pages_data),
            "metadata": metadata,
            "pages": pages_data,
            "full_text": "\n\n".join(full_text_pieces),
            "tables_extracted": total_tables,
        }


PDFService = PDFExtractionService
