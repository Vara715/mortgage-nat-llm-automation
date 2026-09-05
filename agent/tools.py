"""
tools.py
========

Four NeMo Agent Toolkit (NAT) tools for the mortgage policy Q&A agent:

  - policy_retriever   : keyword-overlap search over the curated policy/FAQ
                          chunks in data/clean_mortgage_data.jsonl
  - emi_calculator      : computes a home-loan EMI from principal, annual rate,
                           and tenure in years
  - eligibility_advisor : "Counterfactual Eligibility Advisor" — checks FOIR-based
                           eligibility and, if the applicant doesn't qualify,
                           computes the minimal change (income, tenure, or loan
                           amount) that WOULD qualify them
  - prepayment_advisor  : "Proactive Prepayment Advisor" — given a one-time extra
                           payment, computes interest saved and tenure shortened

Every tool call is also appended to logs/audit_log.jsonl via audit_logger.py —
a starter implementation of the deck's "Compliance Black-Box Recorder" concept
(see that module's docstring for what it does and doesn't cover yet).

All four are registered with NAT's plugin system via @register_function, per
NAT's "Writing Custom Functions" guide. NAT auto-discovers these when this
module is imported from your project's entry point (see README.md, Step 4).
"""

import json
import math
import re
from pathlib import Path

from pydantic import BaseModel, Field

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from agent.audit_logger import log_tool_call

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "clean_mortgage_data.jsonl"

_STOPWORDS = {
    "the", "a", "an", "is", "are", "do", "does", "i", "my", "for", "to", "of",
    "in", "on", "and", "or", "what", "how", "can", "need", "you", "your",
    "me", "it", "if", "be", "with", "at", "as",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


# ---------------------------------------------------------------------------
# Shared EMI math (used by emi_calculator, eligibility_advisor, prepayment_advisor)
# ---------------------------------------------------------------------------


def _emi(principal: float, annual_rate_percent: float, tenure_years: float) -> tuple[float, int, float]:
    """Returns (emi, n_months, monthly_rate)."""
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
# Tool 1: policy_retriever
# ---------------------------------------------------------------------------


class PolicyRetrieverConfig(FunctionBaseConfig, name="policy_retriever"):
    data_path: str = Field(
        default=str(DEFAULT_DATA_PATH),
        description="Path to the curated JSONL produced by curator/clean_pipeline.py",
    )
    top_k: int = Field(default=3, description="Number of chunks to return", ge=1, le=10)


class PolicyRetrieverInput(BaseModel):
    query: str = Field(..., description="The user's mortgage-policy question")


@register_function(config_type=PolicyRetrieverConfig, framework_wrappers=[LLMFrameworkEnum.LANGCHAIN])
async def policy_retriever(config: PolicyRetrieverConfig, builder: Builder):
    data_path = Path(config.data_path)
    if not data_path.exists():
        raise FileNotFoundError(
            f"{data_path} not found — run `python3 curator/clean_pipeline.py` first."
        )

    corpus = []
    with data_path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            corpus.append({"id": row["id"], "text": row["text"], "tokens": _tokenize(row["text"])})

    async def _retrieve(query: str) -> str:
        q_tokens = _tokenize(query)
        if not q_tokens:
            result = "No results — please rephrase the question."
            log_tool_call("policy_retriever", {"query": query}, result)
            return result

        scored = []
        for doc in corpus:
            overlap = len(q_tokens & doc["tokens"])
            if overlap > 0:
                scored.append((overlap, doc))
        scored.sort(key=lambda x: x[0], reverse=True)

        top = scored[: config.top_k]
        if not top:
            result = "No matching policy content found for this query."
            log_tool_call("policy_retriever", {"query": query}, result)
            return result

        result = "\n\n---\n\n".join(f"[{doc['id']}] {doc['text']}" for _, doc in top)
        log_tool_call("policy_retriever", {"query": query}, result)
        return result

    yield FunctionInfo.from_fn(
        _retrieve,
        input_schema=PolicyRetrieverInput,
        description=(
            "Searches the curated mortgage policy and FAQ text for content relevant "
            "to a question. Use this for any question about eligibility, CIBIL score, "
            "documents required, interest rates, LTV, tenure, fees, or prepayment rules. "
            "Does NOT know about any specific customer's application status."
        ),
    )


# ---------------------------------------------------------------------------
# Tool 2: emi_calculator
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
        description=(
            "Calculates the monthly EMI (Equated Monthly Installment) for a home loan "
            "given the principal amount, annual interest rate in percent, and tenure in years. "
            "Use this whenever the user asks to calculate or estimate an EMI."
        ),
    )


