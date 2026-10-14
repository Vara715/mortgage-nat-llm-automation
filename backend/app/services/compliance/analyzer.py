"""
analyzer.py
===========
End-to-end Compliance Orchestration Service.
Connects:
1. Loan term extraction (with source provenance)
2. Hybrid regulatory retrieval (with strict jurisdiction isolation)
3. Deterministic rule evaluation
4. LLM plain-language explanation
5. Finding storage and automated routing to Human Review queue
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.models.entities import (
    LoanDocument,
    ExtractedLoanField,
    ComplianceAnalysis,
    ComplianceFinding,
    FindingEvidence,
    ReviewTask,
    AuditEvent,
)
from backend.app.schemas.compliance import (
    ComplianceAnalysisResponse,
    ComplianceFindingSchema,
    LoanTermEvidence,
    RegulatoryEvidenceItem,
)
from backend.app.services.loan_extraction.term_extractor import LoanTermExtractor
from backend.app.services.retrieval.hybrid_search import HybridSearchService
from backend.app.services.rule_engine.engine import ComplianceRuleEngine
from backend.app.services.compliance.llm_explainer import LLMExplainerService


class ComplianceAnalyzerService:
    def __init__(self, db: Session):
        self.db = db
        self.extractor = LoanTermExtractor()
        self.retriever = HybridSearchService(db)
        self.rule_engine = ComplianceRuleEngine()
        self.explainer = LLMExplainerService()

    def analyze_document(self, loan_doc_id: str) -> ComplianceAnalysisResponse:
        loan_doc = self.db.query(LoanDocument).filter(LoanDocument.id == loan_doc_id).first()
        if not loan_doc:
            raise ValueError(f"Loan document '{loan_doc_id}' not found.")

        # 1. Read document text
        from pathlib import Path
        doc_path = Path(loan_doc.file_path)
        if doc_path.suffix.lower() == ".pdf":
            from backend.app.services.extraction.pdf_service import PDFExtractionService
            pdf_svc = PDFExtractionService()
            extracted_doc = pdf_svc.extract(doc_path)
            full_text = extracted_doc["full_text"]
        else:
            full_text = doc_path.read_text(encoding="utf-8", errors="ignore")

        # 2. Extract structured loan terms
        extraction = self.extractor.extract_terms(full_text, document_name=loan_doc.filename)
        loan_doc.jurisdiction = extraction.jurisdiction
        loan_doc.doc_type = extraction.doc_type
        loan_doc.status = "PARSED"

        # Persist extracted fields
        for field_name, f_record in extraction.fields.items():
            db_field = ExtractedLoanField(
                loan_document_id=loan_doc.id,
                field_name=field_name,
                field_value_str=f_record.value_str or str(f_record.value),
                field_value_num=f_record.value_num,
                source_page=f_record.source_page,
                source_excerpt=f_record.source_excerpt,
                confidence=f_record.confidence,
            )
            self.db.add(db_field)

        # 3. Deterministic rule evaluation
        rule_results = self.rule_engine.evaluate(extraction)

        # 4. Hybrid regulatory retrieval and explanation synthesis
        finding_schemas: list[ComplianceFindingSchema] = []
        db_findings: list[ComplianceFinding] = []

        analysis_id = str(uuid.uuid4())
        has_potential_issue = False
        has_needs_review = False

        for res in rule_results:
            if res.status == "POTENTIAL_ISSUE":
                has_potential_issue = True
            elif res.status in ["NEEDS_REVIEW", "NOT_EVALUABLE"]:
                has_needs_review = True

            # Retrieve jurisdiction-isolated evidence
            evidence_items = self.retriever.search(
                query=f"{res.rule_name} {res.citation} {res.loan_field}",
                jurisdiction=extraction.jurisdiction,
                category=res.category,
                top_k=2,
            )

            # Synthesize explanation
            exp_data = self.explainer.explain_finding(
                rule_name=res.rule_name,
                citation=res.citation,
                status=res.status,
                loan_field=res.loan_field,
                extracted_value=res.extracted_value,
                rule_reasoning=res.reasoning,
                evidence_items=evidence_items,
            )

            f_id = str(uuid.uuid4())
            field_record = extraction.fields.get(res.loan_field)
            src_page = field_record.source_page if field_record else 1
            src_excerpt = field_record.source_excerpt if field_record else "Referenced in loan terms"

            f_schema = ComplianceFindingSchema(
                finding_id=f_id,
                rule_id=res.rule_id,
                category=res.category,
                severity=res.severity,
                status=res.status,
                loan_term=LoanTermEvidence(
                    field=res.loan_field,
                    value=res.extracted_value,
                    source_page=src_page,
                    source_excerpt=src_excerpt,
                ),
                regulatory_evidence=evidence_items,
                reasoning=exp_data["explanation"],
                missing_information=res.missing_information,
                recommended_action=res.recommended_action,
                review_status="PENDING" if res.status in ["POTENTIAL_ISSUE", "NEEDS_REVIEW"] else "NOT_REQUIRED",
            )
            finding_schemas.append(f_schema)

            # DB Finding entity
            finding_entity = ComplianceFinding(
                id=f_id,
                analysis_id=analysis_id,
                rule_id=res.rule_id,
                category=res.category,
                severity=res.severity,
                status=res.status,
                loan_field=res.loan_field,
                extracted_value=res.extracted_value,
                reasoning=exp_data["explanation"],
                recommended_action=res.recommended_action,
                review_status=f_schema.review_status,
            )
            db_findings.append(finding_entity)
            self.db.add(finding_entity)

            # Persist evidence link
            for ev in evidence_items:
                db_ev = FindingEvidence(
                    finding_id=f_id,
                    citation=ev.citation,
                    source_name=ev.source_name,
                    source_url=ev.source_url,
                    page_number=ev.page_number,
                    quoted_text=ev.quoted_text,
                    score=ev.relevance_score,
                )
                self.db.add(db_ev)

            # Automatically route non-compliant or uncertain findings to Human Review Queue
            if res.status in ["POTENTIAL_ISSUE", "NEEDS_REVIEW"]:
                review_task = ReviewTask(
                    finding_id=f_id,
                    status="PENDING",
                    assigned_to="compliance_analyst",
                )
                self.db.add(review_task)

        # 5. Overall status determination (Section 5)
        # Any unresolved material issue prevents an unqualified compliance conclusion
        if has_potential_issue:
            overall_status = "POTENTIAL_ISSUE"
            summary = (
                f"AUDIT WARNING: Potential statutory non-compliance detected in {loan_doc.filename} "
                f"under {extraction.jurisdiction} mortgage regulations. Contractual remediation or legal review required."
            )
        elif has_needs_review:
            overall_status = "NEEDS_REVIEW"
            summary = (
                f"REVIEW REQUIRED: Analysis for {loan_doc.filename} completed with missing or uncertain fields. "
                f"Routing to compliance reviewer for confirmation."
            )
        else:
            overall_status = "NO_ISSUE_IDENTIFIED"
            summary = (
                f"AUDIT COMPLETE: No statutory compliance issues identified for {loan_doc.filename} "
                f"under evaluated {extraction.jurisdiction} regulations."
            )

        analysis_entity = ComplianceAnalysis(
            id=analysis_id,
            loan_document_id=loan_doc.id,
            jurisdiction=extraction.jurisdiction,
            overall_status=overall_status,
            summary=summary,
        )
        self.db.add(analysis_entity)
        loan_doc.status = "ANALYZED"

        # Record audit event
        audit = AuditEvent(
            event_type="COMPLIANCE_ANALYSIS_COMPLETED",
            actor="system",
            entity_type="loan_document",
            entity_id=loan_doc.id,
            payload=str({"analysis_id": analysis_id, "overall_status": overall_status, "findings_count": len(finding_schemas)}),
        )
        self.db.add(audit)
        self.db.commit()

        return ComplianceAnalysisResponse(
            analysis_id=analysis_id,
            loan_document_id=loan_doc.id,
            document_name=loan_doc.filename,
            jurisdiction=extraction.jurisdiction,
            overall_status=overall_status,
            summary=summary,
            findings=finding_schemas,
            limitations=[
                "This platform is a decision-support tool and does not constitute a definitive legal opinion.",
                "A finding of NO_ISSUE_IDENTIFIED applies only to the specific rules and inputs evaluated.",
            ],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
