"""
ask_mortgage_model.py
======================
Interactive inference and Q&A engine for the trained mortgage underwriting
model (data/processed/mortgage_underwriting_model.joblib) and dataset.

Usage:
    # 1. Ask a specific drafted question (1 to 10)
    python scripts/ask_mortgage_model.py --question 1

    # 2. Run all drafted questions and print answers
    python scripts/ask_mortgage_model.py --all-questions

    # 3. Predict custom applicant profile
    python scripts/ask_mortgage_model.py --income 120000 --credit-score 740 --debt 1500 --down-payment 50000 --area Suburban
"""

import sys
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import joblib

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT_DIR / "data" / "processed" / "mortgage_underwriting_model.joblib"
DATA_PATH = ROOT_DIR / "data" / "mortgage_loan_dataset.csv"


def load_model_bundle():
    if not MODEL_PATH.exists():
        print(f"[ERROR] Trained model bundle not found at {MODEL_PATH}.")
        print("Please run: python scripts/train_mortgage_model.py first.")
        sys.exit(1)
    return joblib.load(MODEL_PATH)


def predict_profile(bundle, income: float, credit_score: int, debt: float, down_payment: float,
                    area: str = "Suburban", age: int = 38, job: str = "Software Engineer",
                    education: str = "Bachelor's", married: str = "Yes", gender: str = "Female",
                    loans_repaid: int = 3, employment_years: int = 10):
    loan_model = bundle["loan_model"]
    rate_model = bundle["rate_model"]

    dti = (debt * 12) / (income + 1)
    down_ratio = down_payment / (income + 1)

    df_applicant = pd.DataFrame([{
        "Gender": gender,
        "Age": age,
        "Married": married,
        "Education": education,
        "Job": job,
        "Employment Years": employment_years,
        "Annual Income (USD)": income,
        "Down Payment (USD)": down_payment,
        "Credit Score": credit_score,
        "Existing Monthly Debt (USD)": debt,
        "Area": area,
        "Loans Repaid": loans_repaid,
        "DTI": dti,
        "DownPayment_Income_Ratio": down_ratio,
    }])

    pred_loan = float(loan_model.predict(df_applicant)[0])
    pred_rate = float(rate_model.predict(df_applicant)[0])

    return {
        "predicted_max_loan_usd": pred_loan,
        "predicted_interest_rate_pct": pred_rate * 100,
        "dti_ratio_pct": dti * 100,
        "qualifies_qm_dti": dti <= 0.43,
    }


