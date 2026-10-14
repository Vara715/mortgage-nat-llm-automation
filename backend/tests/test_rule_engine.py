"""
test_rule_engine.py
===================
Tests for deterministic compliance rule evaluations under US CFPB and Indian RBI regimes.
"""

from backend.app.services.loan_extraction.term_extractor import (
    LoanExtractionResult,
    ExtractedFieldRecord,
)
from backend.app.services.rule_engine.engine import ComplianceRuleEngine


def test_us_atr_qm_points_fees_rule():
    engine = ComplianceRuleEngine()

    # Case 1: Compliant (Points and fees 2.2% <= 3.0%)
    res_compliant = LoanExtractionResult(
        document_name="Test Note",
        jurisdiction="US",
        doc_type="Residential Mortgage Note",
        borrower_type="individual",
        fields={
            "loan_amount": ExtractedFieldRecord(field_name="loan_amount", value=200000, value_num=200000, source_excerpt=""),
            "points_and_fees_percent": ExtractedFieldRecord(field_name="points_and_fees_percent", value=2.2, value_num=2.2, source_excerpt=""),
        },
    )
    findings = engine.evaluate(res_compliant)
    rule_001 = next(f for f in findings if f.rule_id == "US-REGZ-ATR-001")
    assert rule_001.status == "NO_ISSUE_IDENTIFIED"

    # Case 2: Violation (Points and fees 4.11% > 3.0%)
    res_violation = LoanExtractionResult(
        document_name="Test Note High Fee",
        jurisdiction="US",
        doc_type="Residential Mortgage Note",
        borrower_type="individual",
        fields={
            "loan_amount": ExtractedFieldRecord(field_name="loan_amount", value=200000, value_num=200000, source_excerpt=""),
            "points_and_fees_percent": ExtractedFieldRecord(field_name="points_and_fees_percent", value=4.11, value_num=4.11, source_excerpt=""),
        },
    )
    findings = engine.evaluate(res_violation)
    rule_001 = next(f for f in findings if f.rule_id == "US-REGZ-ATR-001")
    assert rule_001.status == "POTENTIAL_ISSUE"
    assert rule_001.severity == "CRITICAL"


def test_us_prepayment_penalty_arm_rule():
    engine = ComplianceRuleEngine()

    # Prepayment penalty on ARM is strictly prohibited
    res_arm_violation = LoanExtractionResult(
        document_name="Test ARM Note",
        jurisdiction="US",
        doc_type="Residential Mortgage Note",
        borrower_type="individual",
        fields={
            "interest_rate_type": ExtractedFieldRecord(field_name="interest_rate_type", value="variable", value_str="variable", source_excerpt=""),
            "prepayment_penalty_exists": ExtractedFieldRecord(field_name="prepayment_penalty_exists", value=True, value_num=2.0, value_str="2% PENALTY", source_excerpt=""),
        },
    )
    findings = engine.evaluate(res_arm_violation)
    rule_002 = next(f for f in findings if f.rule_id == "US-REGZ-PPP-002")
    assert rule_002.status == "POTENTIAL_ISSUE"
    assert "1026.43(g)" in rule_002.citation


def test_in_rbi_foreclosure_ban_rule():
    engine = ComplianceRuleEngine()

    # Case 1: Compliant floating rate home loan to individual with no penalty
    res_in_ok = LoanExtractionResult(
        document_name="Test IN Note",
        jurisdiction="IN",
        doc_type="Housing Loan",
        borrower_type="individual",
        fields={
            "interest_rate_type": ExtractedFieldRecord(field_name="interest_rate_type", value="variable", value_str="variable", source_excerpt=""),
            "prepayment_penalty_exists": ExtractedFieldRecord(field_name="prepayment_penalty_exists", value=False, value_str="None (0%)", source_excerpt=""),
        },
    )
    findings = engine.evaluate(res_in_ok)
    rule_in_001 = next(f for f in findings if f.rule_id == "IN-RBI-PPP-001")
    assert rule_in_001.status == "NO_ISSUE_IDENTIFIED"

    # Case 2: Violation - Prepayment charge levied on individual floating rate home loan
    res_in_violation = LoanExtractionResult(
        document_name="Test IN Note Violation",
        jurisdiction="IN",
        doc_type="Housing Loan",
        borrower_type="individual",
        fields={
            "interest_rate_type": ExtractedFieldRecord(field_name="interest_rate_type", value="variable", value_str="variable", source_excerpt=""),
            "prepayment_penalty_exists": ExtractedFieldRecord(field_name="prepayment_penalty_exists", value=True, value_num=3.0, value_str="3% PREPAYMENT PENALTY", source_excerpt=""),
        },
    )
    findings = engine.evaluate(res_in_violation)
    rule_in_001 = next(f for f in findings if f.rule_id == "IN-RBI-PPP-001")
    assert rule_in_001.status == "POTENTIAL_ISSUE"
    assert rule_in_001.severity == "CRITICAL"


def test_in_rbi_penal_charges_rule():
    engine = ComplianceRuleEngine()

    # Compounding of penal charges is prohibited under RBI/2023-24/53
    res_penal_violation = LoanExtractionResult(
        document_name="Test IN Note Compound",
        jurisdiction="IN",
        doc_type="Housing Loan",
        borrower_type="individual",
        fields={
            "penal_interest_compounded": ExtractedFieldRecord(field_name="penal_interest_compounded", value=True, value_str="Compounded", source_excerpt=""),
        },
    )
    findings = engine.evaluate(res_penal_violation)
    rule_penal = next(f for f in findings if f.rule_id == "IN-RBI-PENAL-002")
    assert rule_penal.status == "POTENTIAL_ISSUE"
    assert "DoR.MCS.REC.28/01.01.001/2023-24" in rule_penal.citation or "Fair Lending" in rule_penal.citation
