"""
in_rules.py
===========
Deterministic compliance rules for Indian jurisdiction (Reserve Bank of India Directives).
"""

from typing import List
from backend.app.services.rule_engine.base import DeterministicRule, RuleEvaluationResult
from backend.app.services.loan_extraction.term_extractor import LoanExtractionResult


class INRBIPrepaymentAbolitionRule(DeterministicRule):
    rule_id = "IN-RBI-PPP-001"
    rule_name = "Prohibition of Foreclosure Charges on Floating Rate Home Loans"
    jurisdiction = "IN"
    citation = "RBI Circular DBOD.No.Dir.BC.107/13.03.00/2011-12"
    category = "PREPAYMENT_PENALTY"
    severity = "CRITICAL"
    effective_period = "2012-06-05 to Present"
    applicability_conditions = "Housing loans and term loans sanctioned on a floating interest rate basis to individual borrowers"
    required_inputs = ["interest_rate_type", "prepayment_penalty_exists", "borrower_type"]

    def evaluate(self, extraction: LoanExtractionResult) -> RuleEvaluationResult:
        borrower_type = extraction.borrower_type
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
                reasoning="Prepayment clause not clearly identified. Verification required to confirm zero charges.",
                recommended_action="Inspect Section 3 of agreement for foreclosure fee wording.",
                missing_information=["prepayment_penalty_exists"],
            )

        has_penalty = bool(prepay.value)

        if borrower_type == "individual" and rate_type_val in ["variable", "floating"]:
            if has_penalty:
                return RuleEvaluationResult(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    jurisdiction=self.jurisdiction,
                    citation=self.citation,
                    category=self.category,
                    severity="CRITICAL",
                    status="POTENTIAL_ISSUE",
                    loan_field="prepayment_penalty_exists",
                    extracted_value=prepay.value_str,
                    reasoning=(
                        "Under RBI Circular DBOD.No.Dir.BC.107/13.03.00/2011-12, banks and financial institutions "
                        "are strictly prohibited from charging foreclosure charges or pre-payment penalties on home loans "
                        "on a floating interest rate basis extended to individual borrowers."
                    ),
                    recommended_action="Amend agreement clause to: 'No foreclosure charges or pre-payment penalties shall be levied.'",
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
                    extracted_value="0% Foreclosure Charges",
                    reasoning="Zero foreclosure fees on floating rate individual loan. Fully compliant with RBI directives.",
                    recommended_action="No action required.",
                )
        else:
            # Corporate borrowers or fixed rate loans where prepayment charges are permissible
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="LOW",
                status="NO_ISSUE_IDENTIFIED",
                loan_field="prepayment_penalty_exists",
                extracted_value=f"{borrower_type.title()} borrower / {rate_type_val} rate",
                reasoning="Prepayment charges permitted under commercial negotiations for corporate entities or fixed-rate facilities.",
                recommended_action="No action required.",
            )


class INRBIPenalChargesRule(DeterministicRule):
    rule_id = "IN-RBI-PENAL-002"
    rule_name = "Prohibition of Compounding Penal Interest"
    jurisdiction = "IN"
    citation = "RBI Circular DoR.MCS.REC.28/01.01.001/2023-24 (Fair Lending Practice)"
    category = "PENAL_CHARGES"
    severity = "HIGH"
    effective_period = "2024-01-01 to Present"
    applicability_conditions = "All retail, commercial, and priority sector loan accounts"
    required_inputs = ["penal_interest_compounded"]

    def evaluate(self, extraction: LoanExtractionResult) -> RuleEvaluationResult:
        penal = extraction.fields.get("penal_interest_compounded")
        if not penal:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="MEDIUM",
                status="NEEDS_REVIEW",
                loan_field="penal_interest_compounded",
                extracted_value="Not Specified",
                reasoning="Penal charges terms not identified. Verification required to ensure non-compounding.",
                recommended_action="Review default interest clause in the agreement.",
                missing_information=["penal_interest_compounded"],
            )

        if bool(penal.value):
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="HIGH",
                status="POTENTIAL_ISSUE",
                loan_field="penal_interest_compounded",
                extracted_value="Compounded / Capitalised",
                reasoning=(
                    "Under RBI Fair Lending Practice directives, penalty for default must be levied as separate 'penal charges' "
                    "on a simple interest basis and CANNOT be compounded or capitalised into the loan balance."
                ),
                recommended_action="Amend Default/Penal clause to state that penal charges shall not be compounded or capitalised.",
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
                loan_field="penal_interest_compounded",
                extracted_value="Simple Penal Charges",
                reasoning="Simple penal charges without compounding. Compliant with Fair Lending Practice guidelines.",
                recommended_action="No action required.",
            )


class INRBIHousingLTVRule(DeterministicRule):
    rule_id = "IN-RBI-LTV-003"
    rule_name = "Housing Loan Loan-to-Value (LTV) Ratio Caps"
    jurisdiction = "IN"
    citation = "RBI Master Circular - Housing Finance & Master Directions"
    category = "LTV_MARGIN_LIMITS"
    severity = "CRITICAL"
    effective_period = "2015-07-01 to Present"
    applicability_conditions = "Individual retail housing loans sanctioned by commercial banks"
    required_inputs = ["ltv_percent", "loan_amount"]

    def evaluate(self, extraction: LoanExtractionResult) -> RuleEvaluationResult:
        if extraction.doc_type != "Housing Loan Agreement (India)":
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="LOW",
                status="NOT_EVALUABLE",
                loan_field="ltv_percent",
                extracted_value="Non-Retail Housing Facility",
                reasoning="Statutory LTV caps apply specifically to individual retail housing loans.",
                recommended_action="Verify commercial credit exposure guidelines.",
            )

        f_ltv = extraction.fields.get("ltv_percent")
        f_amt = extraction.fields.get("loan_amount")

        if not f_ltv or not f_amt:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="MEDIUM",
                status="NEEDS_REVIEW",
                loan_field="ltv_percent",
                extracted_value="Missing LTV or Principal",
                reasoning="LTV or loan amount could not be computed. Verification of borrower down payment required.",
                recommended_action="Input property value and sanctioned loan amount to calculate LTV.",
                missing_information=["ltv_percent", "loan_amount"],
            )

        ltv = f_ltv.value_num if f_ltv.value_num is not None else 80.0
        amt = f_amt.value_num if f_amt.value_num is not None else 5000000.0

        if amt <= 3000000:
            max_ltv = 90.0
        elif amt <= 7500000:
            max_ltv = 80.0
        else:
            max_ltv = 75.0

        if ltv > max_ltv:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                jurisdiction=self.jurisdiction,
                citation=self.citation,
                category=self.category,
                severity="CRITICAL",
                status="POTENTIAL_ISSUE",
                loan_field="ltv_percent",
                extracted_value=f"{ltv:.1f}% (Limit: {max_ltv:.0f}%)",
                reasoning=(
                    f"LTV of {ltv:.1f}% exceeds statutory RBI ceiling of {max_ltv:.0f}% for loans in this slab (Rs. {amt:,.0f}). "
                    f"RBI mandates a minimum borrower margin contribution of {100-max_ltv:.0f}%."
                ),
                recommended_action=f"Increase borrower margin contribution to bring LTV down to {max_ltv:.0f}%.",
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
                loan_field="ltv_percent",
                extracted_value=f"{ltv:.1f}% (Limit: {max_ltv:.0f}%)",
                reasoning=f"LTV ratio ({ltv:.1f}%) is within the permissible statutory limit of {max_ltv:.0f}%.",
                recommended_action="No action required.",
            )
