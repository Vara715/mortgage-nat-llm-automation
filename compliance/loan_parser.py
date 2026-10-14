"""
loan_parser.py
==============
Implements Loan Form Processing from Slide 8:
- Classify document type (Home Loan, Commercial Term Loan, Retail Credit Agreement)
- Extract fields: interest rate, interest rate type, tenure, foreclosure charges,
  penal charges, loan amount, property value, LTV, NRI provisions, grievance details.
"""

import re
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from extraction.pdf_extractor import ExtractedDocument


class ExtractedLoanTerms(BaseModel):
    document_name: str
    document_type: str = Field(..., description="e.g. Home Loan Agreement, Commercial Bank Term Loan")
    borrower_name: Optional[str] = None
    borrower_type: str = Field(default="individual", description="'individual' or 'corporate'")
    loan_type: str = Field(default="housing_loan", description="'housing_loan', 'commercial_term_loan', etc.")
    sanctioned_amount: Optional[float] = None
    property_value: Optional[float] = None
    ltv_percent: Optional[float] = None
    interest_rate_percent: Optional[float] = None
    interest_rate_type: str = Field(default="floating", description="'floating' or 'fixed'")
    tenure_years: Optional[float] = None
    
    # Specific clauses
    prepayment_clause_text: Optional[str] = None
    prepayment_charges_rate_percent: Optional[float] = None
    has_prepayment_penalty: bool = False
    
    penal_charges_clause_text: Optional[str] = None
    penal_charge_rate_percent: Optional[float] = None
    is_penal_interest_compounded: bool = False
    
    nri_clause_text: Optional[str] = None
    has_nri_borrower: bool = False
    
    grievance_clause_present: bool = False
    kfs_schedule_present: bool = False
    
    raw_extracted_fields: Dict[str, Any] = Field(default_factory=dict)


