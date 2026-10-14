"""
Test script for verifying HybridRegulatoryRetriever and ComplianceEngine end-to-end.
"""

import time
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from kb.storage import RegulatoryKnowledgeStore
from kb.retriever import HybridRegulatoryRetriever
from compliance.loan_parser import LoanDocumentParser
from compliance.compliance_engine import ComplianceEngine
from compliance.alerting import format_alert_summary

store = RegulatoryKnowledgeStore(db_path="data/knowledge_base/regulatory_knowledge.db")
retriever = HybridRegulatoryRetriever(store=store)
engine = ComplianceEngine(retriever=retriever)
parser = LoanDocumentParser()

print("=" * 70)
print("TEST 1: HIGH-PERFORMANCE RETRIEVAL TEST")
print("=" * 70)

queries = [
    "Are banks permitted to charge prepayment penalty on floating rate home loans?",
    "Can banks grant term loans to housing intermediary agencies for NRIs?",
    "What are the LTV ratio limits for housing loans?",
    "Can penal interest be compounded monthly?",
]

for q in queries:
    t0 = time.time()
    results = retriever.retrieve(q, top_k=2)
    latency_ms = (time.time() - t0) * 1000
    print(f"\nQuery: {q}")
    print(f"Latency: {latency_ms:.2f} ms | Results found: {len(results)}")
    if results:
        top = results[0]
        print(f"Top Citation: {top.citation} (Score: {top.score})")
        print(f"Snippet: {top.text[:180]}...")

print("\n" + "=" * 70)
print("TEST 2: COMPLIANCE AUDIT ON NON-COMPLIANT HOME LOAN AGREEMENT")
print("=" * 70)

non_compliant_text = Path("data/real_docs/sample_loan_agreements/non_compliant_home_loan_agreement.txt").read_text(encoding="utf-8")
terms_nc = parser.parse_text(non_compliant_text, document_name="non_compliant_home_loan_agreement.txt")
report_nc = engine.audit_loan_terms(terms_nc)
print(format_alert_summary(report_nc))

print("\n" + "=" * 70)
print("TEST 3: COMPLIANCE AUDIT ON COMPLIANT HOME LOAN AGREEMENT")
print("=" * 70)

compliant_text = Path("data/real_docs/sample_loan_agreements/sample_loan_agreements/compliant_home_loan_agreement.txt")
if not compliant_text.exists():
    compliant_text = Path("data/real_docs/sample_loan_agreements/compliant_home_loan_agreement.txt")
terms_c = parser.parse_text(compliant_text.read_text(encoding="utf-8"), document_name="compliant_home_loan_agreement.txt")
report_c = engine.audit_loan_terms(terms_c)
print(format_alert_summary(report_c))
