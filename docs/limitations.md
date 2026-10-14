# System Limitations, Assumptions & Legal Scope

This document specifies the operational boundaries, regulatory assumptions, and limitations of **morgage-loan-automation**.

---

## 1. Decision-Support Nature & Non-Legal Advice

- **Automated Advisory Tool:** **morgage-loan-automation** is an automated decision-support backend system designed to assist licensed compliance analysts and legal officers. It does not provide legal advice, formal legal opinions, or certified regulatory warranties.
- **Absence of Violation Invariant:** A finding of `NO_ISSUE_IDENTIFIED` applies exclusively to the specific deterministic rules, regulatory sections, and extracted values evaluated during the run. The absence of a detected violation **does not prove or imply that a loan document is fully compliant** with all federal, state, or RBI laws.
- **Unregulated Contract Terms:** Mortgage loan contracts contain numerous commercial and covenants provisions (e.g., choice of law, force majeure, notice requirements, assignment clauses) that fall outside the statutory scope of Truth in Lending or RBI housing finance circulars. These clauses are not evaluated by the automated compliance engine.

---

## 2. Multi-Jurisdictional Scope Boundaries

- **Strict Corpus Segregation:** United States Truth in Lending regulations (12 CFR Part 1026) apply exclusively to consumer transactions secured by a dwelling within the US. Reserve Bank of India circulars apply exclusively to banking transactions in India. The two rule sets are never combined.
- **Unverified Jurisdictions:** Documents originating from other jurisdictions (such as the United Kingdom, European Union, or Canada) are not supported. If jurisdiction detection fails to identify US or India with high confidence, the system halts automated rule checks and marks the contract as `NEEDS_REVIEW`.

---

## 3. Public Mortgage Dataset (HMDA) Limitations

- **Disclosure Data vs. Compliance Proof:** Home Mortgage Disclosure Act (HMDA) records represent institutional statistical disclosures pursuant to Regulation C (12 CFR Part 1003). They are intended to detect discriminatory lending patterns and assess community housing credit needs.
- **Application Outcomes vs. Loan Performance:** Reported approval or origination of a loan in the HMDA dataset **does not establish that the loan complied with Regulation Z or RESPA**. Conversely, application denials do not establish statutory non-compliance.
- **Sample Size Caveat:** Development and demonstration environments utilize a curated subset (200 records) of authentic 2023 CFPB Loan Application Registers. While authentic, localized statistical inferences must consider sample size constraints.
- **Fair Lending Protections:** HMDA protected characteristics (e.g., race, ethnicity, sex) are never treated as permissible automatic grounds for adverse lending decisions.

---

## 4. Extraction & OCR Assumptions

- **High-Quality Digital Text:** Native PDF text extraction using `pdfplumber` yields high fidelity ($>95\%$) on standard uniform mortgage notes (e.g., Fannie Mae Form 3200).
- **Human Field Verification:** Scanned, photocopied, or degraded loan documents may introduce OCR noise. The system incorporates the **Human Review Queue (`/api/reviews/queue`) and n8n HITL Workflow** to allow compliance analysts to review, verify, and override extracted values before finalizing deterministic audits.
