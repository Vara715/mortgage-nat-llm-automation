"""
documents.py
============
API endpoints for loan document upload, text/table parsing, term extraction,
and human analyst field verification.
"""

import os
import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import validate_safe_filename
from backend.app.db.session import get_db
from backend.app.models.entities import LoanDocument, ExtractedLoanField
from backend.app.schemas.document import LoanDocumentResponse, ExtractedFieldSchema, FieldCorrectionRequest
from backend.app.services.extraction.pdf_service import PDFExtractionService
from backend.app.services.loan_extraction.term_extractor import LoanTermExtractor
from backend.app.services.audit.audit_service import AuditService

router = APIRouter(prefix="/documents", tags=["Loan Documents"])


def _to_response(doc: LoanDocument) -> LoanDocumentResponse:
    fields = []
    for f in doc.extracted_fields:
        val = f.reviewer_corrected_value if f.reviewer_corrected_value is not None else (f.field_value_num if f.field_value_num is not None else f.field_value_str)
        fields.append(
            ExtractedFieldSchema(
                id=f.id,
                field_name=f.field_name,
                field_value=val,
                source_page=f.source_page,
                source_excerpt=f.source_excerpt,
                confidence=f.confidence,
                is_verified=f.is_verified,
                reviewer_corrected_value=f.reviewer_corrected_value,
            )
        )
    return LoanDocumentResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        jurisdiction=doc.jurisdiction,
        doc_type=doc.doc_type,
        status=doc.status,
        upload_date=doc.upload_date,
        extracted_fields=fields,
    )


@router.post("/upload", response_model=LoanDocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    jurisdiction_override: str = Form(None),
    db: Session = Depends(get_db),
):
    safe_name = validate_safe_filename(file.filename)
    upload_dir = settings.DATA_DIR / "raw" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = upload_dir / safe_name

    contents = await file.read()
    with open(target_path, "wb") as f:
        f.write(contents)

    # Extract text
    pdf_service = PDFExtractionService()
    if target_path.suffix.lower() == ".pdf":
        extracted = pdf_service.extract(target_path)
        full_text = extracted["full_text"]
    else:
        full_text = contents.decode("utf-8", errors="replace")

    # Extract structured terms
    extractor = LoanTermExtractor()
    extraction_result = extractor.extract_terms(full_text, document_name=safe_name)

    jurisdiction = jurisdiction_override.upper() if jurisdiction_override else extraction_result.jurisdiction

    doc = LoanDocument(
        filename=safe_name,
        file_type=target_path.suffix.lstrip(".").lower() or "pdf",
        file_size=len(contents),
        jurisdiction=jurisdiction,
        doc_type=extraction_result.doc_type,
        status="PARSED",
        file_path=str(target_path),
    )
    db.add(doc)
    db.flush()

    for field_name, f_rec in extraction_result.fields.items():
        field_obj = ExtractedLoanField(
            loan_document_id=doc.id,
            field_name=field_name,
            field_value_str=f_rec.value_str,
            field_value_num=f_rec.value_num,
            source_page=f_rec.source_page,
            source_excerpt=f_rec.source_excerpt,
            confidence=f_rec.confidence,
            is_verified=False,
        )
        db.add(field_obj)

    db.commit()
    db.refresh(doc)

    # Log audit event
    AuditService.log(
        db=db,
        event_type="DOCUMENT_UPLOADED",
        entity_type="LoanDocument",
        entity_id=doc.id,
        payload={
            "filename": safe_name,
            "jurisdiction": jurisdiction,
            "extracted_fields_count": len(extraction_result.fields),
        },
    )

    return _to_response(doc)


@router.get("", response_model=List[LoanDocumentResponse])
def list_documents(jurisdiction: str = None, db: Session = Depends(get_db)):
    q = db.query(LoanDocument)
    if jurisdiction:
        q = q.filter(LoanDocument.jurisdiction == jurisdiction.upper())
    docs = q.order_by(LoanDocument.upload_date.desc()).all()
    return [_to_response(d) for d in docs]


@router.get("/{doc_id}", response_model=LoanDocumentResponse)
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(LoanDocument).filter(LoanDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Loan document not found")
    return _to_response(doc)


@router.patch("/{doc_id}/fields/{field_id}", response_model=ExtractedFieldSchema)
def correct_field(
    doc_id: str,
    field_id: str,
    payload: FieldCorrectionRequest,
    db: Session = Depends(get_db),
):
    field = db.query(ExtractedLoanField).filter(
        ExtractedLoanField.id == field_id,
        ExtractedLoanField.loan_document_id == doc_id,
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="Extracted loan field not found")

    old_val = field.reviewer_corrected_value or field.field_value_str or str(field.field_value_num)
    field.reviewer_corrected_value = payload.corrected_value
    field.is_verified = True

    try:
        field.field_value_num = float(payload.corrected_value.replace("%", "").replace(",", ""))
    except ValueError:
        pass

    db.commit()
    db.refresh(field)

    AuditService.log(
        db=db,
        event_type="FIELD_VALUE_CORRECTED",
        entity_type="ExtractedLoanField",
        entity_id=field.id,
        payload={
            "loan_document_id": doc_id,
            "field_name": field.field_name,
            "old_value": old_val,
            "new_value": payload.corrected_value,
            "comment": payload.comment,
        },
    )

    return ExtractedFieldSchema(
        id=field.id,
        field_name=field.field_name,
        field_value=field.reviewer_corrected_value,
        source_page=field.source_page,
        source_excerpt=field.source_excerpt,
        confidence=1.0,
        is_verified=True,
        reviewer_corrected_value=field.reviewer_corrected_value,
    )


@router.get("/{doc_id}/extraction")
def get_document_extraction(doc_id: str, db: Session = Depends(get_db)):
    """Retrieve structured extraction result and field provenance for a loan document."""
    doc = db.query(LoanDocument).filter(LoanDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Loan document not found")
    return _to_response(doc)


@router.post("/{doc_id}/extract")
def trigger_document_extraction(doc_id: str, db: Session = Depends(get_db)):
    """Trigger or re-run term extraction on an existing document."""
    doc = db.query(LoanDocument).filter(LoanDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Loan document not found")

    p = Path(doc.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Source file missing on disk: {doc.file_path}")

    if p.suffix.lower() == ".pdf":
        pdf_service = PDFExtractionService()
        extracted = pdf_service.extract(p)
        text = extracted["full_text"]
    else:
        text = p.read_text(encoding="utf-8", errors="replace")

    extractor = LoanTermExtractor()
    extraction_result = extractor.extract_terms(text, document_name=doc.filename)

    # Re-populate extracted fields
    db.query(ExtractedLoanField).filter(ExtractedLoanField.loan_document_id == doc.id).delete()
    for field_name, record in extraction_result.fields.items():
        db_field = ExtractedLoanField(
            loan_document_id=doc.id,
            field_name=field_name,
            field_value_str=record.value_str or str(record.value),
            field_value_num=record.value_num,
            source_page=record.source_page or 1,
            source_excerpt=record.source_excerpt or "",
            confidence=record.confidence or 0.95,
        )
        db.add(db_field)

    doc.status = "PARSED"
    db.commit()
    db.refresh(doc)
    return _to_response(doc)
