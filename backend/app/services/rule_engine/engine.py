"""
engine.py
=========
Multi-jurisdictional Rule Engine (Section 4.F & 4.H).
Executes only applicable rules for the validated jurisdiction:
- US rules for US documents
- IN rules for Indian documents
- If jurisdiction is unrecognized or ambiguous, returns NEEDS_REVIEW.
"""

from typing import List, Dict
from backend.app.services.rule_engine.base import DeterministicRule, RuleEvaluationResult
from backend.app.services.rule_engine.us_rules import (
    USRegZPointsAndFeesRule,
    USRegZPrepaymentPenaltyRule,
    USRegZEscrowRequirementRule,
)
from backend.app.services.rule_engine.in_rules import (
    INRBIPrepaymentAbolitionRule,
    INRBIPenalChargesRule,
    INRBIHousingLTVRule,
)
from backend.app.services.loan_extraction.term_extractor import LoanExtractionResult


class ComplianceRuleEngine:
    def __init__(self):
        self.us_rules: List[DeterministicRule] = [
            USRegZPointsAndFeesRule(),
            USRegZPrepaymentPenaltyRule(),
            USRegZEscrowRequirementRule(),
        ]
        self.in_rules: List[DeterministicRule] = [
            INRBIPrepaymentAbolitionRule(),
            INRBIPenalChargesRule(),
            INRBIHousingLTVRule(),
        ]

    def evaluate(self, extraction: LoanExtractionResult) -> List[RuleEvaluationResult]:
        jurisdiction = extraction.jurisdiction.upper()
        results: List[RuleEvaluationResult] = []

        if jurisdiction == "US":
            for rule in self.us_rules:
                res = rule.evaluate(extraction)
                results.append(res)
        elif jurisdiction == "IN":
            for rule in self.in_rules:
                res = rule.evaluate(extraction)
                results.append(res)
        else:
            # Unrecognized jurisdiction: return NEEDS_REVIEW without guessing rules
            results.append(
                RuleEvaluationResult(
                    rule_id="JURISDICTION-AMBIGUITY-000",
                    rule_name="Unidentified Regulatory Jurisdiction",
                    jurisdiction=jurisdiction,
                    citation="Compliance Protocol Section 4.F",
                    category="GENERAL_REGULATORY",
                    severity="CRITICAL",
                    status="NEEDS_REVIEW",
                    loan_field="jurisdiction",
                    extracted_value=jurisdiction,
                    reasoning=f"Document jurisdiction '{jurisdiction}' cannot be established with high confidence. Cannot apply rules from other jurisdictions.",
                    recommended_action="Manually assign jurisdiction (US or IN) before executing automated compliance audit.",
                )
            )

        return results
