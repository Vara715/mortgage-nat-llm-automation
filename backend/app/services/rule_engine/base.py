"""
base.py
=======
Abstract base class and schemas for deterministic compliance rules (Section 4.H).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from backend.app.services.loan_extraction.term_extractor import LoanExtractionResult


class RuleEvaluationResult(BaseModel):
    rule_id: str
    rule_name: str
    jurisdiction: str
    citation: str
    category: str
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    status: str  # 'POTENTIAL_ISSUE', 'NO_ISSUE_IDENTIFIED', 'NEEDS_REVIEW', 'NOT_EVALUABLE'
    loan_field: str
    extracted_value: Optional[str] = None
    reasoning: str
    recommended_action: str
    missing_information: List[str] = []


class DeterministicRule(ABC):
    rule_id: str
    rule_name: str
    jurisdiction: str
    citation: str
    category: str
    severity: str
    version: str = "1.0"
    effective_period: str
    applicability_conditions: str
    required_inputs: List[str]

    @abstractmethod
    def evaluate(self, extraction: LoanExtractionResult) -> RuleEvaluationResult:
        """Evaluates compliance against loan terms. Returns RuleEvaluationResult."""
        pass
