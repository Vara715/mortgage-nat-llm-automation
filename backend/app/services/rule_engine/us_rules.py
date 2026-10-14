"""
us_rules.py
===========
Deterministic compliance rules for United States jurisdiction (CFPB Regulation Z - 12 CFR Part 1026).
"""

from typing import List
from backend.app.services.rule_engine.base import DeterministicRule, RuleEvaluationResult
from backend.app.services.loan_extraction.term_extractor import LoanExtractionResult


class USRegZPointsAndFeesRule(DeterministicRule):
    rule_id = "US-REGZ-ATR-001"
    rule_name = "Qualified Mortgage Points and Fees Cap"
    jurisdiction = "US"
    citation = "12 CFR § 1026.43(e)(3)"
    category = "ABILITY_TO_REPAY_QM"
    severity = "CRITICAL"
    effective_period = "2014-01-10 to Present"
    applicability_conditions = "Consumer-purpose residential mortgage loans >= $100,000 intended as Qualified Mortgages"
    required_inputs = ["loan_amount", "points_and_fees_percent"]

    def evaluate(self, extraction: LoanExtractionResult) -> RuleEvaluationResult:
        if "points_and_fees_percent" not in extraction.fields:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity=self.severity,
                status="NOT_EVALUABLE",
                loan_field="points_and_fees_percent",
                extracted_value="Not Disclosed",
                reasoning="Points and fees breakdown not identified in document text. Cannot verify 3.00% Qualified Mortgage statutory ceiling.",
                recommended_action="Review Closing Disclosure Page 2 Loan Costs and input total points and fees.",
                missing_information=["points_and_fees_percent", "points_and_fees_amount"],
            )

        f_pts = extraction.fields["points_and_fees_percent"]
        pts_pct = f_pts.value_num if f_pts.value_num is not None else 0.0

        if pts_pct > 3.00:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity=self.severity,
                status="POTENTIAL_ISSUE",
                loan_field="points_and_fees_percent",
                extracted_value=f"{pts_pct:.2f}%",
                reasoning=(
                    f"Points and fees ({pts_pct:.2f}%) exceed the 3.00% statutory ceiling for loans >= $100,000 "
                    f"under 12 CFR § 1026.43(e)(3). This loan loses Qualified Mortgage (QM) safe harbor protection "
                    f"and may trigger High-Cost Mortgage (HOEPA) coverage."
                ),
                recommended_action="Cure excessive points and fees through lender credit or borrower fee refund before consummation.",
            )
        else:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="LOW",
                status="NO_ISSUE_IDENTIFIED",
                loan_field="points_and_fees_percent",
                extracted_value=f"{pts_pct:.2f}%",
                reasoning=f"Points and fees ({pts_pct:.2f}%) are within the 3.00% statutory limit for Qualified Mortgages.",
                recommended_action="No corrective action required.",
            )


