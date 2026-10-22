"""
calculate_loan.py
=================
Customer financial advisory calculator CLI for mortgage_assistant.

Features:
1. EMI Calculator (Reducing balance, total repayment, interest breakdown)
2. Eligibility Advisor (FOIR / Debt-to-income limits & counterfactual advice)
3. Prepayment Advisor (Tenure reduction & interest savings calculation)

Usage Examples:
    # 1. Calculate EMI:
    python scripts/calculate_loan.py emi --amount 5000000 --rate 8.5 --tenure 20

    # 2. Check Eligibility (Counterfactual recommendations if exceeded):
    python scripts/calculate_loan.py eligibility --income 150000 --requested-loan 6000000 --rate 8.5 --tenure 20 --existing-emi 15000

    # 3. Calculate Prepayment Interest Savings:
    python scripts/calculate_loan.py prepayment --amount 5000000 --rate 8.5 --tenure 20 --months-paid 24 --prepay 500000

    # 4. Interactive Mode:
    python scripts/calculate_loan.py
"""

import sys
import math
import argparse


def calculate_emi(principal: float, annual_rate_percent: float, tenure_years: float) -> tuple[float, int, float]:
    r = (annual_rate_percent / 12) / 100
    n = round(tenure_years * 12)
    if r == 0:
        return principal / n, n, r
    f = (1 + r) ** n
    return principal * r * f / (f - 1), n, r


def outstanding_balance(principal: float, r: float, n_months: int, months_elapsed: int) -> float:
    if r == 0:
        return principal * (1 - months_elapsed / n_months)
    return principal * ((1 + r) ** n_months - (1 + r) ** months_elapsed) / ((1 + r) ** n_months - 1)


def run_emi(principal: float, rate: float, tenure: float):
    emi, n_months, _ = calculate_emi(principal, rate, tenure)
    total_payment = emi * n_months
    total_interest = total_payment - principal

    print("\n" + "=" * 65)
    print("  CUSTOMER HOME LOAN EMI & AMORTIZATION BREAKDOWN")
    print("=" * 65)
    print(f"  Loan Principal       : Rs. {principal:,.2f}")
    print(f"  Annual Interest Rate : {rate:.2f}%")
    print(f"  Tenure               : {tenure:.1f} years ({n_months} installments)")
    print("-" * 65)
    print(f"  -> Monthly EMI       : Rs. {emi:,.2f} / month")
    print(f"  -> Total Repayment   : Rs. {total_payment:,.2f}")
    print(f"  -> Total Interest    : Rs. {total_interest:,.2f} ({total_interest / principal * 100:.1f}% of loan)")
    print("=" * 65 + "\n")


def run_eligibility(income: float, requested_loan: float, rate: float, tenure: float, existing_emi: float = 0.0, foir_limit_pct: float = 50.0):
    foir_limit = foir_limit_pct / 100.0
    new_emi, n_months, r = calculate_emi(requested_loan, rate, tenure)
    total_monthly_debt = existing_emi + new_emi
    foir = total_monthly_debt / income

    print("\n" + "=" * 65)
    print("  BORROWER ELIGIBILITY & FOIR ASSESSMENT")
    print("=" * 65)
    print(f"  Gross Monthly Income : Rs. {income:,.2f}")
    print(f"  Existing Monthly EMI : Rs. {existing_emi:,.2f}")
    print(f"  Requested Loan       : Rs. {requested_loan:,.2f} ({rate:.2f}% for {tenure} yrs)")
    print(f"  New Proposed EMI     : Rs. {new_emi:,.2f} / month")
    print(f"  Total Monthly Debt   : Rs. {total_monthly_debt:,.2f}")
    print(f"  Current FOIR Ratio   : {foir * 100:.1f}% (Policy Cap: {foir_limit_pct:.0f}%)")
    print("-" * 65)

    if foir <= foir_limit:
        print("  STATUS: [ELIGIBLE]")
        print("  Your total debt obligations are within the bank's 50% FOIR policy limit.")
    else:
        print("  STATUS: [INELIGIBLE — EXCEEDS 50% FOIR LIMIT]")
        print("\n  Counterfactual Recommendations (Smallest changes to qualify):")
        
        max_allowed_new_emi = (income * foir_limit) - existing_emi
        
        if max_allowed_new_emi <= 0:
            print("  1. Existing debt obligations already consume >= 50% of your income.")
            print(f"     Reduce existing debt by Rs. {existing_emi - (income * foir_limit):,.2f}/month first.")
        else:
            # 1. Income increase needed
            income_needed = total_monthly_debt / foir_limit
            print(f"  1. Increase gross monthly income by Rs. {income_needed - income:,.2f} (to Rs. {income_needed:,.2f})")

            # 2. Reduce loan amount
            f = (1 + r) ** n_months
            p_max = max_allowed_new_emi * (f - 1) / (r * f)
            print(f"  2. Reduce requested loan amount by Rs. {requested_loan - p_max:,.2f} (to Rs. {p_max:,.2f})")

            # 3. Extend tenure
            if max_allowed_new_emi > r * requested_loan:
                n_needed = math.log(max_allowed_new_emi / (max_allowed_new_emi - r * requested_loan)) / math.log(1 + r)
                years_needed = n_needed / 12
                if years_needed <= 30:
                    print(f"  3. Extend tenure by ~{years_needed - tenure:.1f} years (to {years_needed:.1f} years)")

    print("=" * 65 + "\n")


