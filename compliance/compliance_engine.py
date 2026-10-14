"""
compliance_engine.py
====================
Core Regulatory Compliance Engine for TCS Mortgage Loan Compliance System (Slide 2 & 8):
- Queries HybridRegulatoryRetriever with extracted loan parameters
- Reasons over compliance against statutory RBI Circulars & Master Directions
- Generates structured ClauseCheckResult and full ComplianceAuditReport with alerting & remediation
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from compliance.loan_parser import ExtractedLoanTerms
from kb.retriever import HybridRegulatoryRetriever, RetrievalResult


class ClauseCheckResult(BaseModel):
    check_name: str
    status: str = Field(..., description="'COMPLIANT', 'NON_COMPLIANT', 'WARNING', or 'NOT_APPLICABLE'")
    extracted_value: Any
    regulatory_threshold: str
    regulatory_citation: str
    violation_reason: Optional[str] = None
    recommended_remediation: Optional[str] = None
    retrieved_clauses: List[str] = Field(default_factory=list)


class ComplianceAuditReport(BaseModel):
    document_name: str
    document_type: str
    borrower_type: str
    overall_status: str = Field(..., description="'COMPLIANT', 'NON_COMPLIANT', or 'WARNING'")
    total_checks: int
    violations_count: int
    warnings_count: int
    clause_results: List[ClauseCheckResult]
    executive_summary: str
    actionable_recommendations: List[str]


class ComplianceEngine:
    """
    Evaluates extracted loan agreements and application parameters against
    real-world RBI regulations and generates structured audit reports.
    """

    def __init__(self, retriever: HybridRegulatoryRetriever):
        self.retriever = retriever

    def audit_loan_terms(self, terms: ExtractedLoanTerms) -> ComplianceAuditReport:
        checks: List[ClauseCheckResult] = []

        # -------------------------------------------------------------
        # Check 1: Prepayment & Foreclosure Charges on Floating Rate Loans
        # -------------------------------------------------------------
        prepay_results = self.retriever.retrieve(
            query="levy of foreclosure charges pre-payment penalty floating rate home loan individual borrower",
            top_k=2,
            category="Prepayment & Foreclosure",
        )
        prepay_citation = (
            prepay_results[0].citation if prepay_results
            else "RBI Circular DBOD.No.Dir.BC.107/13.03.00/2011-12"
        )
        prepay_context = [r.text for r in prepay_results]

        if terms.borrower_type == "individual" and terms.interest_rate_type == "floating":
            if terms.has_prepayment_penalty or (terms.prepayment_charges_rate_percent and terms.prepayment_charges_rate_percent > 0):
                rate_str = f"{terms.prepayment_charges_rate_percent}%" if terms.prepayment_charges_rate_percent else "applicable charges"
                checks.append(
                    ClauseCheckResult(
                        check_name="Prepayment & Foreclosure Charges",
                        status="NON_COMPLIANT",
                        extracted_value=f"Levies {rate_str} foreclosure fee on floating-rate individual loan",
                        regulatory_threshold="0% (Strict prohibition on foreclosure/prepayment charges for floating rate home loans to individuals)",
                        regulatory_citation=prepay_citation,
                        violation_reason=(
                            f"The agreement levies prepayment charges ({rate_str}) on a floating-rate home loan "
                            f"to an individual borrower. Under RBI circular DBOD.No.Dir.BC.107/13.03.00/2011-12, "
                            f"banks are strictly prohibited from levying foreclosure charges or pre-payment penalties on such loans."
                        ),
                        recommended_remediation=(
                            "Amend Section/Clause on Prepayment to: 'No foreclosure charges or pre-payment penalties "
                            "shall be levied on floating-rate home loans sanctioned to individual borrowers.'"
                        ),
                        retrieved_clauses=prepay_context,
                    )
                )
            else:
                checks.append(
                    ClauseCheckResult(
                        check_name="Prepayment & Foreclosure Charges",
                        status="COMPLIANT",
                        extracted_value="Zero foreclosure charges on floating-rate individual loan",
                        regulatory_threshold="0% foreclosure fee permitted",
                        regulatory_citation=prepay_citation,
                        retrieved_clauses=prepay_context,
                    )
                )
        else:
            # Corporate or fixed-rate loan where prepayment fee is legally permissible
            checks.append(
                ClauseCheckResult(
                    check_name="Prepayment & Foreclosure Charges",
                    status="COMPLIANT",
                    extracted_value=f"{terms.borrower_type.title()} borrower / {terms.interest_rate_type} rate",
                    regulatory_threshold="Permitted for corporate borrowers or purely fixed-rate facilities",
                    regulatory_citation=prepay_citation,
                    retrieved_clauses=prepay_context,
                )
            )

        # -------------------------------------------------------------
        # Check 2: Penal Interest Compounding & Capitalisation
        # -------------------------------------------------------------
        penal_results = self.retriever.retrieve(
            query="penal charges default interest compounding capitalised loan accounts",
            top_k=2,
            category="Regulatory Penalties",
        )
        penal_citation = (
            penal_results[0].citation if penal_results
            else "RBI Circular DoR.MCS.REC.28/01.01.001/2023-24 (Fair Lending Practice)"
        )
        penal_context = [r.text for r in penal_results]

        if terms.is_penal_interest_compounded:
            checks.append(
                ClauseCheckResult(
                    check_name="Penal Charges & Default Interest",
                    status="NON_COMPLIANT",
                    extracted_value="Penal interest is compounded or capitalised into principal",
                    regulatory_threshold="Compounding strictly prohibited; must be simple 'penal charges'",
                    regulatory_citation=penal_citation,
                    violation_reason=(
                        "The contract specifies compounding or capitalisation of penal interest. Under RBI's "
                        "Fair Lending Practice directives, penalty for default must be recovered as separate "
                        "penal charges and CANNOT be compounded or added to the principal balance."
                    ),
                    recommended_remediation=(
                        "Amend Default/Penal clause to: 'Penal charges for late payment shall be levied on a simple interest basis "
                        "and shall not be compounded or capitalised into the loan balance.'"
                    ),
                    retrieved_clauses=penal_context,
                )
            )
        else:
            checks.append(
                ClauseCheckResult(
                    check_name="Penal Charges & Default Interest",
                    status="COMPLIANT",
                    extracted_value=f"Simple penal charges ({terms.penal_charge_rate_percent or 2}% without compounding)",
                    regulatory_threshold="Simple penal charges only, no compounding",
                    regulatory_citation=penal_citation,
                    retrieved_clauses=penal_context,
                )
            )

        # -------------------------------------------------------------
        # Check 3: Loan to Value (LTV) Cap
        # -------------------------------------------------------------
        ltv_results = self.retriever.retrieve(
            query="loan to value LTV ratio caps margin limits housing finance",
            top_k=2,
            category="LTV & Margin Norms",
        )
        ltv_citation = (
            ltv_results[0].citation if ltv_results
            else "RBI Master Directions on Housing Loans LTV & Margin Norms"
        )
        ltv_context = [r.text for r in ltv_results]

        if terms.loan_type == "housing_loan" and terms.ltv_percent:
            amount = terms.sanctioned_amount or 5000000.0  # default 50L if unspecified
            if amount <= 3000000:
                max_ltv = 90.0
            elif amount <= 7500000:
                max_ltv = 80.0
            else:
                max_ltv = 75.0

            if terms.ltv_percent > max_ltv:
                checks.append(
                    ClauseCheckResult(
                        check_name="Loan-to-Value (LTV) Ratio",
                        status="NON_COMPLIANT",
                        extracted_value=f"{terms.ltv_percent:.1f}% LTV on Rs. {amount:,.0f} loan",
                        regulatory_threshold=f"Max {max_ltv:.0f}% LTV for this loan slab",
                        regulatory_citation=ltv_citation,
                        violation_reason=(
                            f"The proposed LTV ratio ({terms.ltv_percent:.1f}%) exceeds the statutory RBI ceiling "
                            f"of {max_ltv:.0f}% for loans in this quantum tier (sanctioned amount: Rs. {amount:,.0f})."
                        ),
                        recommended_remediation=(
                            f"Increase borrower margin contribution by Rs. "
                            f"{((terms.ltv_percent - max_ltv) / 100 * (terms.property_value or (amount / (terms.ltv_percent / 100)))):,.0f} "
                            f"to reduce LTV to {max_ltv:.0f}% or lower."
                        ),
                        retrieved_clauses=ltv_context,
                    )
                )
            else:
                checks.append(
                    ClauseCheckResult(
                        check_name="Loan-to-Value (LTV) Ratio",
                        status="COMPLIANT",
                        extracted_value=f"{terms.ltv_percent:.1f}% LTV (Limit: {max_ltv:.0f}%)",
                        regulatory_threshold=f"Max {max_ltv:.0f}% LTV",
                        regulatory_citation=ltv_citation,
                        retrieved_clauses=ltv_context,
                    )
                )
        else:
            checks.append(
                ClauseCheckResult(
                    check_name="Loan-to-Value (LTV) Ratio",
                    status="NOT_APPLICABLE",
                    extracted_value=f"LTV not specified or {terms.loan_type}",
                    regulatory_threshold="LTV caps apply to retail individual housing loans",
                    regulatory_citation=ltv_citation,
                    retrieved_clauses=ltv_context,
                )
            )

        # -------------------------------------------------------------
        # Check 4: NRI Lending & Intermediary Verification (Slide 6)
        # -------------------------------------------------------------
        nri_results = self.retriever.retrieve(
            query="granting loans Non-Resident Indians NRI housing intermediary agencies",
            top_k=2,
            category="NRI Financing",
        )
        nri_citation = (
            nri_results[0].citation if nri_results
            else "RBI Master Circular - Housing Finance, Section 3.2.4"
        )
        nri_context = [r.text for r in nri_results]

        if terms.has_nri_borrower:
            checks.append(
                ClauseCheckResult(
                    check_name="NRI Lending & Authorization Compliance",
                    status="WARNING",
                    extracted_value="NRI borrower or intermediary on-lending detected",
                    regulatory_threshold="Intermediary must possess specific RBI authorization for NRI lending",
                    regulatory_citation=nri_citation,
                    violation_reason=None,
                    recommended_remediation=(
                        "Verify and file proof that the intermediary/originating agency holds valid RBI authorization "
                        "to grant housing loans to NRIs per Section 3.2.4(ii) of the Master Circular."
                    ),
                    retrieved_clauses=nri_context,
                )
            )
        else:
            checks.append(
                ClauseCheckResult(
                    check_name="NRI Lending & Authorization Compliance",
                    status="COMPLIANT",
                    extracted_value="Standard domestic resident borrower",
                    regulatory_threshold="Standard domestic KYC & underwriting",
                    regulatory_citation=nri_citation,
                    retrieved_clauses=nri_context,
                )
            )

        # -------------------------------------------------------------
        # Check 5: Key Facts Statement (KFS) & Grievance Redressal
        # -------------------------------------------------------------
        kfs_results = self.retriever.retrieve(
            query="Key Facts Statement KFS grievance redressal nodal officer",
            top_k=2,
            category="Fair Practices Code",
        )
        kfs_citation = kfs_results[0].citation if kfs_results else "RBI Fair Lending Guidelines (KFS)"
        kfs_context = [r.text for r in kfs_results]

        if not terms.grievance_clause_present:
            checks.append(
                ClauseCheckResult(
                    check_name="Grievance Redressal & Nodal Officer Disclosure",
                    status="WARNING",
                    extracted_value="No specific nodal officer grievance details identified in document body",
                    regulatory_threshold="Mandatory disclosure of Principal Nodal Officer contact details",
                    regulatory_citation=kfs_citation,
                    violation_reason="RBI guidelines mandate prominent disclosure of nodal grievance officer details in all loan agreements.",
                    recommended_remediation="Append Part 2 of KFS containing Nodal Grievance Redressal Officer contact phone and email.",
                    retrieved_clauses=kfs_context,
                )
            )
        else:
            checks.append(
                ClauseCheckResult(
                    check_name="Grievance Redressal & Nodal Officer Disclosure",
                    status="COMPLIANT",
                    extracted_value="Grievance redressal mechanism identified",
                    regulatory_threshold="Mandatory disclosure of grievance officer",
                    regulatory_citation=kfs_citation,
                    retrieved_clauses=kfs_context,
                )
            )

        # Compute overall status
        violations = sum(1 for c in checks if c.status == "NON_COMPLIANT")
        warnings = sum(1 for c in checks if c.status == "WARNING")

        if violations > 0:
            overall_status = "NON_COMPLIANT"
            exec_summary = (
                f"AUDIT FAILED: {violations} regulatory violation(s) identified in {terms.document_name}. "
                f"Immediate contractual remediation required before loan execution or disbursement."
            )
        elif warnings > 0:
            overall_status = "WARNING"
            exec_summary = (
                f"AUDIT PASSED WITH WARNINGS: 0 statutory violations, but {warnings} advisory item(s) "
                f"require documentation or verification in {terms.document_name}."
            )
        else:
            overall_status = "COMPLIANT"
            exec_summary = (
                f"AUDIT PASSED: {terms.document_name} complies with all evaluated RBI mortgage guidelines and directives."
            )

        recs = [c.recommended_remediation for c in checks if c.recommended_remediation]

        return ComplianceAuditReport(
            document_name=terms.document_name,
            document_type=terms.document_type,
            borrower_type=terms.borrower_type,
            overall_status=overall_status,
            total_checks=len(checks),
            violations_count=violations,
            warnings_count=warnings,
            clause_results=checks,
            executive_summary=exec_summary,
            actionable_recommendations=recs,
        )
