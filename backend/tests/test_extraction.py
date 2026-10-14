"""
test_extraction.py
==================
Tests for loan document structured term extraction and provenance tracking.
"""

from backend.app.services.loan_extraction.term_extractor import LoanTermExtractor


def test_us_qm_note_extraction():
    extractor = LoanTermExtractor()
    sample_text = """
    NOTE
    JULY 15, 2023
    SPRINGFIELD, ILLINOIS
    1. BORROWER'S PROMISE TO PAY
    In return for a loan that I have received, I promise to pay U.S. $350,000.00 (this amount is called "Principal").
    2. INTEREST
    Interest will be charged on unpaid principal until the full amount of Principal has been paid.
    I will pay interest at a yearly rate of 6.250%.
    3. PAYMENTS
    I will make a payment every month on the first day of each month.
    4. BORROWER'S RIGHT TO PREPAY
    I have the right to make payments of Principal at any time before they are due.
    A prepayment of all or part of the Principal will not require any penalty.
    Total upfront points and fees charged do not exceed 2.10% of total loan amount.
    Annual Percentage Rate (APR) is 6.35%.
    """

    res = extractor.extract_terms(sample_text, document_name="test_us_note.txt")
    assert res.jurisdiction == "US"
    assert "loan_amount" in res.fields
    assert res.fields["loan_amount"].value_num == 350000.0
    assert "interest_rate" in res.fields
    assert res.fields["interest_rate"].value_num == 6.25
    assert "points_and_fees_percent" in res.fields
    assert res.fields["points_and_fees_percent"].value_num == 2.1
    assert "prepayment_penalty_exists" in res.fields
    assert res.fields["prepayment_penalty_exists"].value is False


def test_in_housing_loan_extraction():
    extractor = LoanTermExtractor()
    sample_text = """
    HOUSING LOAN AGREEMENT
    Date: 12th October 2023, Bengaluru, Karnataka
    Between State Bank of India and Mr. Rajesh Sharma (Individual Borrower).
    1. SANCTION OF LOAN
    The Bank agrees to lend and the Borrower agrees to borrow Rs. 4,500,000 (Rupees Forty Five Lakhs only).
    2. INTEREST RATE
    Floating rate of interest linked to EBLR at 8.75% per annum.
    3. PREPAYMENT / FORECLOSURE
    No foreclosure charges or prepayment penalties shall be levied since this is an individual floating rate housing loan.
    4. PENALTY ON DEFAULT
    In case of default, penal charges shall be levied at 2% p.a. without any compounding or capitalization.
    Property Value assessed at Rs. 6,000,000.
    """

    res = extractor.extract_terms(sample_text, document_name="test_in_loan.txt")
    assert res.jurisdiction == "IN"
    assert res.borrower_type == "individual"
    assert "loan_amount" in res.fields
    assert res.fields["loan_amount"].value_num == 4500000.0
    assert "interest_rate_type" in res.fields
    assert res.fields["interest_rate_type"].value == "variable"
    assert "prepayment_penalty_exists" in res.fields
    assert res.fields["prepayment_penalty_exists"].value is False
    assert "property_value" in res.fields
    assert res.fields["property_value"].value_num == 6000000.0
    assert "ltv_percent" in res.fields
    assert round(res.fields["ltv_percent"].value_num, 1) == 75.0
    assert "penal_interest_compounded" in res.fields
    assert res.fields["penal_interest_compounded"].value is False
