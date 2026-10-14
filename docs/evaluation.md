# System Evaluation & Benchmark Methodology

This document details the automated test suites, benchmark datasets, evaluation scripts, and verification metrics for **morgage-loan-automation**.

---

## 1. Automated Test Suite (Pytest)

The automated test suite runs via `pytest` and validates unit behavior, integration between components, and end-to-end API workflows:

```bash
python -m pytest backend/tests -v
```

### Test Suite Execution Summary (24 Tests, 100% Pass Rate):

| Test Module | Test Name | Invariant Verified | Status |
| :--- | :--- | :--- | :--- |
| `test_api_e2e.py` | `test_health_endpoint` | Base health check returns DB connected | PASS |
| `test_api_e2e.py` | `test_sources_endpoint` | Registry lists sources with SHA-256 | PASS |
| `test_api_e2e.py` | `test_regulations_search` | Reg search returns relevant chunks | PASS |
| `test_api_e2e.py` | `test_documents_list_and_get` | Document metadata and extraction retrieval | PASS |
| `test_api_e2e.py` | `test_compliance_analyses` | Compliance analysis lists and details | PASS |
| `test_api_e2e.py` | `test_review_tasks_and_decision` | HITL decision submission & status transition | PASS |
| `test_api_e2e.py` | `test_hmda_analytics_api` | HMDA statistical aggregates and distributions | PASS |
| `test_api_e2e.py` | `test_audit_events_api` | Chronological audit ledger queries | PASS |
| `test_api_e2e.py` | `test_report_pdf_download` | ReportLab PDF compliance certificate streaming | PASS |
| `test_automation_api.py` | `test_readiness_probe` | `/api/health/ready` probe verifies chunks | PASS |
| `test_automation_api.py` | `test_datasets_crud_and_ingestion` | Dataset manifest registration & ingestion | PASS |
| `test_automation_api.py` | `test_retrieval_search_api` | `/api/retrieval/search` POST route & filters | PASS |
| `test_automation_api.py` | `test_structured_qa_api` | Grounded Q&A generation endpoint | PASS |
| `test_automation_api.py` | `test_review_queue_endpoint` | `/api/reviews/queue` alias for n8n integration | PASS |
| `test_automation_api.py` | `test_document_classification_service` | DocumentClassifier 7-class taxonomy | PASS |
| `test_compliance_analysis.py` | `test_compliance_analysis_workflow` | Full pipeline: upload $\rightarrow$ extract $\rightarrow$ rules $\rightarrow$ HITL | PASS |
| `test_extraction.py` | `test_us_qm_note_extraction` | Numerical extraction of US QM terms & provenance | PASS |
| `test_extraction.py` | `test_in_housing_loan_extraction` | Extraction of Indian housing loan terms & fees | PASS |
| `test_hmda_analytics.py` | `test_hmda_analytics_computation` | HMDA mean, median, approval ratio calculation | PASS |
| `test_retrieval.py` | `test_hybrid_search_jurisdiction_isolation` | Zero leakage between US Reg Z and RBI circulars | PASS |
| `test_rule_engine.py` | `test_us_atr_qm_points_fees_rule` | Mathematical 3.00% QM points/fees ceiling | PASS |
| `test_rule_engine.py` | `test_us_prepayment_penalty_arm_rule` | 12 CFR 1026.43(g) ARM prepayment ban | PASS |
| `test_rule_engine.py` | `test_in_rbi_foreclosure_ban_rule` | RBI DBOD 107 floating rate foreclosure ban | PASS |
| `test_rule_engine.py` | `test_in_rbi_penal_charges_rule` | RBI Fair Lending penal interest non-compounding | PASS |

---

## 2. Benchmark Evaluation Scripts

In addition to pytest, the platform includes 3 reproducible standalone evaluation scripts that run against dedicated benchmark corpora in `data/benchmark/`:

### 2.1 Loan Term Extraction Benchmark (`scripts/evaluate_extraction.py`)
- **Benchmark Corpus:** `data/benchmark/extraction_benchmark.json` (4 curated authentic loan documents across US and IN jurisdictions).
- **Evaluation Criteria:** Compares extracted numerical and boolean terms against ground-truth values within specified error tolerances ($\pm 0.5\%$, $\pm \$5,000$).
- **Command:**
  ```bash
  python scripts/evaluate_extraction.py
  ```
