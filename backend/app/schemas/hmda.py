"""
hmda.py
=======
Pydantic schemas for HMDA public mortgage analytics and import operations.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel


class HMDARecordResponse(BaseModel):
    id: int
    activity_year: str
    lei: str
    loan_type: str
    loan_purpose: str
    loan_amount: float
    action_taken: str
    state_code: str
    county_code: str
    interest_rate: Optional[float] = None
    rate_spread: Optional[float] = None
    property_value: Optional[float] = None
    loan_to_value_ratio: Optional[float] = None


class HMDAAnalyticsResponse(BaseModel):
    total_records: int
    sample_size_notes: str
    disclaimer: str
    loan_types_distribution: Dict[str, int]
    loan_purposes_distribution: Dict[str, int]
    actions_taken_distribution: Dict[str, int]
    approval_rate_percent: float
    denial_rate_percent: float
    avg_loan_amount: float
    median_loan_amount: float
    avg_interest_rate: Optional[float] = None
    avg_ltv: Optional[float] = None
    state_breakdown: Dict[str, int]


class HMDAImportResponse(BaseModel):
    import_id: str
    filename: str
    total_records_imported: int
    imported_at: datetime
    checksum: str