# ---------------------------------------------------------------------------
# Tool 3: eligibility_advisor  ("Counterfactual Eligibility Advisor")
# ---------------------------------------------------------------------------


class EligibilityAdvisorConfig(FunctionBaseConfig, name="eligibility_advisor"):
    foir_limit_percent: float = Field(
        default=50.0,
        description="Max allowed Fixed Obligation to Income Ratio, as a percent",
    )
    max_tenure_years: float = Field(default=30.0, description="Policy maximum loan tenure in years")


class EligibilityAdvisorInput(BaseModel):
    monthly_income: float = Field(..., description="Applicant's gross monthly income in rupees", gt=0)
    existing_monthly_emi: float = Field(
        default=0, description="Applicant's existing EMI/loan obligations per month in rupees", ge=0
    )
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

        # Option A — extra income needed at current EMI
        income_needed = total_obligation / foir_limit
        lines.append(f"  - Increase monthly income by Rs. {income_needed - monthly_income:,.2f}, OR")

        # Option B — extra tenure needed, if achievable within policy max tenure
        if max_emi_allowed > r * requested_principal > 0:
            n_needed = math.log(max_emi_allowed / (max_emi_allowed - r * requested_principal)) / math.log(1 + r)
            years_needed = n_needed / 12
            if years_needed <= config.max_tenure_years:
                extra_years = years_needed - requested_tenure_years
                lines.append(f"  - Extend tenure by about {extra_years:.1f} years, OR")

        # Option C — reduce loan amount
        if max_emi_allowed > 0:
            f = (1 + r) ** n_months
            p_max = max_emi_allowed * (f - 1) / (r * f)
            lines.append(f"  - Reduce the loan amount by about Rs. {requested_principal - p_max:,.2f}")

        result = "\n".join(lines)
        log_tool_call(
            "eligibility_advisor",
            {
                "monthly_income": monthly_income,
                "existing_monthly_emi": existing_monthly_emi,
                "requested_principal": requested_principal,
                "annual_rate_percent": annual_rate_percent,
                "requested_tenure_years": requested_tenure_years,
            },
            result,
        )
        return result

    yield FunctionInfo.from_fn(
        _advise,
        input_schema=EligibilityAdvisorInput,
        description=(
            "Checks home loan eligibility using the FOIR (Fixed Obligation to Income Ratio) rule "
            "given monthly income, existing EMI obligations, and the requested loan's principal, "
            "rate, and tenure. If the applicant is NOT eligible, returns the smallest changes "
            "(extra income, extra tenure, or reduced loan amount) that would make them eligible, "
            "instead of just a flat rejection. Use this for any eligibility-check or "
            "'can I afford/qualify for' style question with concrete numbers."
        ),
    )


# ---------------------------------------------------------------------------
# Tool 4: prepayment_advisor  ("Proactive Prepayment Advisor")
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
        log_tool_call(
            "prepayment_advisor",
            {
                "principal": principal,
                "annual_rate_percent": annual_rate_percent,
                "tenure_years": tenure_years,
                "months_elapsed": months_elapsed,
                "extra_payment": extra_payment,
            },
            result,
        )
        return result

    yield FunctionInfo.from_fn(
        _advise,
        input_schema=PrepaymentAdvisorInput,
        description=(
            "Given an existing loan (principal, rate, tenure, months already paid) and a "
            "one-time extra/prepayment amount, calculates how much interest is saved and "
            "how many months the loan tenure is shortened by, keeping the EMI unchanged. "
            "Use this for any 'what if I pay extra' or prepayment-benefit question."
        ),
    )

