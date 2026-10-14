"""
document.py
===========
Pydantic schemas for loan documents and extracted loan fields.
"""

from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel


class ExtractedFieldSchema(BaseModel):
    id: str
    field_name: str
    field_value: Optional[Any] = None
    source_page: int
    source_excerpt: str
    confidence: float
    is_verified: bool
    reviewer_corrected_value: Optional[str] = None


class LoanDocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    jurisdiction: str
    doc_type: str
    status: str
    upload_date: datetime
    extracted_fields: List[ExtractedFieldSchema] = []


class FieldCorrectionRequest(BaseModel):
    corrected_value: str
    comment: Optional[str] = None
