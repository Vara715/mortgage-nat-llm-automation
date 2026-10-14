"""
hmda.py
=======
API endpoints for authentic HMDA public mortgage lending analytics,
distribution metrics, and dataset ingestion.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.entities import HMDARecord
from backend.app.schemas.hmda import HMDAAnalyticsResponse, HMDARecordResponse, HMDAImportResponse
from backend.app.services.hmda.analytics import HMDAAnalyticsService
from backend.app.services.hmda.loader import HMDALoaderService

router = APIRouter(prefix="/hmda", tags=["HMDA Public Data"])


@router.get("/analytics", response_model=HMDAAnalyticsResponse)
def get_hmda_analytics(
    state_code: Optional[str] = None,
    loan_purpose: Optional[str] = None,
    loan_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    service = HMDAAnalyticsService(db)
    return service.compute_analytics(state_code=state_code, loan_purpose=loan_purpose, loan_type=loan_type)


@router.get("/records", response_model=List[HMDARecordResponse])
def get_hmda_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action_taken: Optional[str] = None,
    loan_purpose: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(HMDARecord)
    if action_taken:
        query = query.filter(HMDARecord.action_taken == action_taken)
    if loan_purpose:
        query = query.filter(HMDARecord.loan_purpose == loan_purpose)

    records = query.offset(offset).limit(limit).all()
    return [
        HMDARecordResponse(
            id=r.id,
            activity_year=r.activity_year,
            lei=r.lei,
            loan_type=r.loan_type,
            loan_purpose=r.loan_purpose,
            loan_amount=r.loan_amount,
            action_taken=r.action_taken,
            state_code=r.state_code,
            county_code=r.county_code,
            interest_rate=r.interest_rate,
            rate_spread=r.rate_spread,
            property_value=r.property_value,
            loan_to_value_ratio=r.loan_to_value_ratio,
        )
        for r in records
    ]


@router.post("/import", response_model=HMDAImportResponse)
def import_hmda_data(db: Session = Depends(get_db)):
    csv_path = settings.DATA_DIR / "raw" / "hmda" / "hmda_2023_subset.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Authentic HMDA dataset subset not found on disk.")
    service = HMDALoaderService(db)
    return service.import_csv(csv_path)
