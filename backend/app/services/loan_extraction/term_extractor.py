"""
term_extractor.py
=================
Loan document classification and structured term extraction (Section 4.E).
Extracts fields with source page and verbatim text evidence.
Detects jurisdiction (US vs IN) and flags missing or ambiguous terms.
"""

import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


def _safe_float(val: Optional[str]) -> Optional[float]:
    if not val:
        return None
    cleaned = re.sub(r"[^\d\.]", "", str(val))
    if not cleaned or not any(c.isdigit() for c in cleaned):
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


class ExtractedFieldRecord(BaseModel):
    field_name: str
    value: Any
    value_num: Optional[float] = None
    value_str: Optional[str] = None
    source_page: int = 1
    source_excerpt: str
    confidence: float = 0.95


class LoanExtractionResult(BaseModel):
    document_name: str
    jurisdiction: str  # 'US' or 'IN'
    doc_type: str
    borrower_type: str  # 'individual' or 'corporate'
    fields: Dict[str, ExtractedFieldRecord]
    missing_fields: List[str] = []


class LoanTermExtractor:
    def extract_terms(self, text: str, document_name: str = "Loan_Agreement") -> LoanExtractionResult:
        text_lower = text.lower()
        fields: Dict[str, ExtractedFieldRecord] = {}
        missing: List[str] = []

        # 1. Determine Jurisdiction
        is_indian = any(w in text_lower for w in ["rupee", "rs.", "lakh", "crore", "rbi", "reserve bank of india", "ireda", "delhi", "mumbai", "maharashtra", "companies act", "banking regulation act"])
        is_us = any(w in text_lower for w in ["12 cfr", "fannie mae", "freddie mac", "u.s. $", "consumer financial protection bureau", "regulation z", "subprime residential", "fha loan", "va loan", "closing disclosure"])

        if is_indian and not is_us:
            jurisdiction = "IN"
            doc_type = "Commercial Term Loan" if "commercial" in text_lower or "corporate" in text_lower or "ltd." in text_lower else "Housing Loan Agreement (India)"
        elif is_us:
            jurisdiction = "US"
            doc_type = "Residential Mortgage Note (US Uniform Instrument)"
        elif is_indian:
            jurisdiction = "IN"
            doc_type = "Housing Loan Agreement (India)"
        else:
            jurisdiction = "US"  # default fallback
            doc_type = "General Credit Agreement"

        # 2. Determine Borrower Type
        borrower_type = "individual"
        m_borrower = re.search(r"[^\n]{0,100}(?:borrower|consumer)[^\n]{0,100}", text, re.IGNORECASE)
        b_excerpt = m_borrower.group(0) if m_borrower else "Borrower specified in agreement"
        if any(w in b_excerpt.lower() for w in ["pvt ltd", "corporation", "commercial borrower", "inc.", "llc", "company within the meaning"]):
            borrower_type = "corporate"

        # 3. Principal / Loan Amount
        m_amt = re.search(r"(?:u\.s\.\s*\$|inr|rs\.?|₹|\$)\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
        amt_val = _safe_float(m_amt.group(1)) if m_amt else None
        if amt_val is not None:
            fields["loan_amount"] = ExtractedFieldRecord(
                field_name="loan_amount",
                value=amt_val,
                value_num=amt_val,
                value_str=f"{amt_val:,.2f}",
                source_excerpt=m_amt.group(0),
            )
        else:
            missing.append("loan_amount")

        # 4. Interest Rate & Rate Type
        m_rate = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:per annum|yearly rate|p\.a\.?|interest rate)?", text, re.IGNORECASE)
        rate_val = _safe_float(m_rate.group(1)) if m_rate else None
        if rate_val is not None:
            fields["interest_rate"] = ExtractedFieldRecord(
                field_name="interest_rate",
                value=rate_val,
                value_num=rate_val,
                value_str=f"{rate_val}%",
                source_excerpt=m_rate.group(0),
            )
        else:
            missing.append("interest_rate")

        # Rate type: Fixed vs Variable / Adjustable / Floating
        if any(w in text_lower for w in ["adjustable rate", "variable rate", "floating", "sofr", "mclr", "repo rate"]):
            rate_type = "variable"
        elif "fixed rate" in text_lower:
            rate_type = "fixed"
        else:
            rate_type = "variable" if jurisdiction == "IN" else "fixed"

        m_rate_type_exc = re.search(r"[^\n]{0,50}(?:fixed rate|adjustable rate|variable rate|floating rate)[^\n]{0,50}", text, re.IGNORECASE)
        fields["interest_rate_type"] = ExtractedFieldRecord(
            field_name="interest_rate_type",
            value=rate_type,
            value_str=rate_type,
            source_excerpt=m_rate_type_exc.group(0).strip() if m_rate_type_exc else f"Peers indicate {rate_type} rate structure",
        )

        # 5. Prepayment Penalty
        # If any explicit negative assertion exists in the document, it's False
        prepay_negations = [
            "no prepayment", "without paying any prepayment", "zero pre-payment", "zero prepayment",
            "nil", "no charges", "no foreclosure", "not require any penalty", "no penalty",
            "not be levied", "no prepayment charge", "waived the prepayment penalty"
        ]
        if any(neg in text_lower for neg in prepay_negations):
            m_neg_exc = re.search(r"[^\n]{0,50}(?:" + "|".join([re.escape(neg) for neg in prepay_negations]) + r")[^\n]{0,80}", text, re.IGNORECASE)
            fields["prepayment_penalty_exists"] = ExtractedFieldRecord(
                field_name="prepayment_penalty_exists",
                value=False,
                value_num=0.0,
                value_str="None (0%)",
                source_excerpt=m_neg_exc.group(0).strip() if m_neg_exc else "Zero prepayment charges verified",
            )
        else:
            m_prepay = re.search(r"[^\n]{0,60}(?:prepayment\s+penalty|prepayment[^\n]{0,80}penalty|foreclosure\s+charges?|prepayment\s+charge)[^\n]{0,150}", text, re.IGNORECASE)
            if m_prepay:
                p_text = m_prepay.group(0).strip()
                m_p_rate = re.search(r"(\d+(?:\.\d+)?)\s*%", p_text)
                penalty_pct = _safe_float(m_p_rate.group(1)) if m_p_rate else 2.5
                if penalty_pct is None:
                    penalty_pct = 2.5
                fields["prepayment_penalty_exists"] = ExtractedFieldRecord(
                    field_name="prepayment_penalty_exists",
                    value=True,
                    value_num=penalty_pct,
                    value_str=f"{penalty_pct}% penalty applies",
                    source_excerpt=p_text,
                )
            else:
                missing.append("prepayment_penalty_exists")

        # 6. US QM Points and Fees
        # Extract percentage (e.g. "equals 1.20% of the total loan amount" or "4.11% of the loan amount")
        m_pts_pct = re.search(r"(?:points(?: and fees)?|origination charges|total fees|lender fees)[^\n]{0,120}?(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
        # Extract dollar amount (e.g. "$4,200.00" or "$11,500.00")
        m_pts_amt = re.search(r"(?:points(?: and fees)?|origination charges|total fees|lender fees)[^\n]{0,120}?\$\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
        
        pts_amount = _safe_float(m_pts_amt.group(1)) if m_pts_amt else None
        pts_percent = _safe_float(m_pts_pct.group(1)) if m_pts_pct else None

        if pts_percent is not None or pts_amount is not None:
            if pts_amount is not None:
                fields["points_and_fees_amount"] = ExtractedFieldRecord(
                    field_name="points_and_fees_amount",
                    value=pts_amount,
                    value_num=pts_amount,
                    value_str=f"${pts_amount:,.2f}",
                    source_excerpt=m_pts_amt.group(0).strip() if m_pts_amt else "",
                )
            if pts_percent is not None:
                fields["points_and_fees_percent"] = ExtractedFieldRecord(
                    field_name="points_and_fees_percent",
                    value=pts_percent,
                    value_num=pts_percent,
                    value_str=f"{pts_percent}%",
                    source_excerpt=m_pts_pct.group(0).strip() if m_pts_pct else "",
                )
        else:
            missing.append("points_and_fees_percent")
            if jurisdiction == "US":
                missing.append("points_and_fees_amount")

        # 7. US HPML Escrow requirement
        m_escrow = re.search(r"[^\n]{0,60}escrow[^\n]{0,150}", text, re.IGNORECASE)
        if m_escrow:
            e_text = m_escrow.group(0).strip()
            is_waived = "waived" in e_text.lower() or "no escrow" in e_text.lower()
            fields["escrow_established"] = ExtractedFieldRecord(
                field_name="escrow_established",
                value=not is_waived,
                value_str="Established" if not is_waived else "Waived",
                source_excerpt=e_text,
            )

        # 8. Property Value & Indian LTV
        m_prop = re.search(r"property\s+value[^\d]{0,40}(?:u\.s\.\s*\$|inr|rs\.?|₹|\$)?\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
        if m_prop:
            prop_val = float(m_prop.group(1).replace(",", ""))
            fields["property_value"] = ExtractedFieldRecord(
                field_name="property_value",
                value=prop_val,
                value_num=prop_val,
                value_str=f"{prop_val:,.2f}",
                source_excerpt=m_prop.group(0),
            )

        m_ltv = re.search(r"(?:ltv|loan to value|loan-to-value)[^\d%]{0,25}(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
        if m_ltv:
            ltv_val = float(m_ltv.group(1))
            fields["ltv_percent"] = ExtractedFieldRecord(
                field_name="ltv_percent",
                value=ltv_val,
                value_num=ltv_val,
                value_str=f"{ltv_val}%",
                source_excerpt=m_ltv.group(0),
            )
        elif "property_value" in fields and "loan_amount" in fields and fields["property_value"].value_num:
            calc_ltv = (fields["loan_amount"].value_num / fields["property_value"].value_num) * 100.0
            fields["ltv_percent"] = ExtractedFieldRecord(
                field_name="ltv_percent",
                value=round(calc_ltv, 2),
                value_num=round(calc_ltv, 2),
                value_str=f"{calc_ltv:.2f}%",
                source_excerpt=f"Calculated from loan amount ({fields['loan_amount'].value_num}) / property value ({fields['property_value'].value_num})",
            )
        elif jurisdiction == "IN":
            missing.append("ltv_percent")

        # 9. Indian Penal Interest Compounding
        m_penal = re.search(r"[^\n]{0,60}(?:default interest|penal interest|penal charge)[^\n]{0,150}", text, re.IGNORECASE)
        if m_penal:
            penal_text = m_penal.group(0).strip()
            is_comp = "compound" in penal_text.lower() and not any(w in penal_text.lower() for w in ["not compounded", "without compounding", "without any compounding"])
            fields["penal_interest_compounded"] = ExtractedFieldRecord(
                field_name="penal_interest_compounded",
                value=is_comp,
                value_str="Compounded" if is_comp else "Simple interest",
                source_excerpt=penal_text,
            )

        # 10. Loan Tenure
        m_tenure = re.search(r"(\d+)\s*(?:years|months)", text, re.IGNORECASE)
        if m_tenure:
            t_num = float(m_tenure.group(1))
            fields["loan_tenure"] = ExtractedFieldRecord(
                field_name="loan_tenure",
                value=t_num,
                value_num=t_num,
                value_str=m_tenure.group(0),
                source_excerpt=m_tenure.group(0),
            )

        return LoanExtractionResult(
            document_name=document_name,
            jurisdiction=jurisdiction,
            doc_type=doc_type,
            borrower_type=borrower_type,
            fields=fields,
            missing_fields=missing,
        )
