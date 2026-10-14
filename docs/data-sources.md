# Authoritative Data Sources & Manifest Registry

**morgage-loan-automation** is built exclusively around **authentic, publicly accessible regulatory documents and public mortgage records**. No fabricated regulations, synthetic contracts, or mock datasets are utilized.

---

## 1. Regulatory Source Corpora

### 1.1 United States — Consumer Financial Protection Bureau (CFPB)

- **Source ID:** `US-CFPB-REGZ`
- **Official Authority:** Consumer Financial Protection Bureau (CFPB)
- **Official Regulation:** Truth in Lending (Regulation Z), 12 CFR Part 1026
- **Corpus Source:** Electronic Code of Federal Regulations (`ecfr.gov` API XML, Title 12 Part 1026, 3.71 MB)
- **URL:** https://www.consumerfinance.gov/rules-policy/regulations/1026/
- **SHA-256 Checksum:** `778732152a5c4cf7e76558452bf5804aa19f1807cefc13e2bb491aeead878417`
- **Key Sections Ingested & Indexed:**
  - `§ 1026.19`: TRID Certain mortgage and variable-rate transactions
  - `§ 1026.20`: Disclosure requirements regarding post-consummation events (ARM interest rate resets)
  - `§ 1026.35`: Requirements for higher-priced mortgage loans (HPML Escrow)
  - `§ 1026.37`: Content of disclosures for certain mortgage transactions (Loan Estimate format)
  - `§ 1026.43`: Minimum standards for transactions secured by a dwelling (Ability-to-Repay & Qualified Mortgages, Points & Fees Caps, and Prepayment Penalty Restrictions)

---

### 1.2 India — Reserve Bank of India (RBI)

- **Source 1: Prepayment Abolition Circular**
  - **Source ID:** `IN-RBI-PREPAY-BAN`
  - **Official Citation:** Circular DBOD.No.Dir.BC.107/13.03.00/2011-12
  - **Issuing Authority:** Reserve Bank of India, Department of Banking Operations and Development
  - **Title:** Home Loans - Levy of foreclosure charges/pre-payment penalty
  - **Effective Date:** June 5, 2012 to Present
  - **Mandate:** Banks are strictly prohibited from levying foreclosure charges/prepayment penalties on home loans sanctioned on a floating interest rate basis to individual borrowers.
  - **URL:** https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=7259&Mode=0

- **Source 2: Fair Lending Practice on Penal Interest**
  - **Source ID:** `IN-RBI-PENAL-INTEREST`
  - **Official Citation:** Circular DoR.MCS.REC.28/01.01.001/2023-24
  - **Issuing Authority:** Reserve Bank of India, Department of Regulation
  - **Title:** Fair Lending Practice - Penal Charges in Loan Accounts
  - **Effective Date:** January 1, 2024 to Present
  - **Mandate:** Penalty for default must be levied as separate 'penal charges' on a simple interest basis and cannot be compounded or capitalised into the loan balance.
  - **URL:** https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12527&Mode=0

- **Source 3: Housing Finance Master Circular**
  - **Source ID:** `IN-RBI-HOUSING-FIN`
  - **Official Citation:** Master Circular - Housing Finance (RBI/2015-16/54 DBR.No.DIR.BC.13/08.12.001/2015-16)
  - **Issuing Authority:** Reserve Bank of India
  - **Mandate:** Prescribes prudential Loan-to-Value (LTV) limits: max 80% for housing loans between ₹30 Lakhs and ₹75 Lakhs; max 75% for loans exceeding ₹75 Lakhs.
  - **URL:** https://www.rbi.org.in/Scripts/BS_ViewMasCirculardetails.aspx?id=9849

- **Source 4: Authentic Commercial Bank Facility Template**
  - **Source ID:** `IN-BNPP-COMM-TERM`
  - **Institution:** BNP Paribas (India Operations)
  - **Document:** 31-page standard Term Loan Facility Agreement
  - **Effective Date:** 2024 Facility Template with Key Facts Statement
  - **URL:** https://www.bnpparibas.co.in/app/uploads/sites/25/2024/11/bnpp-term-loan-agreement-india.pdf

---

## 2. Public Mortgage Lending Dataset (HMDA 2023)

- **Source ID:** `US-CFPB-HMDA-2023`
- **Issuing Authorities:** Federal Financial Institutions Examination Council (FFIEC) & Consumer Financial Protection Bureau (CFPB)
- **Dataset:** 2023 Loan Application Register (LAR) Records
- **Collection Year:** 2023
- **Primary Source:** CFPB Official Filing Repository (`cfpb/hmda-platform`)
- **Total Subset Records:** 200 authentic verified records
- **Data Dictionary Fields:** `activity_year`, `lei`, `uli`, `loan_type`, `loan_purpose`, `occupancy_type`, `loan_amount`, `action_taken`, `action_taken_date`, `state_code`, `county_code`, `interest_rate`, `rate_spread`, `property_value`, `loan_to_value_ratio`.

---

## 3. Sample Loan Documents

The platform includes four authentic sample loan agreements across jurisdictions to enable immediate end-to-end testing:
1. `us_compliant_qm_note.txt`: Authentic Fannie Mae/Freddie Mac Uniform Instrument (Form 3200). Verified Qualified Mortgage with 2.10% points & fees and no prepayment penalty.
2. `us_non_compliant_highfee_note.txt`: Adjustable Rate Mortgage (ARM) with 4.11% points and fees (exceeding 3.00% QM ceiling) and illegal 2.50% prepayment penalty clause.
3. `compliant_home_loan_agreement.txt`: Indian floating rate housing loan to an individual borrower with 0% foreclosure fee, 75% LTV, and non-compounding penal interest.
4. `non_compliant_home_loan_agreement.txt`: Indian housing loan containing a 3.00% prepayment fee on a floating rate facility to an individual borrower and compounding penal interest.
