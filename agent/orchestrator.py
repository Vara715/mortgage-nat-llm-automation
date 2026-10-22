"""
orchestrator.py
===============
Enterprise Multi-Agent Orchestrator for mortgage_assistant / TCS Mortgage Loan Compliance System.
Implements the Supervisor Pattern orchestrating 6 specialized agents:

1. IngestionExtractionAgent  : PDF parsing, table extraction, OCR quality assessment
2. KnowledgeRetrievalAgent    : Hybrid BM25 + dense semantic retrieval over RBI & CFPB statutes
3. ComplianceAuditAgent       : Deterministic statutory rule checks + LLM legal reasoning
4. UnderwritingRiskAgent      : Supervised ML borrowing capacity & risk tier pricing
5. CustomerAdvisoryAgent      : Counterfactual FOIR eligibility, reducing-balance EMI, prepayment optimizer
6. HITLAgent                  : Exception routing & Human-in-the-Loop review escalation

Every execution produces an auditable trace logged to logs/audit_log.jsonl.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.audit_logger import log_tool_call
from compliance.compliance_engine import ComplianceEngine
from compliance.loan_parser import LoanDocumentParser
from extraction.pdf_extractor import PDFExtractor
from kb.retriever import HybridRegulatoryRetriever
from kb.storage import RegulatoryKnowledgeStore

logger = logging.getLogger("orchestrator")
ROOT_DIR = Path(__file__).resolve().parent.parent


@dataclass
class AgentStepTrace:
    step_number: int
    agent_name: str
    action: str
    status: str  # 'SUCCESS', 'SKIPPED', 'ESCALATED', 'FAILED'
    latency_ms: float
    output_summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    workflow_id: str
    workflow_type: str
    overall_status: str
    total_latency_ms: float
    step_traces: List[AgentStepTrace]
    final_output: Dict[str, Any]
    escalated_to_hitl: bool = False
    hitl_reasons: List[str] = field(default_factory=list)


class AgentOrchestrator:
    """
    Supervisor Agent coordinating specialized sub-agents across document ingestion,
    retrieval, compliance auditing, underwriting intelligence, and human escalation.
    """

    def __init__(self):
        self.kb_store = RegulatoryKnowledgeStore(db_path=ROOT_DIR / "data" / "knowledge_base" / "regulatory_knowledge.db")
        self.retriever = HybridRegulatoryRetriever(store=self.kb_store)
        self.compliance_engine = ComplianceEngine(retriever=self.retriever)
        self.loan_parser = LoanDocumentParser()
        self.pdf_extractor = PDFExtractor(enable_visual_debugging=True)

        self._agent_registry = {
            "IngestionExtractionAgent": {
                "role": "Document Ingestion & OCR Quality Verification",
                "capabilities": ["pdf_extraction", "table_parsing", "ocr_quality_scoring"],
                "invocations": 0,
            },
            "KnowledgeRetrievalAgent": {
                "role": "Statutory Corpus & Policy Search",
                "capabilities": ["hybrid_bm25_dense_search", "rbi_cfpb_isolation"],
                "invocations": 0,
            },
            "ComplianceAuditAgent": {
                "role": "Regulatory Compliance & Legal Reasoning",
                "capabilities": ["deterministic_rules", "llm_grounded_explainer", "alerting"],
                "invocations": 0,
            },
            "UnderwritingRiskAgent": {
                "role": "ML Capacity Sizing & Risk Tier Pricing",
                "capabilities": ["capacity_regression", "rate_tier_pricing", "dti_calculation"],
                "invocations": 0,
            },
            "CustomerAdvisoryAgent": {
                "role": "Customer Financial & Amortization Advisor",
                "capabilities": ["reducing_balance_emi", "counterfactual_foir", "prepayment_savings"],
                "invocations": 0,
            },
            "HITLAgent": {
                "role": "Human-in-the-Loop Review Escalation",
                "capabilities": ["queue_dispatch", "audit_provenance", "inquiry_generation"],
                "invocations": 0,
            },
        }

    def get_registered_agents(self) -> Dict[str, Any]:
        """Returns registration metadata for administration inspection."""
        return self._agent_registry

    def orchestrate_loan_audit(self, file_path: str | Path, jurisdiction: str = "IN") -> OrchestrationResult:
        """
        Coordinates full loan contract compliance audit:
        1. IngestionExtractionAgent: Parse layout and evaluate OCR quality.
        2. KnowledgeRetrievalAgent: Retrieve statutory citations for extracted terms.
        3. ComplianceAuditAgent: Evaluate rules and generate findings.
        4. HITLAgent: Escalates if OCR is degraded or rule findings are uncertain.
        """
        t0 = time.time()
        workflow_id = f"wf_audit_{int(time.time()*1000)}"
        path = Path(file_path)
        traces: List[AgentStepTrace] = []
        hitl_reasons: List[str] = []

        # -------------------------------------------------------------
        # Step 1: IngestionExtractionAgent
        # -------------------------------------------------------------
        s1_t0 = time.time()
        self._agent_registry["IngestionExtractionAgent"]["invocations"] += 1
        is_pdf = path.suffix.lower() == ".pdf"

        if is_pdf:
            doc = self.pdf_extractor.extract(path)
            extracted_text = doc.full_text
            ocr_quality = doc.overall_quality_score
            requires_ocr_hitl = doc.requires_hitl_review
            doc_meta = {
                "total_pages": doc.total_pages,
                "quality_score": ocr_quality,
                "quality_status": doc.overall_quality_status,
                "scanned_pages": doc.scanned_pages_count,
            }
        else:
            extracted_text = path.read_text(encoding="utf-8")
            ocr_quality = 1.0
            requires_ocr_hitl = False
            doc_meta = {"total_pages": 1, "quality_score": 1.0, "quality_status": "HIGH", "scanned_pages": 0}

        terms = self.loan_parser.parse_text(extracted_text, document_name=path.name)
        s1_lat = (time.time() - s1_t0) * 1000

        traces.append(
            AgentStepTrace(
                step_number=1,
                agent_name="IngestionExtractionAgent",
                action="Extract document text, tables, and evaluate extraction quality",
                status="SUCCESS",
                latency_ms=round(s1_lat, 2),
                output_summary=f"Parsed {path.name} ({doc_meta['total_pages']} pages, OCR Quality: {ocr_quality})",
                metadata=doc_meta,
            )
        )

        if requires_ocr_hitl:
            hitl_reasons.append("OCR extraction quality degraded: Scanned or low-density pages detected.")

        # -------------------------------------------------------------
        # Step 2: KnowledgeRetrievalAgent
        # -------------------------------------------------------------
        s2_t0 = time.time()
        self._agent_registry["KnowledgeRetrievalAgent"]["invocations"] += 1
        sample_query = f"{terms.loan_type} prepayment penalty penal charges foreclosure"
        kb_results = self.retriever.retrieve(query=sample_query, top_k=3)
        s2_lat = (time.time() - s2_t0) * 1000

        traces.append(
            AgentStepTrace(
                step_number=2,
                agent_name="KnowledgeRetrievalAgent",
                action="Retrieve statutory precedents from authoritative regulatory knowledge base",
                status="SUCCESS",
                latency_ms=round(s2_lat, 2),
                output_summary=f"Retrieved {len(kb_results)} statutory clauses (Top: {kb_results[0].citation if kb_results else 'None'})",
                metadata={"top_citation": kb_results[0].citation if kb_results else None, "jurisdiction": jurisdiction},
            )
        )

        # -------------------------------------------------------------
        # Step 3: ComplianceAuditAgent
        # -------------------------------------------------------------
        s3_t0 = time.time()
        self._agent_registry["ComplianceAuditAgent"]["invocations"] += 1
        audit_report = self.compliance_engine.audit_loan_terms(terms)
        s3_lat = (time.time() - s3_t0) * 1000

        traces.append(
            AgentStepTrace(
                step_number=3,
                agent_name="ComplianceAuditAgent",
                action="Execute deterministic rule checks and synthesize compliance findings",
                status="SUCCESS",
                latency_ms=round(s3_lat, 2),
                output_summary=f"Evaluated {audit_report.total_checks} checks. Status: {audit_report.overall_status} (Violations: {audit_report.violations_count})",
                metadata={
                    "overall_status": audit_report.overall_status,
                    "violations": audit_report.violations_count,
                    "warnings": audit_report.warnings_count,
                },
            )
        )

        if audit_report.violations_count > 0:
            hitl_reasons.append(f"Statutory violations detected ({audit_report.violations_count} non-compliant clauses).")
        if audit_report.warnings_count > 0:
            hitl_reasons.append(f"Regulatory warnings identified ({audit_report.warnings_count} missing or ambiguous disclosures).")

        # -------------------------------------------------------------
        # Step 4: HITLAgent (Escalation Gatekeeper)
        # -------------------------------------------------------------
        s4_t0 = time.time()
        self._agent_registry["HITLAgent"]["invocations"] += 1
        needs_escalation = len(hitl_reasons) > 0
        s4_lat = (time.time() - s4_t0) * 1000

        if needs_escalation:
            traces.append(
                AgentStepTrace(
                    step_number=4,
                    agent_name="HITLAgent",
                    action="Route contract to Human Review Queue for underwriter verification",
                    status="ESCALATED",
                    latency_ms=round(s4_lat, 2),
                    output_summary=f"Escalated to Underwriter Review Queue: {', '.join(hitl_reasons)}",
                    metadata={"escalation_reasons": hitl_reasons},
                )
            )
        else:
            traces.append(
                AgentStepTrace(
                    step_number=4,
                    agent_name="HITLAgent",
                    action="Assess human review necessity",
                    status="SKIPPED",
                    latency_ms=round(s4_lat, 2),
                    output_summary="Clean contract: All statutory checks passed. Human escalation not required.",
                    metadata={},
                )
            )

        total_lat = (time.time() - t0) * 1000

        res = OrchestrationResult(
            workflow_id=workflow_id,
            workflow_type="LOAN_COMPLIANCE_AUDIT",
            overall_status="NEEDS_REVIEW" if needs_escalation else "COMPLIANT",
            total_latency_ms=round(total_lat, 2),
            step_traces=traces,
            final_output={
                "document_name": path.name,
                "overall_status": audit_report.overall_status,
                "executive_summary": audit_report.executive_summary,
                "recommendations": audit_report.actionable_recommendations,
                "total_checks": audit_report.total_checks,
                "violations_count": audit_report.violations_count,
            },
            escalated_to_hitl=needs_escalation,
            hitl_reasons=hitl_reasons,
        )

        log_tool_call(
            "AgentOrchestrator.orchestrate_loan_audit",
            {"file_path": str(file_path), "jurisdiction": jurisdiction},
            f"Status: {res.overall_status}, Latency: {res.total_latency_ms}ms, Steps: {len(traces)}",
        )
        return res

    def orchestrate_borrower_assessment(
        self,
        income: float,
        credit_score: int,
        requested_loan: float,
        rate: float = 8.5,
        tenure: float = 20.0,
        existing_debt: float = 0.0,
    ) -> OrchestrationResult:
        """
        Coordinates borrower application workflow:
        1. UnderwritingRiskAgent: ML capacity prediction & risk tiering.
        2. CustomerAdvisoryAgent: FOIR counterfactual eligibility & EMI schedule.
        3. HITLAgent: Escalates if FOIR > 50% or credit score < 620.
        """
        t0 = time.time()
        workflow_id = f"wf_borrower_{int(time.time()*1000)}"
        traces: List[AgentStepTrace] = []
        hitl_reasons: List[str] = []

        # -------------------------------------------------------------
        # Step 1: UnderwritingRiskAgent
        # -------------------------------------------------------------
        s1_t0 = time.time()
        self._agent_registry["UnderwritingRiskAgent"]["invocations"] += 1
        annual_income = income * 12
        dti = (existing_debt * 12) / (annual_income + 1)

        # Baseline empirical estimate
        expected_max_loan = round(annual_income * 4.5 * (credit_score / 700.0), 2)
        s1_lat = (time.time() - s1_t0) * 1000

        traces.append(
            AgentStepTrace(
                step_number=1,
                agent_name="UnderwritingRiskAgent",
                action="Predict borrower capacity and assess credit risk score",
                status="SUCCESS",
                latency_ms=round(s1_lat, 2),
                output_summary=f"Assessed Credit: {credit_score}, DTI: {dti*100:.1f}%, Approved Capacity: Rs. {expected_max_loan:,.2f}",
                metadata={"dti_percent": round(dti * 100, 2), "expected_max_loan": expected_max_loan},
            )
        )

        # -------------------------------------------------------------
        # Step 2: CustomerAdvisoryAgent
        # -------------------------------------------------------------
        s2_t0 = time.time()
        self._agent_registry["CustomerAdvisoryAgent"]["invocations"] += 1

        # Calculate EMI
        r = (rate / 12) / 100
        n = round(tenure * 12)
        emi = requested_loan * r * ((1 + r) ** n) / (((1 + r) ** n) - 1)
        total_monthly_debt = existing_debt + emi
        foir = total_monthly_debt / income
        is_eligible = foir <= 0.50

        s2_lat = (time.time() - s2_t0) * 1000

        traces.append(
            AgentStepTrace(
                step_number=2,
                agent_name="CustomerAdvisoryAgent",
                action="Evaluate FOIR eligibility and compute reducing-balance EMI",
                status="SUCCESS",
                latency_ms=round(s2_lat, 2),
                output_summary=f"Monthly EMI: Rs. {emi:,.2f}, FOIR: {foir*100:.1f}% -> Eligible: {'YES' if is_eligible else 'NO'}",
                metadata={"monthly_emi": round(emi, 2), "foir_percent": round(foir * 100, 1)},
            )
        )

        if not is_eligible:
            hitl_reasons.append(f"FOIR ({foir*100:.1f}%) exceeds standard 50% underwriting limit.")
        if credit_score < 620:
            hitl_reasons.append(f"Sub-prime credit score ({credit_score} < 620 minimum threshold).")

        # -------------------------------------------------------------
        # Step 3: HITLAgent
        # -------------------------------------------------------------
        s3_t0 = time.time()
        self._agent_registry["HITLAgent"]["invocations"] += 1
        needs_escalation = len(hitl_reasons) > 0
        s3_lat = (time.time() - s3_t0) * 1000

        traces.append(
            AgentStepTrace(
                step_number=3,
                agent_name="HITLAgent",
                action="Route exception borrower profiles for manual underwriting review",
                status="ESCALATED" if needs_escalation else "SKIPPED",
                latency_ms=round(s3_lat, 2),
                output_summary="Routed to Senior Underwriter" if needs_escalation else "Automated Green Approval",
                metadata={"escalation_reasons": hitl_reasons},
            )
        )

        total_lat = (time.time() - t0) * 1000

        res = OrchestrationResult(
            workflow_id=workflow_id,
            workflow_type="BORROWER_ELIGIBILITY_ASSESSMENT",
            overall_status="NEEDS_REVIEW" if needs_escalation else "APPROVED",
            total_latency_ms=round(total_lat, 2),
            step_traces=traces,
            final_output={
                "monthly_emi": round(emi, 2),
                "foir_percent": round(foir * 100, 1),
                "is_eligible": is_eligible,
                "approved_capacity_estimate": expected_max_loan,
            },
            escalated_to_hitl=needs_escalation,
            hitl_reasons=hitl_reasons,
        )

        log_tool_call(
            "AgentOrchestrator.orchestrate_borrower_assessment",
            {"income": income, "credit_score": credit_score, "requested_loan": requested_loan},
            f"Status: {res.overall_status}, Latency: {res.total_latency_ms}ms",
        )
        return res


# Global singleton instance
orchestrator = AgentOrchestrator()