def run_prepayment(principal: float, rate: float, tenure: float, months_elapsed: int, extra_payment: float):
    emi, n_months, r = calculate_emi(principal, rate, tenure)
    
    if months_elapsed >= n_months:
        print("[ERROR] months_elapsed must be less than the total loan tenure in months.")
        return

    balance = outstanding_balance(principal, r, n_months, months_elapsed)
    remaining_months_original = n_months - months_elapsed

    print("\n" + "=" * 65)
    print("  PREPAYMENT ADVISOR & INTEREST SAVINGS ANALYSIS")
    print("=" * 65)
    print(f"  Original Loan Principal    : Rs. {principal:,.2f} ({rate:.2f}% for {tenure} yrs)")
    print(f"  EMIs Paid So Far           : {months_elapsed} months")
    print(f"  Outstanding Loan Balance   : Rs. {balance:,.2f}")
    print(f"  Proposed One-Time Prepay   : Rs. {extra_payment:,.2f}")
    print("-" * 65)

    if extra_payment >= balance:
        print(f"  STATUS: Full closure! This prepayment completely settles the remaining balance.")
    else:
        new_balance = balance - extra_payment
        if emi <= r * new_balance:
            print("  [ERROR] Monthly EMI is too small relative to remaining balance.")
            return

        n_new = math.log(emi / (emi - r * new_balance)) / math.log(1 + r)
        months_saved = remaining_months_original - n_new
        interest_saved = (emi * remaining_months_original) - (extra_payment + emi * n_new)

        print(f"  New Outstanding Balance    : Rs. {new_balance:,.2f}")
        print(f"  Monthly EMI (Unchanged)    : Rs. {emi:,.2f} / month")
        print(f"  Original Remaining Tenure  : {remaining_months_original} months ({remaining_months_original / 12:.1f} years)")
        print(f"  New Remaining Tenure       : ~{n_new:.1f} months ({n_new / 12:.1f} years)")
        print(f"  Tenure Reduced By          : ~{months_saved:.1f} months ({months_saved / 12:.1f} years!)")
        print(f"  ESTIMATED INTEREST SAVED   : Rs. {interest_saved:,.2f}")

    print("=" * 65 + "\n")


