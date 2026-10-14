"""
llm_explainer.py
================
Evidence-grounded explanation service for morgage-loan-automation.
- Calls configured LLM provider (Groq, OpenAI, NIM, or Ollama) when API keys are available
- Defends against prompt injection in mortgage contracts
- Synthesizes clear, plain-language legal explanations strictly grounded in retrieved statutory text
- Formulates targeted follow-up inquiries for human reviewers
- Gracefully falls back to deterministic template if offline or on network failure
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.core.security import sanitize_untrusted_text
from backend.app.schemas.compliance import RegulatoryEvidenceItem

logger = logging.getLogger("morgage-loan-automation.llm")


class LLMExplainerService:
    def __init__(self):
        self.provider = (settings.LLM_PROVIDER or "mock_or_env").lower()
        self.openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
        self.groq_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        self.nim_key = settings.NVIDIA_API_KEY or os.environ.get("NVIDIA_API_KEY")

        # Resolve model name
        configured_model = settings.DEFAULT_LLM_MODEL
        if not configured_model or configured_model.strip() in ["None", "null", ""]:
            if self.provider == "groq":
                self.model = "qwen/qwen3.8-27b"
            elif self.provider == "openai":
                self.model = "gpt-4o-mini"
            elif self.provider == "nim":
                self.model = "meta/llama-3-70b-instruct"
            else:
                self.model = "qwen/qwen3.8-27b"
        else:
            self.model = configured_model.strip()

        self.client = None
        self._init_client()

    def _init_client(self):
        """Initializes OpenAI-compatible client for Groq, OpenAI, NIM, or Ollama."""
        try:
            from openai import OpenAI

            if self.provider == "groq" and self.groq_key:
                logger.info(f"Connecting to Groq API using model '{self.model}'...")
                self.client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=self.groq_key)
            elif self.provider == "openai" and self.openai_key:
                logger.info(f"Connecting to OpenAI API using model '{self.model}'...")
                self.client = OpenAI(api_key=self.openai_key)
            elif self.provider == "nim" and self.nim_key:
                logger.info(f"Connecting to NVIDIA NIM API using model '{self.model}'...")
                self.client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=self.nim_key)
            elif self.provider == "ollama":
                ollama_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
                logger.info(f"Connecting to local Ollama at {ollama_url} using model '{self.model}'...")
                self.client = OpenAI(base_url=f"{ollama_url}/v1", api_key="ollama")
            elif self.groq_key:
                # Key present even if provider was not explicitly set to 'groq'
                logger.info(f"Auto-detected Groq key. Using Groq with model '{self.model}'...")
                self.client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=self.groq_key)
            elif self.openai_key:
                logger.info(f"Auto-detected OpenAI key. Using OpenAI with model '{self.model}'...")
                self.client = OpenAI(api_key=self.openai_key)
            else:
                logger.info("No external LLM key provided. Operating in deterministic template mode.")
                self.client = None
        except Exception as e:
            logger.warning(f"Could not initialize external LLM client: {e}. Falling back to deterministic template.")
            self.client = None

    def explain_finding(
        self,
        rule_name: str,
        citation: str,
        status: str,
        loan_field: str,
        extracted_value: Optional[str],
        rule_reasoning: str,
        evidence_items: List[RegulatoryEvidenceItem],
    ) -> Dict[str, Any]:
        """
        Generates an evidence-grounded explanation and reviewer notes.
        Invokes live LLM (Groq / OpenAI) when available, with automatic fallback to deterministic reasoning.
        """
        # 1. Sanitize untrusted input against prompt injection
        safe_val, has_inj = sanitize_untrusted_text(str(extracted_value or "None"))

        evidence_snippets = [f"[{e.citation}]: \"{e.quoted_text[:250]}\"" for e in evidence_items]
        evidence_text = "\n".join(evidence_snippets) if evidence_snippets else "No statutory excerpt found."

        # 2. Attempt Live LLM Reasoning if client is available
        if self.client:
            try:
                system_prompt = (
                    "You are a senior mortgage regulatory compliance intelligence engine. "
                    "Analyze the provided compliance rule finding against the retrievable statutory evidence. "
                    "Explain the legal implication clearly and objectively. Never fabricate laws or contradict the status. "
                    "Respond with a brief 2-3 sentence explanation followed by 1-2 practical questions for a human compliance reviewer."
                )

                user_prompt = (
                    f"COMPLIANCE FINDING DETAILS:\n"
                    f"- Rule: {rule_name}\n"
                    f"- Official Statute: {citation}\n"
                    f"- Compliance Status: {status}\n"
                    f"- Contract Term: {loan_field}\n"
                    f"- Extracted Value: {safe_val}\n"
                    f"- Deterministic Analysis: {rule_reasoning}\n\n"
                    f"STATUTORY EVIDENCE:\n{evidence_text}\n\n"
                    f"Please provide:\n"
                    f"1. A precise explanation of why this term is {status} under {citation}.\n"
                    f"2. Practical questions for the compliance reviewer."
                )

                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=300,
                    temperature=0.2,
                )

                llm_response = completion.choices[0].message.content.strip()
                if llm_response:
                    # Parse explanation and questions
                    lines = [line.strip() for line in llm_response.split("\n") if line.strip()]
                    explanation_lines = []
                    reviewer_questions = []
                    for line in lines:
                        if line.startswith(("-", "*", "1.", "2.", "?")) or "question" in line.lower() or line.endswith("?"):
                            clean_q = re.sub(r"^[\d\.\-\*\s]+", "", line)
                            if clean_q and len(clean_q) > 10:
                                reviewer_questions.append(clean_q)
                        else:
                            explanation_lines.append(line)

                    plain_explanation = " ".join(explanation_lines) if explanation_lines else llm_response
                    if not reviewer_questions:
                        reviewer_questions = [
                            f"Can the originating lender provide written documentation or addenda regarding {citation}?",
                            f"Does the borrower qualify for any statutory exemptions under applicable guidelines?",
                        ]

                    if has_inj:
                        plain_explanation += " [SECURITY WARNING: Untrusted document text contained potential prompt injection patterns which were sanitized.]"

                    return {
                        "explanation": plain_explanation,
                        "reviewer_questions": reviewer_questions[:3],
                        "injection_detected": has_inj,
                        "llm_provider": self.provider,
                        "llm_model": self.model,
                    }
            except Exception as e:
                logger.warning(f"Live LLM call to {self.provider} ({self.model}) failed: {e}. Falling back to deterministic template.")

        # 3. Fallback: Structured deterministic explanation template guarantees zero hallucination
        if status == "POTENTIAL_ISSUE":
            plain_explanation = (
                f"Statutory conflict detected under {citation} ({rule_name}). "
                f"The contract term '{loan_field}' was evaluated as '{safe_val}', which fails the regulatory threshold. "
                f"Ground-truth citation details: {rule_reasoning}"
            )
            reviewer_questions = [
                f"Can the originating lender provide written evidence of an exemption from {citation}?",
                "Has a revised disclosure or loan agreement amendment been drafted?",
            ]
        elif status == "NEEDS_REVIEW":
            plain_explanation = (
                f"Uncertain compliance status for {rule_name}. The document text does not provide clear disclosure "
                f"of '{loan_field}'. Immediate verification against official closing schedules is recommended."
            )
            reviewer_questions = [
                f"Please manually inspect the original document pages to confirm the exact value of '{loan_field}'.",
            ]
        elif status == "NOT_EVALUABLE":
            plain_explanation = (
                f"The requirement for {rule_name} cannot be evaluated because the necessary field '{loan_field}' "
                f"is absent or not applicable to this transaction structure."
            )
            reviewer_questions = [
                f"Is '{loan_field}' required for this specific loan product and jurisdiction?",
            ]
        else:
            plain_explanation = (
                f"Verified compliant with {citation}. The extracted value '{safe_val}' meets all applicable statutory criteria."
            )
            reviewer_questions = []

        if has_inj:
            plain_explanation += " [SECURITY WARNING: Untrusted document text contained potential prompt injection patterns which were sanitized.]"

        return {
            "explanation": plain_explanation,
            "reviewer_questions": reviewer_questions,
            "injection_detected": has_inj,
            "llm_provider": "deterministic_fallback",
            "llm_model": "template-grounded-v1",
        }
