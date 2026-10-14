"""
evaluate_compliance.py
======================
Evaluates the deterministic rule engine against verified ground-truth test cases
for both US (CFPB Regulation Z) and Indian (RBI directives) mortgage compliance.
Exit code: 0 if 100% of deterministic rule checks pass, else 1.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.services.rule_engine.engine import ComplianceRuleEngine
from backend.app.services.loan_extraction.term_extractor import ExtractedFieldRecord, LoanExtractionResult


def _col(text: str, width: int) -> str:
    return str(text)[:width].ljust(width)


def run_compliance_evaluation() -> int:
    engine = ComplianceRuleEngine()

    test_cases = [
        {
            "id": "tc_us_qm_compliant",
            "name": "US Compliant QM Note (1.2% fees, fixed rate)",
            "jurisdiction": "US",
            "terms": {
                "loan_amount": ExtractedFieldRecord(field_name="loan_amount", value=350000.0, value_num=350000.0, source_excerpt="$350,000.00"),
                "points_and_fees_percent": ExtractedFieldRecord(field_name="points_and_fees_percent", value=1.2, value_num=1.2, source_excerpt="1.20%"),
                "interest_rate_type": ExtractedFieldRecord(field_name="interest_rate_type", value="fixed", value_str="fixed", source_excerpt="Fixed Rate"),
                "prepayment_penalty_exists": ExtractedFieldRecord(field_name="prepayment_penalty_exists", value=False, source_excerpt="no prepayment penalty"),
            },
            "expected": {
                "US-REGZ-ATR-001": "NO_ISSUE_IDENTIFIED",
            }
        },
        {
            "id": "tc_us_qm_violation",
            "name": "US High-Fee Non-Compliant QM Note (4.11% fees)",
            "jurisdiction": "US",
            "terms": {
                "loan_amount": ExtractedFieldRecord(field_name="loan_amount", value=280000.0, value_num=280000.0, source_excerpt="$280,000.00"),
                "points_and_fees_percent": ExtractedFieldRecord(field_name="points_and_fees_percent", value=4.11, value_num=4.11, source_excerpt="4.11%"),
                "interest_rate_type": ExtractedFieldRecord(field_name="interest_rate_type", value="variable", value_str="variable", source_excerpt="Adjustable Rate"),
                "prepayment_penalty_exists": ExtractedFieldRecord(field_name="prepayment_penalty_exists", value=True, value_num=3.5, source_excerpt="3.50% penalty"),
            },
            "expected": {
                "US-REGZ-ATR-001": "POTENTIAL_ISSUE",
                "US-REGZ-PPP-002": "POTENTIAL_ISSUE",
            }
        },
        {
            "id": "tc_in_rbi_compliant",
            "name": "Indian Compliant Housing Loan (Zero foreclosure, simple interest)",
            "jurisdiction": "IN",
            "terms": {
                "borrower_type": ExtractedFieldRecord(field_name="borrower_type", value="individual", value_str="individual", source_excerpt="Individual borrower"),
                "interest_rate_type": ExtractedFieldRecord(field_name="interest_rate_type", value="floating", value_str="floating", source_excerpt="floating rate"),
                "prepayment_penalty_exists": ExtractedFieldRecord(field_name="prepayment_penalty_exists", value=False, source_excerpt="NO FORECLOSURE CHARGES"),
                "penal_interest_compounded": ExtractedFieldRecord(field_name="penal_interest_compounded", value=False, source_excerpt="shall not be compounded"),
            },
            "expected": {
                "IN-RBI-PPP-001": "NO_ISSUE_IDENTIFIED",
                "IN-RBI-PENAL-002": "NO_ISSUE_IDENTIFIED",
            }
        },
        {
            "id": "tc_in_rbi_violation",
            "name": "Indian Non-Compliant Loan (Foreclosure penalty + compounded default interest)",
            "jurisdiction": "IN",
            "terms": {
                "borrower_type": ExtractedFieldRecord(field_name="borrower_type", value="individual", value_str="individual", source_excerpt="Individual borrower"),
                "interest_rate_type": ExtractedFieldRecord(field_name="interest_rate_type", value="floating", value_str="floating", source_excerpt="Floating Rate"),
                "prepayment_penalty_exists": ExtractedFieldRecord(field_name="prepayment_penalty_exists", value=True, value_num=2.5, source_excerpt="prepayment penalty of 2.50%"),
                "penal_interest_compounded": ExtractedFieldRecord(field_name="penal_interest_compounded", value=True, source_excerpt="shall be compounded monthly"),
            },
            "expected": {
                "IN-RBI-PPP-001": "POTENTIAL_ISSUE",
                "IN-RBI-PENAL-002": "POTENTIAL_ISSUE",
            }
        },
    ]

    total_checks = 0
    passed_checks = 0

    SEP = "=" * 85
    print(f"\n{SEP}")
    print("  DETERMINISTIC COMPLIANCE RULE ENGINE BENCHMARK")
    print(SEP)

    hdr = (
        _col("CASE ID", 22) +
        _col("RULE ID", 18) +
        _col("STATUS", 10) +
        _col("OUTCOME", 20) +
        _col("MATCH", 8)
    )
    print(f"  {hdr}")
    print(f"  {'-' * 81}")

    for case in test_cases:
        cid = case["id"]
        jur = case["jurisdiction"]
        terms = case["terms"]
        expected = case["expected"]

        extraction = LoanExtractionResult(
            document_name=cid,
            jurisdiction=jur,
            doc_type="Mortgage Agreement",
            borrower_type="individual",
            fields=terms,
            missing_fields=[],
        )
        results = engine.evaluate(extraction)
        result_map = {r.rule_id: r.status for r in results}

        for rule_id, exp_status in expected.items():
            total_checks += 1
            got_status = result_map.get(rule_id, "NOT_EVALUATED")
            matched = (got_status == exp_status)

            if matched:
                passed_checks += 1

            row = (
                _col(cid, 22) +
                _col(rule_id, 18) +
                _col(f"[{'PASS' if matched else 'FAIL'}]", 10) +
                _col(got_status, 20) +
                _col("YES" if matched else "NO", 8)
            )
            print(f"  {row}")

    print(f"\n{SEP}")
    print("  COMPLIANCE ENGINE BENCHMARK SUMMARY")
    print(SEP)
    print(f"  Total rule checks evaluated: {total_checks}")
    print(f"  Checks matching ground-truth: {passed_checks}")
    accuracy = (passed_checks / total_checks * 100) if total_checks else 0.0
    print(f"  Deterministic Rule Precision : {accuracy:.1f}%")
    print(SEP)

    if accuracy == 100.0:
        print("  RESULT: PASS (100% deterministic precision verified)")
        return 0
    else:
        print(f"  RESULT: FAIL (Accuracy {accuracy:.1f}% < 100%)")
        return 1


if __name__ == "__main__":
    sys.exit(run_compliance_evaluation())
