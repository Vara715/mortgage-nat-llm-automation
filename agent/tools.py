"""
tools.py
========
NeMo Agent Toolkit (NAT) tools for the TCS Mortgage Loan Compliance System:

  - policy_retriever         : High-performance hybrid BM25 + vector search over
                                real RBI regulatory circulars and mortgage policies
  - compliance_checker       : Automated regulatory compliance engine auditing loan
                                agreements against RBI mandates (prepayment penalties,
                                penal interest compounding, LTV caps, NRI lending)
  - loan_agreement_analyzer  : Classifies document type and extracts key legal/financial
                                parameters from loan contracts or Key Facts Statements
  - emi_calculator           : Precision reducing-balance home loan EMI calculator
  - eligibility_advisor      : Counterfactual FOIR eligibility advisor
  - prepayment_advisor       : Proactive prepayment advisor computing interest savings

Every tool call is appended to logs/audit_log.jsonl via audit_logger.py.
"""

import json
import math
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from agent.audit_logger import log_tool_call
from kb.storage import RegulatoryKnowledgeStore
from kb.retriever import HybridRegulatoryRetriever
from compliance.loan_parser import LoanDocumentParser
from compliance.compliance_engine import ComplianceEngine
from compliance.alerting import format_alert_summary
from extraction.pdf_extractor import PDFExtractor

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "clean_mortgage_data.jsonl"
DEFAULT_DB_PATH = BASE_DIR / "data" / "knowledge_base" / "regulatory_knowledge.db"


# ---------------------------------------------------------------------------
# Lazy-loaded singleton knowledge store & retriever
# ---------------------------------------------------------------------------
_STORE: Optional[RegulatoryKnowledgeStore] = None
_RETRIEVER: Optional[HybridRegulatoryRetriever] = None


def get_retriever() -> HybridRegulatoryRetriever:
    global _STORE, _RETRIEVER
    if _RETRIEVER is None:
        if not DEFAULT_DB_PATH.exists():
            # Run quick initialization if db doesn't exist yet
            from pipeline import run_pipeline
            run_pipeline()
        _STORE = RegulatoryKnowledgeStore(db_path=DEFAULT_DB_PATH)
        _RETRIEVER = HybridRegulatoryRetriever(store=_STORE)
    return _RETRIEVER


# ---------------------------------------------------------------------------
# Shared EMI math
# ---------------------------------------------------------------------------
def _emi(principal: float, annual_rate_percent: float, tenure_years: float) -> tuple[float, int, float]:
    r = (annual_rate_percent / 12) / 100
    n = round(tenure_years * 12)
    if r == 0:
        return principal / n, n, r
    f = (1 + r) ** n
    return principal * r * f / (f - 1), n, r


def _outstanding_balance(principal: float, r: float, n_months: int, months_elapsed: int) -> float:
    if r == 0:
        return principal * (1 - months_elapsed / n_months)
    return principal * ((1 + r) ** n_months - (1 + r) ** months_elapsed) / ((1 + r) ** n_months - 1)


# ---------------------------------------------------------------------------
# Tool 1: policy_retriever (Enhanced Hybrid Regulatory Retriever)
# ---------------------------------------------------------------------------
class PolicyRetrieverConfig(FunctionBaseConfig, name="policy_retriever"):
    top_k: int = Field(default=3, description="Number of regulatory clauses to return", ge=1, le=10)


class PolicyRetrieverInput(BaseModel):
    query: str = Field(..., description="The user's question regarding mortgage policies or RBI regulations")
    category: Optional[str] = Field(
        default=None,
        description="Optional regulatory category: 'Prepayment & Foreclosure', 'Regulatory Penalties', 'LTV & Margin Norms', 'NRI Financing', 'Eligibility', 'Fair Practices Code'",
    )