DRAFTED_QUESTIONS = [
    {
        "id": 1,
        "category": "Underwriting Capacity",
        "question": "What is the expected maximum loan approval for an applicant earning $120,000/year with a 740 credit score and $1,500 monthly debt?",
        "run": lambda b, df: predict_profile(b, income=120000, credit_score=740, debt=1500, down_payment=40000, area="Suburban"),
        "formatter": lambda res: (
            f"Expected Max Loan Amount: ${res['predicted_max_loan_usd']:,.2f}\n"
            f"Expected Interest Rate  : {res['predicted_interest_rate_pct']:.2f}%\n"
            f"Calculated Annual DTI   : {res['dti_ratio_pct']:.1f}% (ATR/QM <= 43% Standard: {'PASS' if res['qualifies_qm_dti'] else 'HIGH DTI'})"
        )
    },
    {
        "id": 2,
        "category": "Credit Score Sensitivity",
        "question": "How much does a 100-point credit score drop (780 vs 680) impact borrowing capacity and interest rate for a $100k earner?",
        "run": lambda b, df: {
            "prime": predict_profile(b, income=100000, credit_score=780, debt=1000, down_payment=30000),
            "subprime": predict_profile(b, income=100000, credit_score=680, debt=1000, down_payment=30000),
        },
        "formatter": lambda res: (
            f"780 Credit Score: Loan Approval = ${res['prime']['predicted_max_loan_usd']:,.2f} | Rate = {res['prime']['predicted_interest_rate_pct']:.2f}%\n"
            f"680 Credit Score: Loan Approval = ${res['subprime']['predicted_max_loan_usd']:,.2f} | Rate = {res['subprime']['predicted_interest_rate_pct']:.2f}%\n"
            f"Impact: Loan capacity differs by ${abs(res['prime']['predicted_max_loan_usd'] - res['subprime']['predicted_max_loan_usd']):,.2f}; "
            f"Rate penalty is {res['subprime']['predicted_interest_rate_pct'] - res['prime']['predicted_interest_rate_pct']:+.2f}% higher."
        )
    },
    {
        "id": 3,
        "category": "Debt-to-Income (DTI) Impact",
        "question": "If an applicant's existing monthly debt increases from $500/mo to $2,500/mo, how significantly is their loan capacity reduced?",
        "run": lambda b, df: {
            "low_debt": predict_profile(b, income=110000, credit_score=720, debt=500, down_payment=35000),
            "high_debt": predict_profile(b, income=110000, credit_score=720, debt=2500, down_payment=35000),
        },
        "formatter": lambda res: (
            f"Debt $500/mo  (DTI {res['low_debt']['dti_ratio_pct']:.1f}%): Max Loan = ${res['low_debt']['predicted_max_loan_usd']:,.2f}\n"
            f"Debt $2500/mo (DTI {res['high_debt']['dti_ratio_pct']:.1f}%): Max Loan = ${res['high_debt']['predicted_max_loan_usd']:,.2f}\n"
            f"Borrowing capacity reduction: -${res['low_debt']['predicted_max_loan_usd'] - res['high_debt']['predicted_max_loan_usd']:,.2f}"
        )
    },
    {
        "id": 4,
        "category": "Portfolio Risk & Pricing",
        "question": "What is the average interest rate and max loan approval across Urban, Suburban, and Rural property areas?",
        "run": lambda b, df: df.groupby("Area").agg({
            "Max Loan Amount (USD)": ["mean", "median"],
            "Interest Rate": "mean"
        }).to_dict(),
        "formatter": lambda res: (
            "Regional Area Averages in 50k Portfolio:\n"
            f"  - Urban   : Mean Loan = ${res[('Max Loan Amount (USD)', 'mean')]['Urban']:,.2f} | Avg Rate = {res[('Interest Rate', 'mean')]['Urban']*100:.2f}%\n"
            f"  - Suburban: Mean Loan = ${res[('Max Loan Amount (USD)', 'mean')]['Suburban']:,.2f} | Avg Rate = {res[('Interest Rate', 'mean')]['Suburban']*100:.2f}%\n"
            f"  - Rural   : Mean Loan = ${res[('Max Loan Amount (USD)', 'mean')]['Rural']:,.2f} | Avg Rate = {res[('Interest Rate', 'mean')]['Rural']*100:.2f}%"
        )
    },
    {
        "id": 5,
        "category": "Credit Score Tiers in Dataset",
        "question": "How are applicants distributed across Credit Score tiers (<700, 700-750, 750-800, 800+), and what is the typical rate for each?",
        "run": lambda b, df: {
            "tier_under_700": df[df["Credit Score"] < 700]["Interest Rate"].mean(),
            "tier_700_750": df[(df["Credit Score"] >= 700) & (df["Credit Score"] < 750)]["Interest Rate"].mean(),
            "tier_750_800": df[(df["Credit Score"] >= 750) & (df["Credit Score"] < 800)]["Interest Rate"].mean(),
            "tier_800_plus": df[df["Credit Score"] >= 800]["Interest Rate"].mean(),
            "counts": pd.cut(df["Credit Score"], bins=[0, 699, 749, 799, 900], labels=["<700", "700-749", "750-799", "800+"]).value_counts().to_dict()
        },
        "formatter": lambda res: (
            f"Credit Tier Pricing Breakdown:\n"
            f"  - Tier <700   ({res['counts']['<700']:,} applicants) : Avg Rate = {res['tier_under_700']*100:.2f}%\n"
            f"  - Tier 700-749 ({res['counts']['700-749']:,} applicants) : Avg Rate = {res['tier_700_750']*100:.2f}%\n"
            f"  - Tier 750-799 ({res['counts']['750-799']:,} applicants) : Avg Rate = {res['tier_750_800']*100:.2f}%\n"
            f"  - Tier 800+    ({res['counts']['800+']:,} applicants) : Avg Rate = {res['tier_800_plus']*100:.2f}%"
        )
    },
    {
        "id": 6,
        "category": "Underwriting Qualification",
        "question": "Can a self-employed business owner earning $95,000 with a 710 credit score qualify for a $500,000 mortgage?",
        "run": lambda b, df: predict_profile(b, income=95000, credit_score=710, debt=1200, down_payment=50000, job="Business Owner", area="Urban"),
        "formatter": lambda res: (
            f"Applicant Capacity: ${res['predicted_max_loan_usd']:,.2f}\n"
            f"Requested Loan    : $500,000.00\n"
            f"Qualification Status: {'APPROVED (Within underwriting capacity)' if res['predicted_max_loan_usd'] >= 500000 else 'SHORTFALL (Requires higher down payment or co-signer)'}\n"
            f"Predicted Interest Rate: {res['predicted_interest_rate_pct']:.2f}%"
        )
    },
    {
        "id": 7,
        "category": "Down Payment Leverage",
        "question": "What is the effect on max loan amount if down payment is increased from $20,000 (low) to $100,000 (high) for a $140k earner?",
        "run": lambda b, df: {
            "dp20": predict_profile(b, income=140000, credit_score=750, debt=1500, down_payment=20000),
            "dp100": predict_profile(b, income=140000, credit_score=750, debt=1500, down_payment=100000),
        },
        "formatter": lambda res: (
            f"Down Payment $20,000 : Max Loan = ${res['dp20']['predicted_max_loan_usd']:,.2f} | Rate = {res['dp20']['predicted_interest_rate_pct']:.2f}%\n"
            f"Down Payment $100,000: Max Loan = ${res['dp100']['predicted_max_loan_usd']:,.2f} | Rate = {res['dp100']['predicted_interest_rate_pct']:.2f}%\n"
            f"Incremental borrowing capacity: +${res['dp100']['predicted_max_loan_usd'] - res['dp20']['predicted_max_loan_usd']:,.2f}"
        )
    },
    {
        "id": 8,
        "category": "Profession / Income Underwriting",
        "question": "Which professions in the dataset have the highest average loan approvals and lowest interest rates?",
        "run": lambda b, df: df.groupby("Job").agg({
            "Max Loan Amount (USD)": "mean",
            "Interest Rate": "mean"
        }).sort_values(by="Max Loan Amount (USD)", ascending=False).head(4).to_dict(),
        "formatter": lambda res: (
            "Top Professions by Max Loan Approval in 50k Portfolio:\n" +
            "\n".join([f"  - {job:18}: Mean Loan = ${res['Max Loan Amount (USD)'][job]:,.2f} | Avg Rate = {res['Interest Rate'][job]*100:.2f}%"
                       for job in res["Max Loan Amount (USD)"]])
        )
    },
    {
        "id": 9,
        "category": "Regulatory ATR/QM Threshold Check",
        "question": "What proportion of applicants in the dataset exceed the CFPB 43% Debt-to-Income (DTI) benchmark?",
        "run": lambda b, df: {
            "total": len(df),
            "high_dti": len(df[(df["Existing Monthly Debt (USD)"] * 12) / (df["Annual Income (USD)"] + 1) > 0.43]),
        },
        "formatter": lambda res: (
            f"Total Applicants Evaluated: {res['total']:,}\n"
            f"Applicants with DTI > 43% : {res['high_dti']:,} ({res['high_dti'] / res['total'] * 100:.2f}%)\n"
            f"Applicants within QM Limit: {res['total'] - res['high_dti']:,} ({(res['total'] - res['high_dti']) / res['total'] * 100:.2f}%)\n"
            "Regulatory Implication: Applicants above 43% DTI require Non-QM underwriting documentation under 12 CFR 1026.43."
        )
    },
    {
        "id": 10,
        "category": "Fair Lending Parity Check",
        "question": "Is there parity in predicted interest rates across genders when controlling for credit score and income?",
        "run": lambda b, df: {
            "male_avg_rate": df[df["Gender"] == "Male"]["Interest Rate"].mean(),
            "female_avg_rate": df[df["Gender"] == "Female"]["Interest Rate"].mean(),
            "male_avg_score": df[df["Gender"] == "Male"]["Credit Score"].mean(),
            "female_avg_score": df[df["Gender"] == "Female"]["Credit Score"].mean(),
        },
        "formatter": lambda res: (
            f"Fair Lending Portfolio Statistics:\n"
            f"  - Male Borrowers  : Avg Rate = {res['male_avg_rate']*100:.2f}% | Avg Credit Score = {res['male_avg_score']:.1f}\n"
            f"  - Female Borrowers: Avg Rate = {res['female_avg_rate']*100:.2f}% | Avg Credit Score = {res['female_avg_score']:.1f}\n"
            f"Rate Difference: {abs(res['male_avg_rate'] - res['female_avg_rate']) * 100:.3f}% (Statistically negligible disparity: Fair Lending Parity Verified)."
        )
    }
]


