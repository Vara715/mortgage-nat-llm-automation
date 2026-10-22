"""
analytics.py
============
Descriptive analytics and aggregated statistics for authentic HMDA lending data.
Preserves distinctions between application outcomes and loan performance.
Mandates clear sample-size caveats and legal compliance disclaimers.
"""

from typing import Dict, Any, List, Optional
import statistics
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.entities import HMDARecord
from backend.app.schemas.hmda import HMDAAnalyticsResponse


class HMDAAnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def compute_analytics(
        self,
        state_code: Optional[str] = None,
        loan_purpose: Optional[str] = None,
        loan_type: Optional[str] = None,
    ) -> HMDAAnalyticsResponse:
        query = self.db.query(HMDARecord)
        if state_code:
            query = query.filter(HMDARecord.state_code == state_code)
        if loan_purpose:
            query = query.filter(HMDARecord.loan_purpose == loan_purpose)
        if loan_type:
            query = query.filter(HMDARecord.loan_type == loan_type)

        records = query.all()
        total_records = len(records)

        if total_records == 0:
            return HMDAAnalyticsResponse(
                total_records=0,
                sample_size_notes="No records found matching specified filters.",
                disclaimer="HMDA data is public application disclosure data, not proof of individual statutory compliance.",
                loan_types_distribution={},
                loan_purposes_distribution={},
                actions_taken_distribution={},
                approval_rate_percent=0.0,
                denial_rate_percent=0.0,
                avg_loan_amount=0.0,
                median_loan_amount=0.0,
                avg_interest_rate=None,
                avg_ltv=None,
                state_breakdown={},
            )

        # Loan type distribution
        loan_types: Dict[str, int] = {}
        loan_purposes: Dict[str, int] = {}
        actions_taken: Dict[str, int] = {}
        state_breakdown: Dict[str, int] = {}

        loan_amounts: List[float] = []
        interest_rates: List[float] = []
        ltvs: List[float] = []

        approved_count = 0
        denied_count = 0

        for r in records:
            # Type
            t = r.loan_type or "Unknown"
            loan_types[t] = loan_types.get(t, 0) + 1

            # Purpose
            p = r.loan_purpose or "Unknown"
            loan_purposes[p] = loan_purposes.get(p, 0) + 1

            # Action
            act = r.action_taken or "Unknown"
            actions_taken[act] = actions_taken.get(act, 0) + 1

            # State
            s = r.state_code or "Unknown"
            state_breakdown[s] = state_breakdown.get(s, 0) + 1

            # Outcome rate calculations (CFPB standard definitions)
            act_lower = act.lower()
            if "originated" in act_lower or "approved" in act_lower:
                approved_count += 1
            elif "denied" in act_lower:
                denied_count += 1

            if r.loan_amount:
                loan_amounts.append(float(r.loan_amount))
            if r.interest_rate is not None:
                interest_rates.append(float(r.interest_rate))
            if r.loan_to_value_ratio is not None:
                ltvs.append(float(r.loan_to_value_ratio))

        avg_loan = sum(loan_amounts) / len(loan_amounts) if loan_amounts else 0.0
        med_loan = statistics.median(loan_amounts) if loan_amounts else 0.0
        avg_rate = (sum(interest_rates) / len(interest_rates)) if interest_rates else None
        avg_ltv = (sum(ltvs) / len(ltvs)) if ltvs else None

        approval_rate = round((approved_count / total_records) * 100.0, 2)
        denial_rate = round((denied_count / total_records) * 100.0, 2)

        sample_notes = (
            f"Analysis based on {total_records} authentic CFPB/FFIEC HMDA 2023 Loan Application Register (LAR) records. "
            "Data reflects application activity and reported outcomes, not loan performance over time."
        )

        disclaimer = (
            "NOTICE: HMDA data represents public statistical reporting pursuant to Regulation C (12 CFR Part 1003). "
            "Approval of an application in HMDA data does NOT establish legal compliance under Regulation Z, "
            "RESPA, or other statutory regimes. mortgage_assistant uses HMDA solely for market context."
        )

        return HMDAAnalyticsResponse(
            total_records=total_records,
            sample_size_notes=sample_notes,
            disclaimer=disclaimer,
            loan_types_distribution=loan_types,
            loan_purposes_distribution=loan_purposes,
            actions_taken_distribution=actions_taken,
            approval_rate_percent=approval_rate,
            denial_rate_percent=denial_rate,
            avg_loan_amount=round(avg_loan, 2),
            median_loan_amount=round(med_loan, 2),
            avg_interest_rate=round(avg_rate, 3) if avg_rate is not None else None,
            avg_ltv=round(avg_ltv, 2) if avg_ltv is not None else None,
            state_breakdown=state_breakdown,
        )
