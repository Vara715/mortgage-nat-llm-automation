"""
evaluate_extraction.py
======================
Evaluates LoanTermExtractor against the annotated extraction benchmark corpus.
Compares extracted fields (value_num / value_str / value_bool) against expected
values with optional tolerance windows.

Exit code: 0 if overall field_accuracy_pct >= 50%, else 1.
"""

import sys
import json
import math
from pathlib import Path

# Ensure project root is on the path before any project imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.services.loan_extraction.term_extractor import LoanTermExtractor  # noqa: E402

# ---------------------------------------------------------------------------
# Extractor field name mapping
# The benchmark uses canonical names; the extractor may store them under
# slightly different keys. This map translates benchmark keys → extractor keys.
# ---------------------------------------------------------------------------
FIELD_ALIAS: dict[str, list[str]] = {
    "rate_type":              ["interest_rate_type"],
    "prepayment_penalty_exists": ["prepayment_penalty_exists"],
    "penal_charges_compound": ["penal_interest_compounded"],
    "interest_rate":          ["interest_rate"],
    "loan_amount":            ["loan_amount"],
    "points_and_fees_percent": ["points_and_fees_percent"],
}


def _resolve_field(fields: dict, bench_key: str):
    """Return the ExtractedFieldRecord for a benchmark field key, or None."""
    candidates = FIELD_ALIAS.get(bench_key, [bench_key])
    for k in candidates:
        if k in fields:
            return fields[k]
    return None


def _check_field(record, expected: dict) -> tuple[str, str]:
    """
    Compare a single extracted field record against expected spec.

    Returns (status, detail) where status is one of:
      'CORRECT' | 'WRONG' | 'MISSING'
    """
    if record is None:
        return "MISSING", "field not extracted"

    # Boolean comparison
    if "value_bool" in expected:
        # The extractor stores booleans in record.value (Python bool)
        extracted_bool = bool(record.value)
        expected_bool = bool(expected["value_bool"])
        if extracted_bool == expected_bool:
            return "CORRECT", f"{extracted_bool}"
        return "WRONG", f"got {extracted_bool}, expected {expected_bool}"

    # Numeric comparison with absolute tolerance
    if "value_num" in expected:
        tol = expected.get("tolerance", 0)
        exp_num = float(expected["value_num"])
        got_num = record.value_num
        if got_num is None:
            # Try parsing value_str as float
            try:
                got_num = float(str(record.value_str).replace(",", "").replace("%", ""))
            except (TypeError, ValueError):
                return "WRONG", f"value_num is None, value_str='{record.value_str}'"
        if math.isclose(got_num, exp_num, abs_tol=tol + 1e-9):
            return "CORRECT", f"{got_num} ~ {exp_num} (tol={tol})"
        return "WRONG", f"got {got_num}, expected {exp_num} +/-{tol}"

    # String comparison (case-insensitive, substring if tolerance_pct given)
    if "value_str" in expected:
        exp_str = str(expected["value_str"]).lower()
        got_raw = record.value_str or str(record.value)
        got_str = got_raw.lower()
        tol_pct = expected.get("tolerance_pct")
        # For numeric strings, check within pct tolerance
        if tol_pct is not None:
            try:
                exp_f = float(exp_str.replace("%", ""))
                got_f = float(got_str.replace("%", "").split()[0])
                if abs(got_f - exp_f) <= tol_pct + 1e-9:
                    return "CORRECT", f"{got_f} ~ {exp_f} (+/-{tol_pct}%)"
                return "WRONG", f"got {got_f}, expected {exp_f} +/-{tol_pct}"
            except ValueError:
                pass
        # Plain substring match
        if exp_str in got_str or got_str in exp_str:
            return "CORRECT", f"'{got_str}'"
        return "WRONG", f"got '{got_str}', expected '{exp_str}'"

    return "WRONG", "unknown expected spec"


def _load_doc(doc_path_rel: str) -> str | None:
    """Read document text from a path relative to the project root."""
    project_root = Path(__file__).parent.parent
    p = project_root / doc_path_rel
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="ignore")


def _col(text: str, width: int) -> str:
    """Left-justify text in a fixed-width column."""
    return str(text)[:width].ljust(width)


def run_evaluation(benchmark_path: str) -> int:
    """Run extraction evaluation. Returns exit code (0 = pass, 1 = fail)."""
    data = json.loads(Path(benchmark_path).read_text(encoding="utf-8"))
    extractor = LoanTermExtractor()

    total_cases = 0
    total_fields = 0
    fields_correct = 0
    fields_missing = 0
    fields_wrong = 0

    SEP = "-" * 90

    for case in data:
        doc_id      = case["doc_id"]
        doc_path    = case["doc_path"]
        description = case["description"]
        expected    = case["expected_fields"]

        total_cases += 1

        # ── Load document ───────────────────────────────────────────────────
        text = _load_doc(doc_path)
        if text is None:
            print(f"\n[SKIP] {doc_id}: file not found → {doc_path}")
            # Count all expected fields as MISSING
            for key in expected:
                total_fields += 1
                fields_missing += 1
            continue

        # ── Extract ─────────────────────────────────────────────────────────
        result = extractor.extract_terms(text, document_name=Path(doc_path).name)

        # ── Per-case header ─────────────────────────────────────────────────
        print(f"\n{SEP}")
        print(f"  Case : {doc_id}")
        print(f"  Desc : {description}")
        print(f"  Jurisdiction detected: {result.jurisdiction}  |  Doc type: {result.doc_type}")
        print(SEP)
        hdr = (
            _col("FIELD", 32) +
            _col("STATUS", 9) +
            _col("DETAIL", 46)
        )
        print(f"  {hdr}")
        print(f"  {'-'*87}")

        for bench_key, exp_spec in expected.items():
            record = _resolve_field(result.fields, bench_key)
            status, detail = _check_field(record, exp_spec)

            total_fields += 1
            if status == "CORRECT":
                fields_correct += 1
            elif status == "MISSING":
                fields_missing += 1
            else:
                fields_wrong += 1

            row = (
                _col(bench_key, 32) +
                _col(f"[{status}]", 9) +
                _col(detail, 46)
            )
            print(f"  {row}")

    # ── Summary ─────────────────────────────────────────────────────────────
    field_accuracy_pct = (fields_correct / total_fields * 100) if total_fields else 0.0
    print(f"\n{'='*90}")
    print("  EXTRACTION EVALUATION SUMMARY")
    print(f"{'='*90}")
    print(f"  Total test cases   : {total_cases}")
    print(f"  Total fields tested: {total_fields}")
    print(f"  Fields correct     : {fields_correct}")
    print(f"  Fields missing     : {fields_missing}")
    print(f"  Fields wrong       : {fields_wrong}")
    print(f"  Field accuracy     : {field_accuracy_pct:.1f}%")
    print(f"{'='*90}")

    threshold = 50.0
    if field_accuracy_pct >= threshold:
        print(f"  RESULT: PASS  (accuracy {field_accuracy_pct:.1f}% >= {threshold}%)")
        return 0
    else:
        print(f"  RESULT: FAIL  (accuracy {field_accuracy_pct:.1f}% < {threshold}%)")
        return 1


if __name__ == "__main__":
    benchmark = Path(__file__).parent.parent / "data" / "benchmark" / "extraction_benchmark.json"
    exit_code = run_evaluation(str(benchmark))
    sys.exit(exit_code)
