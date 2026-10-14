"""
compliance.py
=============
Pydantic schemas for Section 5: Compliance Finding Schema.
Validates findings, evidence, loan terms, and audit reports.
"""

from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class LoanTermEvidence(BaseModel):
    field: str
    value: Optional[Any] = None
    source_page: int = 1
    source_excerpt: str


class RegulatoryEvidenceItem(BaseModel):
    source_name: str
    source_url: str
    citation: str
    page_number: Optional[int] = None
    quoted_text: str
    document_version: Optional[str] = None
    relevance_score: float = 1.0


class ComplianceFindingSchema(BaseModel):
    finding_id: str
    rule_id: str
    category: str
    severity: str = Field(..., description="'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'")
    status: str = Field(..., description="'POTENTIAL_ISSUE', 'NO_ISSUE_IDENTIFIED', 'NEEDS_REVIEW', 'NOT_EVALUABLE'")
    loan_term: LoanTermEvidence
    regulatory_evidence: List[RegulatoryEvidenceItem] = Field(default_factory=list)
    reasoning: str
    missing_information: List[str] = Field(default_factory=list)
    recommended_action: str
    review_status: str = Field(default="PENDING", description="'PENDING', 'ACCEPTED', 'REJECTED', 'MODIFIED'")


class ComplianceAnalysisResponse(BaseModel):
    analysis_id: str
    loan_document_id: str
    document_name: str
    jurisdiction: str = Field(..., description="'US' or 'IN'")
    overall_status: str = Field(..., description="'POTENTIAL_ISSUE', 'NO_ISSUE_IDENTIFIED', 'NEEDS_REVIEW'")
    summary: str
    findings: List[ComplianceFindingSchema] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    generated_at: str
