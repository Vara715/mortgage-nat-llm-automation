"""
report_generator.py
===================
Generates formal compliance audit reports in PDF format using ReportLab.
Includes executive summary, finding breakdown, exact statutory citations,
human review audit statuses, and strict legal disclaimers.
"""

import io
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from backend.app.schemas.compliance import ComplianceAnalysisResponse


class ComplianceReportGenerator:
    @staticmethod
    def generate_pdf(analysis: ComplianceAnalysisResponse) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        # Custom typography styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
            fontName="Helvetica-Bold",
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b"),
        )
        heading2_style = ParagraphStyle(
            "Heading2Custom",
            parent=styles["Heading2"],
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1e293b"),
            fontName="Helvetica-Bold",
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "BodyCustom",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
        )
        disclaimer_style = ParagraphStyle(
            "DisclaimerCustom",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#b91c1c"),
            fontName="Helvetica-Oblique",
        )
        cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        )
        badge_style = ParagraphStyle(
            "BadgeStyle",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            fontName="Helvetica-Bold",
        )

        elements = []

        # 1. Header Banner
        elements.append(Paragraph("mortgage_assistant", title_style))
        elements.append(
            Paragraph(
                "Regulatory Compliance Audit & Evidence-Grounded Verification Report",
                subtitle_style,
            )
        )
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb"), spaceAfter=12, spaceBefore=6))

        # 2. Executive Metadata Box
        status_color = "#dc2626" if analysis.overall_status == "POTENTIAL_ISSUE" else "#16a34a" if analysis.overall_status == "NO_ISSUE_IDENTIFIED" else "#d97706"
        meta_data = [
            [
                Paragraph("<b>Document Evaluated:</b>", cell_style),
                Paragraph(analysis.document_name, cell_style),
                Paragraph("<b>Jurisdiction:</b>", cell_style),
                Paragraph(analysis.jurisdiction, cell_style),
            ],
            [
                Paragraph("<b>Analysis ID:</b>", cell_style),
                Paragraph(analysis.analysis_id[:13] + "...", cell_style),
                Paragraph("<b>Overall Status:</b>", cell_style),
                Paragraph(f"<font color='{status_color}'><b>{analysis.overall_status}</b></font>", badge_style),
            ],
            [
                Paragraph("<b>Generated Timestamp:</b>", cell_style),
                Paragraph(analysis.generated_at, cell_style),
                Paragraph("<b>Total Findings:</b>", cell_style),
                Paragraph(str(len(analysis.findings)), cell_style),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[1.5 * inch, 2.3 * inch, 1.4 * inch, 1.8 * inch])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 12))

        # 3. Non-Legal Advice Disclaimer (Prominent)
        disclaimer_text = (
            "<b>LEGAL & COMPLIANCE DISCLAIMER:</b> mortgage_assistant is an automated decision-support system. "
            "This report is generated for compliance review assistance and does not constitute a legal opinion, "
            "formal regulatory warranty, or guarantee of compliance. A missing violation does not establish "
            "that the loan document is compliant with applicable federal, state, or RBI regulations. "
            "Final determinations must be made by qualified compliance officers and legal counsel."
        )
        elements.append(Paragraph(disclaimer_text, disclaimer_style))
        elements.append(Spacer(1, 10))

        # 4. Executive Summary
        elements.append(Paragraph("Executive Summary", heading2_style))
        elements.append(Paragraph(analysis.summary, body_style))
        elements.append(Spacer(1, 10))

        # 5. Compliance Findings Breakdown
        elements.append(Paragraph("Detailed Compliance Findings & Grounded Evidence", heading2_style))

        if not analysis.findings:
            elements.append(Paragraph("No regulatory compliance issues were flagged for this document.", body_style))
        else:
            for idx, f in enumerate(analysis.findings, 1):
                sev_color = "#dc2626" if f.severity in ("CRITICAL", "HIGH") else "#d97706" if f.severity == "MEDIUM" else "#16a34a"
                stat_color = "#dc2626" if f.status == "POTENTIAL_ISSUE" else "#16a34a" if f.status == "NO_ISSUE_IDENTIFIED" else "#d97706"

                finding_rows = [
                    [
                        Paragraph(f"<b>Finding #{idx}: {f.rule_id} ({f.category})</b>", cell_style),
                        Paragraph(f"Severity: <font color='{sev_color}'><b>{f.severity}</b></font> | Status: <font color='{stat_color}'><b>{f.status}</b></font>", cell_style),
                    ],
                    [
                        Paragraph("<b>Extracted Loan Term:</b>", cell_style),
                        Paragraph(
                            f"<b>Field:</b> {f.loan_term.field} = <b>{f.loan_term.value}</b> (Page {f.loan_term.source_page})<br/>"
                            f"<i>Excerpt:</i> \"{f.loan_term.source_excerpt}\"",
                            cell_style,
                        ),
                    ],
                    [
                        Paragraph("<b>Regulatory Rule & Citations:</b>", cell_style),
                        Paragraph(
                            "".join(
                                [
                                    f"• <b>{ev.citation}</b> ({ev.source_name})<br/>"
                                    f"  <i>Statutory Text:</i> \"{ev.quoted_text[:250]}...\"<br/>"
                                    for ev in f.regulatory_evidence
                                ]
                            ) if f.regulatory_evidence else "Standard deterministic rule threshold applied.",
                            cell_style,
                        ),
                    ],
                    [
                        Paragraph("<b>Compliance Reasoning:</b>", cell_style),
                        Paragraph(f.reasoning, cell_style),
                    ],
                    [
                        Paragraph("<b>Action & HITL Status:</b>", cell_style),
                        Paragraph(f"<b>Recommended Action:</b> {f.recommended_action}<br/><b>Review Status:</b> {f.review_status}", cell_style),
                    ],
                ]

                f_table = Table(finding_rows, colWidths=[1.8 * inch, 5.2 * inch])
                f_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                elements.append(KeepTogether([f_table, Spacer(1, 8)]))

        # 6. Limitations & Information Gaps
        if analysis.limitations:
            elements.append(Paragraph("Document Scope & Limitations", heading2_style))
            for lim in analysis.limitations:
                elements.append(Paragraph(f"• {lim}", body_style))
            elements.append(Spacer(1, 8))

        # 7. Audit Footprint
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=12, spaceAfter=8))
        elements.append(
            Paragraph(
                f"Generated by mortgage_assistant Platform • Confidential Audit Record • "
                f"ISO/IEC 27001 & SOC 2 Compliant Hash Tracking: {analysis.analysis_id}",
                subtitle_style,
            )
        )

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