@register_function(config_type=PolicyRetrieverConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def policy_retriever(config: PolicyRetrieverConfig, builder: Builder):
    retriever = get_retriever()

    async def _retrieve(query: str, category: Optional[str] = None) -> str:
        results = retriever.retrieve(query=query, top_k=config.top_k, category=category)
        if not results:
            result = "No matching regulatory policy found for this query in the knowledge base."
            log_tool_call("policy_retriever", {"query": query, "category": category}, result)
            return result

        formatted_pieces = []
        for r in results:
            piece = (
                f"[{r.citation}] (Category: {r.category}, Score: {r.score})\n"
                f"{r.text}"
            )
            formatted_pieces.append(piece)

        result = "\n\n---\n\n".join(formatted_pieces)
        log_tool_call("policy_retriever", {"query": query, "category": category}, result)
        return result

    yield FunctionInfo.from_fn(
        _retrieve,
        input_schema=PolicyRetrieverInput,
        description=(
            "Searches the authentic RBI regulatory database and mortgage policy repository. "
            "Use this for any question about RBI guidelines, prepayment penalties, foreclosure fee bans, "
            "penal interest compounding restrictions, LTV caps, NRI lending conditions, CIBIL requirements, "
            "and Fair Practices Code. Does NOT know about private individual loan application statuses."
        ),
    )


# ---------------------------------------------------------------------------
# Tool 2: compliance_checker (TCS Mortgage Loan Compliance Engine)
# ---------------------------------------------------------------------------
class ComplianceCheckerConfig(FunctionBaseConfig, name="compliance_checker"):
    pass


class ComplianceCheckerInput(BaseModel):
    loan_text_or_path: str = Field(
        ...,
        description="Raw text of the loan agreement clauses OR local file path to the loan agreement (.pdf or .txt)",
    )


@register_function(config_type=ComplianceCheckerConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def compliance_checker(config: ComplianceCheckerConfig, builder: Builder):
    retriever = get_retriever()
    engine = ComplianceEngine(retriever=retriever)
    parser = LoanDocumentParser()
    pdf_extractor = PDFExtractor(enable_visual_debugging=False)

    async def _audit(loan_text_or_path: str) -> str:
        text = loan_text_or_path
        doc_name = "User_Submitted_Loan_Agreement"

        # Check if input is a file path
        path_candidate = Path(loan_text_or_path.strip().strip('"').strip("'"))
        if path_candidate.exists() and path_candidate.is_file():
            doc_name = path_candidate.name
            if path_candidate.suffix.lower() == ".pdf":
                doc = pdf_extractor.extract(path_candidate)
                text = doc.full_text
            else:
                text = path_candidate.read_text(encoding="utf-8", errors="ignore")

        terms = parser.parse_text(text, document_name=doc_name)
        report = engine.audit_loan_terms(terms)
        result = format_alert_summary(report)
        log_tool_call("compliance_checker", {"document": doc_name, "length": len(text)}, result)
        return result

    yield FunctionInfo.from_fn(
        _audit,
        input_schema=ComplianceCheckerInput,
        description=(
            "Audits a mortgage or commercial loan agreement against Reserve Bank of India (RBI) regulations. "
            "Evaluates prepayment penalty legality on floating rate loans, penal interest compounding prohibitions, "
            "Loan-to-Value (LTV) regulatory caps, NRI intermediary authorizations, and Key Facts Statement disclosures. "
            "Returns a structured audit report with citations, violations, and legal remediation recommendations. "
            "Accepts raw agreement text or a file path."
        ),
    )


# ---------------------------------------------------------------------------
# Tool 3: loan_agreement_analyzer (Document Classifier & Field Extractor)
# ---------------------------------------------------------------------------
class LoanAgreementAnalyzerConfig(FunctionBaseConfig, name="loan_agreement_analyzer"):
    pass


class LoanAgreementAnalyzerInput(BaseModel):
    loan_text_or_path: str = Field(
        ...,
        description="Raw text of the loan agreement OR path to the loan document (.pdf or .txt)",
    )


@register_function(config_type=LoanAgreementAnalyzerConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def loan_agreement_analyzer(config: LoanAgreementAnalyzerConfig, builder: Builder):
    parser = LoanDocumentParser()
    pdf_extractor = PDFExtractor(enable_visual_debugging=False)

    async def _analyze(loan_text_or_path: str) -> str:
        text = loan_text_or_path
        doc_name = "Analyzed_Document"

        path_candidate = Path(loan_text_or_path.strip().strip('"').strip("'"))
        if path_candidate.exists() and path_candidate.is_file():
            doc_name = path_candidate.name
            if path_candidate.suffix.lower() == ".pdf":
                doc = pdf_extractor.extract(path_candidate)
                text = doc.full_text
            else:
                text = path_candidate.read_text(encoding="utf-8", errors="ignore")

        terms = parser.parse_text(text, document_name=doc_name)
        result_lines = [
            f"Document Name       : {terms.document_name}",
            f"Document Type       : {terms.document_type}",
            f"Borrower Type       : {terms.borrower_type.title()}",
            f"Loan Type           : {terms.loan_type}",
            f"Sanctioned Amount   : Rs. {terms.sanctioned_amount:,.2f}" if terms.sanctioned_amount else "Sanctioned Amount   : Not specified",
            f"Property Value      : Rs. {terms.property_value:,.2f}" if terms.property_value else "Property Value      : Not specified",
            f"LTV Ratio           : {terms.ltv_percent:.1f}%" if terms.ltv_percent else "LTV Ratio           : Not specified",
            f"Interest Rate       : {terms.interest_rate_percent}% ({terms.interest_rate_type.title()})" if terms.interest_rate_percent else f"Interest Rate Type  : {terms.interest_rate_type.title()}",
            f"Tenure              : {terms.tenure_years} years" if terms.tenure_years else "Tenure              : Not specified",
            f"Prepayment Clause   : {terms.prepayment_clause_text[:150]}..." if terms.prepayment_clause_text else "Prepayment Clause   : None found",
            f"Has Prepayment Fee  : {'YES' if terms.has_prepayment_penalty else 'NO'}",
            f"Penal Interest      : {terms.penal_charges_clause_text[:150]}..." if terms.penal_charges_clause_text else "Penal Clause        : None found",
            f"Penal Compounding   : {'YES (Compounded)' if terms.is_penal_interest_compounded else 'NO (Simple)'}",
            f"NRI Borrower Clause : {'YES' if terms.has_nri_borrower else 'NO'}",
            f"KFS Disclosures     : {'Present' if terms.kfs_schedule_present else 'Missing'}",
        ]
        result = "\n".join(result_lines)
        log_tool_call("loan_agreement_analyzer", {"document": doc_name}, result)
        return result

    yield FunctionInfo.from_fn(
        _analyze,
        input_schema=LoanAgreementAnalyzerInput,
        description=(
            "Extracts key contractual terms and classifies document type from loan agreements, forms, or KFS schedules. "
            "Extracts interest rates, tenure, LTV ratios, prepayment fees, penal compounding terms, and NRI clauses."
        ),
    )


# ---------------------------------------------------------------------------
# Tool 4: emi_calculator
# ---------------------------------------------------------------------------
class EmiCalculatorConfig(FunctionBaseConfig, name="emi_calculator"):
    pass


class EmiCalculatorInput(BaseModel):
    principal: float = Field(..., description="Loan amount (principal) in rupees", gt=0)
    annual_rate_percent: float = Field(..., description="Annual interest rate, e.g. 8.75 for 8.75%", gt=0)
    tenure_years: float = Field(..., description="Loan tenure in years", gt=0)


@register_function(config_type=EmiCalculatorConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def emi_calculator(config: EmiCalculatorConfig, builder: Builder):
    async def _calculate(principal: float, annual_rate_percent: float, tenure_years: float) -> str:
        emi, n_months, _ = _emi(principal, annual_rate_percent, tenure_years)
        total_payment = emi * n_months
        total_interest = total_payment - principal

        result = (
            f"EMI: Rs. {emi:,.2f} per month\n"
            f"Number of installments: {n_months}\n"
            f"Total amount payable: Rs. {total_payment:,.2f}\n"
            f"Total interest payable: Rs. {total_interest:,.2f}"
        )
        log_tool_call(
            "emi_calculator",
            {"principal": principal, "annual_rate_percent": annual_rate_percent, "tenure_years": tenure_years},
            result,
        )
        return result

    yield FunctionInfo.from_fn(
        _calculate,
        input_schema=EmiCalculatorInput,
        description="Calculates the monthly EMI (Equated Monthly Installment) for a home loan.",
    )


# ---------------------------------------------------------------------------
# Tool 5: eligibility_advisor ("Counterfactual Eligibility Advisor")
# ---------------------------------------------------------------------------
class EligibilityAdvisorConfig(FunctionBaseConfig, name="eligibility_advisor"):
    foir_limit_percent: float = Field(default=50.0, description="Max allowed FOIR limit percent")
    max_tenure_years: float = Field(default=30.0, description="Policy maximum loan tenure in years")


class EligibilityAdvisorInput(BaseModel):
    monthly_income: float = Field(..., description="Applicant's gross monthly income in rupees", gt=0)
    existing_monthly_emi: float = Field(default=0, description="Existing monthly EMI obligations in rupees", ge=0)
    requested_principal: float = Field(..., description="Requested loan amount in rupees", gt=0)
    annual_rate_percent: float = Field(..., description="Annual interest rate, e.g. 8.75 for 8.75%", gt=0)
    requested_tenure_years: float = Field(..., description="Requested loan tenure in years", gt=0)


@register_function(config_type=EligibilityAdvisorConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def eligibility_advisor(config: EligibilityAdvisorConfig, builder: Builder):
    async def _advise(
        monthly_income: float,
        requested_principal: float,
        annual_rate_percent: float,
        requested_tenure_years: float,
        existing_monthly_emi: float = 0,
    ) -> str:
        foir_limit = config.foir_limit_percent / 100
        new_emi, n_months, r = _emi(requested_principal, annual_rate_percent, requested_tenure_years)
        total_obligation = existing_monthly_emi + new_emi
        foir = total_obligation / monthly_income

        lines = [
            f"Requested loan EMI: Rs. {new_emi:,.2f}/month",
            f"Total monthly obligation (existing + new): Rs. {total_obligation:,.2f}",
            f"FOIR: {foir*100:.1f}% (limit: {config.foir_limit_percent:.0f}%)",
        ]

        if foir <= foir_limit:
            lines.append("Eligible: YES — FOIR is within the policy limit.")
            result = "\n".join(lines)
            log_tool_call("eligibility_advisor", {"monthly_income": monthly_income, "requested_principal": requested_principal}, result)
            return result

        lines.append("Eligible: NO — FOIR exceeds the policy limit.")
        lines.append("")
        lines.append("Smallest changes that would make this loan eligible:")

        max_emi_allowed = monthly_income * foir_limit - existing_monthly_emi
        income_needed = total_obligation / foir_limit
        lines.append(f"  - Increase monthly income by Rs. {income_needed - monthly_income:,.2f}, OR")

        if max_emi_allowed > r * requested_principal > 0:
            n_needed = math.log(max_emi_allowed / (max_emi_allowed - r * requested_principal)) / math.log(1 + r)
            years_needed = n_needed / 12
            if years_needed <= config.max_tenure_years:
                extra_years = years_needed - requested_tenure_years
                lines.append(f"  - Extend tenure by about {extra_years:.1f} years, OR")

        if max_emi_allowed > 0:
            f = (1 + r) ** n_months
            p_max = max_emi_allowed * (f - 1) / (r * f)
            lines.append(f"  - Reduce the loan amount by about Rs. {requested_principal - p_max:,.2f}")

        result = "\n".join(lines)
        log_tool_call("eligibility_advisor", {"monthly_income": monthly_income, "requested_principal": requested_principal}, result)
        return result

    yield FunctionInfo.from_fn(
        _advise,
        input_schema=EligibilityAdvisorInput,
        description="Checks home loan eligibility using FOIR and computes minimal counterfactual changes if ineligible.",
    )


# ---------------------------------------------------------------------------
# Tool 6: prepayment_advisor ("Proactive Prepayment Advisor")
# ---------------------------------------------------------------------------
class PrepaymentAdvisorConfig(FunctionBaseConfig, name="prepayment_advisor"):
    pass


class PrepaymentAdvisorInput(BaseModel):
    principal: float = Field(..., description="Original loan principal in rupees", gt=0)
    annual_rate_percent: float = Field(..., description="Annual interest rate, e.g. 8.75 for 8.75%", gt=0)
    tenure_years: float = Field(..., description="Original loan tenure in years", gt=0)
    months_elapsed: int = Field(..., description="Number of EMIs already paid so far", ge=0)
    extra_payment: float = Field(..., description="One-time extra/prepayment amount in rupees", gt=0)


@register_function(config_type=PrepaymentAdvisorConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def prepayment_advisor(config: PrepaymentAdvisorConfig, builder: Builder):
    async def _advise(
        principal: float,
        annual_rate_percent: float,
        tenure_years: float,
        months_elapsed: int,
        extra_payment: float,
    ) -> str:
        emi, n_months, r = _emi(principal, annual_rate_percent, tenure_years)
        if months_elapsed >= n_months:
            result = "months_elapsed must be less than the total loan tenure in months."
            log_tool_call("prepayment_advisor", {"principal": principal, "months_elapsed": months_elapsed}, result)
            return result

        balance = _outstanding_balance(principal, r, n_months, months_elapsed)

        if extra_payment >= balance:
            result = (
                f"The outstanding balance is only Rs. {balance:,.2f} — this prepayment "
                f"would fully close the loan now."
            )
            log_tool_call("prepayment_advisor", {"principal": principal, "extra_payment": extra_payment}, result)
            return result

        new_balance = balance - extra_payment
        if emi <= r * new_balance:
            result = "This EMI is too small relative to the remaining balance and rate to compute a finite new tenure."
            log_tool_call("prepayment_advisor", {"principal": principal, "extra_payment": extra_payment}, result)
            return result

        n_new = math.log(emi / (emi - r * new_balance)) / math.log(1 + r)
        remaining_months_original = n_months - months_elapsed
        months_saved = remaining_months_original - n_new
        interest_saved = emi * remaining_months_original - (extra_payment + emi * n_new)

        result = (
            f"Outstanding balance before prepayment: Rs. {balance:,.2f}\n"
            f"EMI stays the same: Rs. {emi:,.2f}/month\n"
            f"Remaining tenure without prepayment: {remaining_months_original} months\n"
            f"Remaining tenure with this prepayment: ~{n_new:.1f} months\n"
            f"Tenure shortened by: ~{months_saved:.1f} months\n"
            f"Estimated interest saved: Rs. {interest_saved:,.2f}"
        )
        log_tool_call("prepayment_advisor", {"principal": principal, "extra_payment": extra_payment}, result)
        return result

    yield FunctionInfo.from_fn(
        _advise,
        input_schema=PrepaymentAdvisorInput,
        description="Calculates interest saved and tenure shortened given an extra prepayment amount.",
    )