def interactive_menu():
    while True:
        print("=" * 55)
        print("   MORTGAGE CUSTOMER FINANCIAL CALCULATOR")
        print("=" * 55)
        print("  1. Calculate Monthly EMI & Total Interest")
        print("  2. Check FOIR Loan Eligibility (with Recommendations)")
        print("  3. Calculate Prepayment Interest Savings")
        print("  4. Exit")
        print("=" * 55)
        choice = input("Select an option (1-4): ").strip()

        if choice == "1":
            try:
                amt = float(input("Enter loan amount in Rupees (e.g. 5000000): "))
                rate = float(input("Enter annual interest rate % (e.g. 8.5): "))
                tenure = float(input("Enter loan tenure in years (e.g. 20): "))
                run_emi(amt, rate, tenure)
            except ValueError:
                print("[ERROR] Please enter valid numbers.")
        elif choice == "2":
            try:
                income = float(input("Enter gross monthly income in Rupees (e.g. 150000): "))
                existing = float(input("Enter existing monthly EMIs in Rupees (e.g. 15000): "))
                amt = float(input("Enter requested loan amount in Rupees (e.g. 6000000): "))
                rate = float(input("Enter annual interest rate % (e.g. 8.5): "))
                tenure = float(input("Enter tenure in years (e.g. 20): "))
                run_eligibility(income, amt, rate, tenure, existing)
            except ValueError:
                print("[ERROR] Please enter valid numbers.")
        elif choice == "3":
            try:
                amt = float(input("Enter original loan amount in Rupees (e.g. 5000000): "))
                rate = float(input("Enter annual interest rate % (e.g. 8.5): "))
                tenure = float(input("Enter original tenure in years (e.g. 20): "))
                elapsed = int(input("Enter number of EMIs already paid (e.g. 24): "))
                prepay = float(input("Enter one-time prepayment amount in Rupees (e.g. 500000): "))
                run_prepayment(amt, rate, tenure, elapsed, prepay)
            except ValueError:
                print("[ERROR] Please enter valid numbers.")
        elif choice == "4":
            print("Exiting calculator.")
            break
        else:
            print("Invalid choice, please select 1-4.")


def main():
    parser = argparse.ArgumentParser(description="Mortgage Customer Financial Calculators")
    subparsers = parser.add_subparsers(dest="command")

    # EMI parser
    emi_parser = subparsers.add_parser("emi", help="Calculate EMI and interest breakdown")
    emi_parser.add_argument("--amount", type=float, required=True, help="Loan principal amount in Rupees")
    emi_parser.add_argument("--rate", type=float, required=True, help="Annual interest rate percent (e.g. 8.5)")
    emi_parser.add_argument("--tenure", type=float, required=True, help="Tenure in years (e.g. 20)")

    # Eligibility parser
    elig_parser = subparsers.add_parser("eligibility", help="Check FOIR borrower eligibility")
    elig_parser.add_argument("--income", type=float, required=True, help="Gross monthly income in Rupees")
    elig_parser.add_argument("--requested-loan", type=float, required=True, help="Requested principal amount in Rupees")
    elig_parser.add_argument("--rate", type=float, default=8.5, help="Annual interest rate percent (default: 8.5)")
    elig_parser.add_argument("--tenure", type=float, default=20.0, help="Loan tenure in years (default: 20)")
    elig_parser.add_argument("--existing-emi", type=float, default=0.0, help="Existing monthly EMI commitments (default: 0)")

    # Prepayment parser
    prep_parser = subparsers.add_parser("prepayment", help="Calculate prepayment savings and tenure reduction")
    prep_parser.add_argument("--amount", type=float, required=True, help="Original loan principal in Rupees")
    prep_parser.add_argument("--rate", type=float, required=True, help="Annual interest rate percent (e.g. 8.5)")
    prep_parser.add_argument("--tenure", type=float, required=True, help="Original loan tenure in years (e.g. 20)")
    prep_parser.add_argument("--months-paid", type=int, required=True, help="Number of EMIs already paid so far")
    prep_parser.add_argument("--prepay", type=float, required=True, help="One-time prepayment amount in Rupees")

    args = parser.parse_args()

    if args.command == "emi":
        run_emi(args.amount, args.rate, args.tenure)
    elif args.command == "eligibility":
        run_eligibility(args.income, args.requested_loan, args.rate, args.tenure, args.existing_emi)
    elif args.command == "prepayment":
        run_prepayment(args.amount, args.rate, args.tenure, args.months_paid, args.prepay)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
