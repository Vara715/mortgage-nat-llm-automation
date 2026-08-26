"""
tools.py
========

Two NeMo Agent Toolkit (NAT) tools for the mortgage policy Q&A agent:

  - policy_retriever : keyword-overlap search over the curated policy/FAQ
                        chunks in data/clean_mortgage_data.jsonl
  - emi_calculator    : computes a home-loan EMI from principal, annual rate,
                         and tenure in years

Both are registered with NAT's plugin system via @register_function, per
NAT's "Writing Custom Functions" guide. NAT auto-discovers these when this
module is imported from your project's entry point (see README.md, Step 4).
"""

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

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
            return "No results — please rephrase the question."

        scored = []
        for doc in corpus:
            overlap = len(q_tokens & doc["tokens"])
            if overlap > 0:
                scored.append((overlap, doc))
        scored.sort(key=lambda x: x[0], reverse=True)

        top = scored[: config.top_k]
        if not top:
            return "No matching policy content found for this query."

        return "\n\n---\n\n".join(f"[{doc['id']}] {doc['text']}" for _, doc in top)

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
        monthly_rate = (annual_rate_percent / 12) / 100
        n_months = round(tenure_years * 12)

        if monthly_rate == 0:
            emi = principal / n_months
        else:
            factor = (1 + monthly_rate) ** n_months
            emi = principal * monthly_rate * factor / (factor - 1)

        total_payment = emi * n_months
        total_interest = total_payment - principal

        return (
            f"EMI: Rs. {emi:,.2f} per month\n"
            f"Number of installments: {n_months}\n"
            f"Total amount payable: Rs. {total_payment:,.2f}\n"
            f"Total interest payable: Rs. {total_interest:,.2f}"
        )

    yield FunctionInfo.from_fn(
        _calculate,
        input_schema=EmiCalculatorInput,
        description=(
            "Calculates the monthly EMI (Equated Monthly Installment) for a home loan "
            "given the principal amount, annual interest rate in percent, and tenure in years. "
            "Use this whenever the user asks to calculate or estimate an EMI."
        ),
    )
