"""
Creates sample loan agreements (both compliant and non-compliant) for compliance auditing testing.
"""

from pathlib import Path

OUT_DIR = Path("data/real_docs/sample_loan_agreements")
OUT_DIR.mkdir(parents=True, exist_ok=True)

COMPLIANT_LOAN = """HOME LOAN AGREEMENT
Agreement Reference: HL/2026/IND/88492
Date of Execution: 15 January 2026

BETWEEN:
Apex Housing Finance Bank Limited, a banking company licensed under the Banking Regulation Act, 1949 (hereinafter referred to as the 'Lender');
AND
Mr. Ramesh K. Sharma, residing at Flat 402, Green Meadows, Bengaluru - 560034 (hereinafter referred to as the 'Borrower', an individual borrower).

1. SANCTION DETAILS & FACILITY
1.1 Facility: Individual Housing Loan facility for purchase of residential property.
1.2 Sanctioned Loan Amount: Rs. 50,00,000/- (Rupees Fifty Lakhs only).
1.3 Property Market Value: Rs. 70,00,000/- (Rupees Seventy Lakhs only).
1.4 Loan-to-Value (LTV) Ratio: 71.4%, with borrower margin contribution of 28.6% funded from verifiable personal sources.
1.5 Loan Tenure: 20 years (240 monthly installments).

2. INTEREST RATE & REPAYMENT
2.1 Interest Rate: 8.50% per annum, floating rate pegged to the RBI External Benchmark (Repo Rate + spread of 2.00%).
2.2 Repayment: Equated Monthly Installment (EMI) of Rs. 43,391/- per month.

3. PREPAYMENT & FORECLOSURE CHARGES
3.1 The Borrower shall be entitled to prepay the loan facility in part or in full at any time during the tenure.
3.2 In strict adherence to Reserve Bank of India (RBI) circular DBOD.No.Dir.BC.107/13.03.00/2011-12, NO FORECLOSURE CHARGES OR PREPAYMENT PENALTIES shall be levied on this home loan extended on a floating interest rate basis to an individual borrower. Zero pre-payment fee applies.

4. DEFAULT & PENAL CHARGES
4.1 In case of default in payment of any monthly installment on the due date, penal charges at the rate of 2.0% per annum shall be levied on the overdue installment amount.
4.2 In compliance with RBI directions on Fair Lending Practice (Penal Charges in Loan Accounts), all penal charges shall be levied on a simple interest basis and shall not be compounded or capitalised into the principal balance.

5. GRIEVANCE REDRESSAL & KEY FACTS STATEMENT
5.1 Principal Nodal Officer for Grievance Redressal: Mr. S. Ramanathan, General Manager, Apex Bank Bhavan, Bengaluru. Email: nodalofficer@apexbank.example.com, Phone: 080-22998877.
5.2 Annexure A contains the standard Key Facts Statement (KFS) containing the Annual Percentage Rate (APR) and amortisation schedule.
"""

NON_COMPLIANT_LOAN = """HOME LOAN AGREEMENT
Agreement Reference: HL/2026/NC/10294
Date of Execution: 20 February 2026

BETWEEN:
Metro Credit & Finance Bank Limited (hereinafter referred to as the 'Lender');
AND
Mrs. Ananya Verma, residing at C-12, Sector 15, Noida - 201301 (hereinafter referred to as the 'Borrower', an individual borrower).

1. FACILITY & QUANTUM
1.1 Loan Type: Individual Housing Loan Facility.
1.2 Sanctioned Loan Amount: Rs. 65,00,000/- (Rupees Sixty-Five Lakhs only).
1.3 Property Cost: Rs. 70,00,000/- (Rupees Seventy Lakhs only).
1.4 Loan-to-Value (LTV) Ratio: 92.8% of property cost, including financing of registration and stamp duty charges.
1.5 Loan Term: 25 years (300 monthly installments).

2. INTEREST RATE
2.1 Interest Rate: 9.25% per annum on a Floating Rate benchmark basis.

3. PREPAYMENT PENALTY & FORECLOSURE CHARGES
3.1 In the event the Borrower prepays the loan in part or forecloses the entire outstanding loan prior to maturity, the Lender shall levy a prepayment penalty of 2.50% on the prepaid amount plus applicable GST.
3.2 Break costs and administrative exit charges of Rs. 10,000 shall also apply on premature closure.

4. DEFAULT INTEREST & COMPOUNDING
4.1 On any overdue installment, default interest at 2.5% per month shall be charged.
4.2 Default interest shall be compounded monthly and capitalised into the outstanding principal loan amount on each billing cycle.

5. GENERAL TERMS
5.1 The Borrower agrees to abide by the standard credit terms of the Bank.
"""

(OUT_DIR / "compliant_home_loan_agreement.txt").write_text(COMPLIANT_LOAN, encoding="utf-8")
(OUT_DIR / "non_compliant_home_loan_agreement.txt").write_text(NON_COMPLIANT_LOAN, encoding="utf-8")
print("Generated sample loan agreements successfully.")