class LoanDocumentParser:
    """
    Extracts key financial and legal terms from loan agreement text or ExtractedDocument.
    """

    def parse_text(self, text: str, document_name: str = "Loan_Document") -> ExtractedLoanTerms:
        text_lower = text.lower()

        # 1. Classify document type
        if "housing loan" in text_lower or "home loan" in text_lower:
            doc_type = "Home Loan Agreement"
            loan_type = "housing_loan"
        elif "term loan facility" in text_lower or "commercial" in text_lower or "corporate" in text_lower or "bnp paribas" in text_lower:
            doc_type = "Commercial Bank Term Loan"
            loan_type = "commercial_term_loan"
        else:
            doc_type = "Retail Credit Agreement"
            loan_type = "general_credit"

        # 2. Determine borrower type specifically from the Borrower definition or party section
        borrower_type = "individual"
        m_borrower_sec = re.search(r"[^\n]{0,150}(?:borrower|party of the second part|customer)[^\n]{0,150}", text, re.IGNORECASE)
        borrower_snippet = m_borrower_sec.group(0).lower() if m_borrower_sec else text_lower

        if any(w in borrower_snippet for w in ["pvt ltd", "private limited", "public limited", "company within the meaning", "incorporated under the companies act", "partnership firm", "llp", "corporate"]):
            borrower_type = "corporate"
        elif any(w in borrower_snippet for w in ["individual borrower", "mr.", "mrs.", "ms.", "natural person"]):
            borrower_type = "individual"
        elif "individual" in text_lower and not any(w in text_lower for w in ["pvt ltd", "private limited", "company within the meaning of"]):
            borrower_type = "individual"

        # 3. Extract interest rate and rate type
        rate_val = None
        m_rate = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:p\.?a\.?|per annum|interest rate)", text, re.IGNORECASE)
        if not m_rate:
            m_rate = re.search(r"interest rate\s*(?:of|is|:)?\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
        if m_rate:
            rate_val = float(m_rate.group(1))

        if "floating" in text_lower or "benchmark" in text_lower or "mclr" in text_lower or "repo rate" in text_lower:
            rate_type = "floating"
        elif "fixed rate" in text_lower:
            rate_type = "fixed"
        else:
            rate_type = "floating"  # Default in Indian retail mortgage market

        # 4. Extract loan amount & property value
        sanctioned_amt = None
        m_amt = re.search(r"(?:sanctioned loan amount|loan amount|principal amount)\s*(?:is|of|:)?\s*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
        if m_amt:
            try:
                sanctioned_amt = float(m_amt.group(1).replace(",", ""))
            except ValueError:
                pass

        prop_val = None
        m_prop = re.search(r"(?:property value|market value|cost of property|property cost)\s*(?:is|of|:)?\s*(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE)
        if m_prop:
            try:
                prop_val = float(m_prop.group(1).replace(",", ""))
            except ValueError:
                pass

        # Calculate or extract LTV
        ltv = None
        m_ltv = re.search(r"(?:ltv|loan to value|loan-to-value)\s*(?:ratio)?\s*(?:is|of|:)?\s*(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
        if m_ltv:
            ltv = float(m_ltv.group(1))
        elif sanctioned_amt and prop_val and prop_val > 0:
            ltv = round((sanctioned_amt / prop_val) * 100, 2)

        # 5. Extract tenure
        tenure = None
        m_tenure = re.search(r"(?:tenure|loan term|period)\s*(?:is|of|:)?\s*(\d+)\s*(?:years|yrs)", text, re.IGNORECASE)
        if m_tenure:
            tenure = float(m_tenure.group(1))
        else:
            m_tenure_m = re.search(r"(?:tenure|loan term|period)\s*(?:is|of|:)?\s*(\d+)\s*(?:months)", text, re.IGNORECASE)
            if m_tenure_m:
                tenure = round(float(m_tenure_m.group(1)) / 12, 1)

        # 6. Extract Prepayment / Foreclosure clause
        prepay_clause = None
        prepay_rate = None
        has_prepay_penalty = False

        m_prepay_sec = re.search(r"(?:prepayment|foreclosure|pre-payment)[^\n]*\n(?:[^\n]+\n){1,10}", text, re.IGNORECASE)
        if m_prepay_sec:
            prepay_clause = m_prepay_sec.group(0).strip()
        else:
            m_prepay_sec = re.search(r"((?:prepayment|foreclosure|pre-payment)[^\.\n]*(?:[\.\n][^\.\n]*){1,5})", text, re.IGNORECASE)
            if m_prepay_sec:
                prepay_clause = m_prepay_sec.group(1).strip()

        if prepay_clause:
            p_clause_lower = prepay_clause.lower()
            m_prate = re.search(r"(\d+(?:\.\d+)?)\s*%", prepay_clause)
            if m_prate and not any(w in p_clause_lower for w in ["no", "zero", "nil", "0%"]):
                prepay_rate = float(m_prate.group(1))
                has_prepay_penalty = prepay_rate > 0
            elif any(w in p_clause_lower for w in ["subject to applicable prepayment charges", "break costs", "penalty applies", "prepayment penalty of"]):
                has_prepay_penalty = True
                prepay_rate = prepay_rate or 2.0
            elif any(w in p_clause_lower for w in ["nil", "no foreclosure charges", "no prepayment", "without any charge", "zero"]):
                has_prepay_penalty = False
                prepay_rate = 0.0

        # 7. Extract Penal Interest / Default Charges clause
        penal_clause = None
        penal_rate = None
        is_compounded = False

        m_penal_sec = re.search(r"(?:default interest|default charge|penal interest|penal charge|late fee|overdue interest)[^\n]*\n(?:[^\n]+\n){1,10}", text, re.IGNORECASE)
        if m_penal_sec:
            penal_clause = m_penal_sec.group(0).strip()
        else:
            m_penal_sec = re.search(r"((?:default interest|default charge|penal interest|penal charge|late fee)[^\.\n]*(?:[\.\n][^\.\n]*){1,5})", text, re.IGNORECASE)
            if m_penal_sec:
                penal_clause = m_penal_sec.group(1).strip()

        if penal_clause:
            p_lower = penal_clause.lower()
            m_penal_rate = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:per month|p\.m\.|p\.a\.|per annum)?", penal_clause, re.IGNORECASE)
            if m_penal_rate:
                penal_rate = float(m_penal_rate.group(1))

            has_compounding_word = any(w in p_lower for w in ["compound", "capitalised", "capitalized", "added to principal"])
            is_negated = any(
                neg in p_lower
                for neg in [
                    "not be compounded", "not compounded", "no compounding", "without compounding",
                    "shall not be compounded", "not be capitalised", "not be capitalized",
                    "without being compounded", "shall not be added to principal"
                ]
            )
            if has_compounding_word and not is_negated:
                is_compounded = True

        # 8. Check NRI clauses
        nri_clause = None
        has_nri = False
        m_nri = re.search(r"((?:non-resident|nri)[^\.\n]*(?:[\.\n][^\.\n]*){1,4})", text, re.IGNORECASE)
        if m_nri:
            nri_clause = m_nri.group(1).strip()
            has_nri = True

        # 9. Key Facts Statement & Grievance redressal
        kfs_present = "key facts statement" in text_lower or "kfs" in text_lower
        grievance_present = "nodal officer" in text_lower or "grievance redressal" in text_lower

        return ExtractedLoanTerms(
            document_name=document_name,
            document_type=doc_type,
            borrower_type=borrower_type,
            loan_type=loan_type,
            sanctioned_amount=sanctioned_amt,
            property_value=prop_val,
            ltv_percent=ltv,
            interest_rate_percent=rate_val,
            interest_rate_type=rate_type,
            tenure_years=tenure,
            prepayment_clause_text=prepay_clause,
            prepayment_charges_rate_percent=prepay_rate,
            has_prepayment_penalty=has_prepay_penalty,
            penal_charges_clause_text=penal_clause,
            penal_charge_rate_percent=penal_rate,
            is_penal_interest_compounded=is_compounded,
            nri_clause_text=nri_clause,
            has_nri_borrower=has_nri,
            grievance_clause_present=grievance_present,
            kfs_schedule_present=kfs_present,
            raw_extracted_fields={
                "doc_type": doc_type,
                "borrower_type": borrower_type,
                "rate_type": rate_type,
            },
        )

    def parse_document(self, doc: ExtractedDocument) -> ExtractedLoanTerms:
        return self.parse_text(doc.full_text, document_name=doc.source_file)
