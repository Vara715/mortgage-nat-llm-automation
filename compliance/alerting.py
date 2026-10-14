"""
alerting.py
===========
Implements Alerting & Recommendation output from Slide 8:
"If non-compliant -> generate structured output"
Produces structured JSON reports and formatted markdown audit summaries.
"""

import json
from typing import Dict, Any
from compliance.compliance_engine import ComplianceAuditReport


def format_alert_summary(report: ComplianceAuditReport) -> str:
    """Formats a ComplianceAuditReport into a clean, professional audit summary."""
    status_icons = {
        "COMPLIANT": "[COMPLIANT]",
        "NON_COMPLIANT": "[VIOLATION - NON-COMPLIANT]",
        "WARNING": "[WARNING - REVIEW REQUIRED]",
    }

    icon = status_icons.get(report.overall_status, f"[{report.overall_status}]")

    lines = [
        "=" * 70,
        f"TCS MORTGAGE COMPLIANCE AUDIT REPORT: {report.document_name}",
        "=" * 70,
        f"Overall Status: {icon}",
        f"Document Type : {report.document_type} (Borrower: {report.borrower_type.title()})",
        f"Summary       : {report.executive_summary}",
        "-" * 70,
        "DETAILED CLAUSE-BY-CLAUSE REGULATORY CHECKS:",
    ]

    for idx, c in enumerate(report.clause_results, 1):
        lines.append(f"\n{idx}. Check: {c.check_name}")
        lines.append(f"   Status      : {c.status}")
        lines.append(f"   Found       : {c.extracted_value}")
        lines.append(f"   Threshold   : {c.regulatory_threshold}")
        lines.append(f"   Citation    : {c.regulatory_citation}")
        if c.violation_reason:
            lines.append(f"   Violation   : {c.violation_reason}")
        if c.recommended_remediation:
            lines.append(f"   Remediation : {c.recommended_remediation}")

    if report.actionable_recommendations:
        lines.append("\n" + "-" * 70)
        lines.append("ACTIONABLE REMEDIATION RECOMMENDATIONS:")
        for idx, rec in enumerate(report.actionable_recommendations, 1):
            lines.append(f"  [{idx}] {rec}")

    lines.append("=" * 70)
    return "\n".join(lines)


def export_audit_report_json(report: ComplianceAuditReport, indent: int = 2) -> str:
    """Exports ComplianceAuditReport as JSON."""
    return report.model_dump_json(indent=indent)