class USRegZPrepaymentPenaltyRule(DeterministicRule):
    rule_id = "US-REGZ-PPP-002"
    rule_name = "Prepayment Penalty Prohibition on Variable-Rate & High-Cost Loans"
    jurisdiction = "US"
    citation = "12 CFR § 1026.43(g)"
    category = "PREPAYMENT_PENALTY"
    severity = "CRITICAL"
    effective_period = "2014-01-10 to Present"
    applicability_conditions = "All consumer credit transactions secured by a dwelling"
    required_inputs = ["interest_rate_type", "prepayment_penalty_exists"]

    def evaluate(self, extraction: LoanExtractionResult) -> RuleEvaluationResult:
        rate_type = extraction.fields.get("interest_rate_type")
        rate_type_val = rate_type.value_str if rate_type else "variable"
        prepay = extraction.fields.get("prepayment_penalty_exists")

        if not prepay:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="MEDIUM",
                status="NEEDS_REVIEW",
                loan_field="prepayment_penalty_exists",
                extracted_value="Not Explicitly Found",
                reasoning="The agreement does not explicitly state whether a prepayment penalty applies. Human verification required.",
                recommended_action="Review Section 4 of the Note or Closing Disclosure Section H for prepayment penalty disclosures.",
                missing_information=["prepayment_penalty_exists"],
            )

        has_penalty = bool(prepay.value)

        # 1. Check: Prepayment penalty on Variable / Adjustable rate loan is strictly illegal under 12 CFR 1026.43(g)(1)(i)
        if has_penalty and rate_type_val == "variable":
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="CRITICAL",
                status="POTENTIAL_ISSUE",
                loan_field="prepayment_penalty_exists",
                extracted_value=prepay.value_str or "Penalty Applied",
                reasoning=(
                    "Under 12 CFR § 1026.43(g)(1)(i), a covered transaction must not include a prepayment penalty "
                    "if the loan has an adjustable rate or variable interest rate. Levying a prepayment penalty on "
                    "this variable-rate note violates federal Truth in Lending regulations."
                ),
                recommended_action="Immediately strike out the prepayment penalty clause from the Note and provide a revised Loan Estimate/Closing Disclosure.",
            )
        elif has_penalty and rate_type_val == "fixed":
            # Permitted only if QM fixed rate and <= 2% in years 1-2, 0% after 36 months
            p_val = prepay.value_num if prepay.value_num is not None else 2.5
            if p_val > 2.0:
                return RuleEvaluationResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    jurisdiction=self.jurisdiction,
                    citation=self.citation,
                    category=self.category,
                    severity="HIGH",
                    status="POTENTIAL_ISSUE",
                    loan_field="prepayment_penalty_exists",
                    extracted_value=f"{p_val}% Penalty",
                    reasoning=f"Prepayment penalty rate ({p_val}%) exceeds the 2.00% cap permissible under 12 CFR § 1026.43(g)(2)(i).",
                    recommended_action="Reduce prepayment penalty rate to 2.00% or lower for years 1-2, and 0% after 36 months.",
                )
            else:
                return RuleEvaluationResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    jurisdiction=self.jurisdiction,
                    citation=self.citation,
                    category=self.category,
                    severity="LOW",
                    status="NO_ISSUE_IDENTIFIED",
                    loan_field="prepayment_penalty_exists",
                    extracted_value=prepay.value_str,
                    reasoning="Fixed-rate loan prepayment penalty is within statutory caps (<= 2%).",
                    recommended_action="Verify that alternative loan without penalty was offered per § 1026.43(g)(3).",
                )
        else:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="LOW",
                status="NO_ISSUE_IDENTIFIED",
                loan_field="prepayment_penalty_exists",
                extracted_value="No Prepayment Penalty (0%)",
                reasoning="Loan contains no prepayment penalty. Fully compliant with 12 CFR § 1026.43(g).",
                recommended_action="No action required.",
            )


class USRegZEscrowRequirementRule(DeterministicRule):
    rule_id = "US-REGZ-HPML-003"
    rule_name = "Higher-Priced Mortgage Loan Mandatory Escrow Account"
    jurisdiction = "US"
    citation = "12 CFR § 1026.35(b)"
    category = "ESCROW_HPML"
    severity = "HIGH"
    effective_period = "2013-06-01 to Present"
    applicability_conditions = "First-lien higher-priced mortgage loans (HPML) secured by a principal dwelling"
    required_inputs = ["escrow_established"]

    def evaluate(self, extraction: LoanExtractionResult) -> RuleEvaluationResult:
        escrow = extraction.fields.get("escrow_established")
        if not escrow:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="MEDIUM",
                status="NEEDS_REVIEW",
                loan_field="escrow_established",
                extracted_value="Not Disclosed",
                reasoning="Escrow account status not explicitly detailed in extracted text. Verification required if loan qualifies as HPML.",
                recommended_action="Confirm whether an escrow account for property taxes and hazard insurance is active.",
                missing_information=["escrow_established"],
            )

        if not escrow.value:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity=self.severity,
                status="POTENTIAL_ISSUE",
                loan_field="escrow_established",
                extracted_value="Escrow Waived",
                reasoning=(
                    "The contract indicates escrow waiver. Under 12 CFR § 1026.35(b), a creditor may not consummate "
                    "a higher-priced mortgage loan (HPML) without establishing an escrow account for taxes and insurance "
                    "maintained for a minimum of 5 years."
                ),
                recommended_action="Establish an escrow account prior to consummation or verify exemption status under § 1026.35(b)(2).",
            )
        else:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="LOW",
                status="NO_ISSUE_IDENTIFIED",
                loan_field="escrow_established",
                extracted_value="Escrow Established",
                reasoning="Escrow account is established in accordance with 12 CFR § 1026.35.",
                recommended_action="No action required.",
            )