- **Results:**
  ```
  Total test cases   : 4
  Total fields tested: 15
  Fields correct     : 15
  Fields missing     : 0
  Fields wrong       : 0
  Field accuracy     : 100.0% (PASS >= 50.0%)
  ```

### 2.2 Hybrid Retrieval Benchmark (`scripts/evaluate_retrieval.py`)
- **Benchmark Corpus:** `data/benchmark/retrieval_benchmark.json` (4 statutory queries targeting specific legal provisions in CFPB Reg Z and RBI Directives).
- **Evaluation Criteria:** Evaluates Recall@5 and Precision@1 by verifying that retrieved clauses contain the expected statutory citations.
- **Command:**
  ```bash
  python scripts/evaluate_retrieval.py
  ```
- **Results:**
  ```
  Total queries evaluated : 4
  Queries passing recall  : 3
  Overall Recall@5        : 75.0% (PASS >= 50.0%)
  Precision@1             : 50.0%
  ```

### 2.3 Deterministic Compliance Rule Benchmark (`scripts/evaluate_compliance.py`)
- **Benchmark Cases:** 7 deterministic rule evaluation scenarios covering both compliant and violating mortgage terms.
- **Evaluation Criteria:** Compares rule engine outcomes (`NO_ISSUE_IDENTIFIED` vs `POTENTIAL_ISSUE`) against statutory ground-truth.
- **Command:**
  ```bash
  python scripts/evaluate_compliance.py
  ```
- **Results:**
  ```
  Total rule checks evaluated : 7
  Checks matching ground-truth: 7
  Deterministic Rule Precision: 100.0% (PASS)
  ```

---

## 3. Statutory Rule Engine Verification Matrix

| Rule ID | Regulatory Authority | Statute / Directive | Test Scenario | Evaluated Terms | Expected Outcome | Verified Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `US-REGZ-ATR-001` | CFPB | 12 CFR § 1026.43(e)(3) | Compliant QM Note | Points & Fees = 1.20%, Loan = $350k | `NO_ISSUE_IDENTIFIED` | **PASS** |
| `US-REGZ-ATR-001` | CFPB | 12 CFR § 1026.43(e)(3) | Non-Compliant Note | Points & Fees = 4.11%, Loan = $280k | `POTENTIAL_ISSUE` (Critical) | **PASS** |
| `US-REGZ-PPP-002` | CFPB | 12 CFR § 1026.43(g) | ARM Prepayment Penalty | Rate Type = variable, Prepay = True | `POTENTIAL_ISSUE` (Critical) | **PASS** |
| `IN-RBI-PPP-001` | RBI | DBOD.No.Dir.BC.107 | Floating Home Loan | Borrower = individual, Rate = variable, Prepay = False | `NO_ISSUE_IDENTIFIED` | **PASS** |
| `IN-RBI-PPP-001` | RBI | DBOD.No.Dir.BC.107 | Illegal Foreclosure Fee | Borrower = individual, Rate = variable, Prepay = True | `POTENTIAL_ISSUE` (Critical) | **PASS** |
| `IN-RBI-PENAL-002` | RBI | DoR.MCS.REC.28/2023-24 | Compounding Penalty | Penal Charges Compound = True | `POTENTIAL_ISSUE` (High) | **PASS** |
| `IN-RBI-PENAL-002` | RBI | DoR.MCS.REC.28/2023-24 | Simple Penal Charge | Penal Charges Compound = False | `NO_ISSUE_IDENTIFIED` | **PASS** |
| `IN-RBI-LTV-003` | RBI | Master Circular Housing | Compliant LTV | Loan = 45L, Value = 60L (LTV 75%) | `NO_ISSUE_IDENTIFIED` | **PASS** |

---

## 4. Grounding & Anti-Hallucination Controls

To guarantee that findings are grounded in authentic law:
1. **Verbatim Text Anchoring:** The retrieval pipeline requires that each finding cites an exact section code, chunk ID, and page number from the stored regulatory corpus.
2. **Deterministic Precedence:** Statutory limits (such as the 3.00% cap or foreclosure fee bans) are evaluated deterministically in Python code before any LLM generates narrative explanations.
3. **Prompt Injection Sanitization:** User-uploaded contract text is sanitized to neutralize prompt injection phrases before being passed to reasoning layers.
4. **Mandatory Disclaimer Encasement:** All generated PDF certificates and API findings explicitly state that the absence of a violation does not constitute a warranty of legal compliance.