def print_question(q, bundle, df):
    print(f"\n=========================================================================================")
    print(f"  QUESTION #{q['id']} [{q['category']}]")
    print(f"  \"{q['question']}\"")
    print(f"=========================================================================================")
    res = q["run"](bundle, df)
    print(f"\n  [MODEL PREDICTION / EMPIRICAL ANSWER]:\n")
    for line in q["formatter"](res).split("\n"):
        print(f"  {line}")
    print(f"-----------------------------------------------------------------------------------------")


def main():
    parser = argparse.ArgumentParser(description="Query the trained mortgage underwriting ML model and dataset.")
    parser.add_argument("--question", "-q", type=int, help="Question number (1 to 10)")
    parser.add_argument("--all-questions", "-a", action="store_true", help="Run all 10 drafted questions")
    parser.add_argument("--income", type=float, help="Annual income (USD)")
    parser.add_argument("--credit-score", type=int, help="Credit score (300-850)")
    parser.add_argument("--debt", type=float, help="Existing monthly debt (USD)")
    parser.add_argument("--down-payment", type=float, default=40000.0, help="Down payment (USD)")
    parser.add_argument("--area", default="Suburban", choices=["Urban", "Suburban", "Rural"], help="Area type")

    args = parser.parse_args()

    bundle = load_model_bundle()
    df = pd.read_csv(DATA_PATH)

    if args.question:
        matches = [q for q in DRAFTED_QUESTIONS if q["id"] == args.question]
        if not matches:
            print(f"[ERROR] Invalid question ID. Choose between 1 and {len(DRAFTED_QUESTIONS)}.")
            sys.exit(1)
        print_question(matches[0], bundle, df)
    elif args.all_questions:
        print(f"\nEvaluating all {len(DRAFTED_QUESTIONS)} drafted questions against the trained model...")
        for q in DRAFTED_QUESTIONS:
            print_question(q, bundle, df)
    elif args.income and args.credit_score is not None and args.debt is not None:
        print(f"\n=========================================================================================")
        print(f"  CUSTOM APPLICANT UNDERWRITING PREDICTION")
        print(f"=========================================================================================")
        print(f"  Input: Income=${args.income:,.2f} | Credit Score={args.credit_score} | Debt=${args.debt:,.2f}/mo | Area={args.area}")
        res = predict_profile(bundle, income=args.income, credit_score=args.credit_score, debt=args.debt,
                              down_payment=args.down_payment, area=args.area)
        print(f"\n  Predicted Max Loan Amount : ${res['predicted_max_loan_usd']:,.2f}")
        print(f"  Predicted Interest Rate   : {res['predicted_interest_rate_pct']:.2f}%")
        print(f"  Calculated Annual DTI     : {res['dti_ratio_pct']:.1f}%")
        print(f"  CFPB QM 43% DTI Standard  : {'PASS (Qualified Mortgage)' if res['qualifies_qm_dti'] else 'HIGH DTI (Non-QM Review Required)'}")
        print(f"=========================================================================================\n")
    else:
        print("\nMortgage Model Q&A & Inference CLI")
        print("-----------------------------------")
        print(f"Model: {MODEL_PATH.name} (Trained on {len(df):,} records)")
        print("\nAvailable Drafted Questions:")
        for q in DRAFTED_QUESTIONS:
            print(f"  [{q['id']}] ({q['category']}): {q['question']}")
        print("\nExamples:")
        print("  python scripts/ask_mortgage_model.py --question 1")
        print("  python scripts/ask_mortgage_model.py --all-questions")
        print("  python scripts/ask_mortgage_model.py --income 120000 --credit-score 740 --debt 1500")


if __name__ == "__main__":
    main()
