"""
train_mortgage_model.py
========================
Trains supervised ML regression models and builds an underwriting intelligence
pipeline on the 50,000-record mortgage dataset (data/mortgage_loan_dataset.csv).

Targets:
1. Max Loan Amount (USD)  -> Underwriting borrowing capacity prediction
2. Interest Rate          -> Risk-based mortgage rate tier pricing

Outputs:
- Trained pipeline bundle: data/processed/mortgage_underwriting_model.joblib
- Model metrics and feature importances report
- Benchmark predictions for sample borrower profiles
"""

import sys
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "mortgage_loan_dataset.csv"
MODEL_DIR = ROOT_DIR / "data" / "processed"
MODEL_FILE = MODEL_DIR / "mortgage_underwriting_model.joblib"
METRICS_FILE = MODEL_DIR / "mortgage_model_metrics.json"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


def load_and_preprocess_data(csv_path: Path):
    print(f"[1/4] Loading dataset from: {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"      Loaded {len(df):,} records and {len(df.columns)} columns.")

    # Feature Engineering
    # Debt-to-Income (Annual Debt / Annual Income)
    df["DTI"] = (df["Existing Monthly Debt (USD)"] * 12) / (df["Annual Income (USD)"] + 1)
    # Down Payment to Income Ratio
    df["DownPayment_Income_Ratio"] = df["Down Payment (USD)"] / (df["Annual Income (USD)"] + 1)

    return df


def build_pipeline():
    numeric_features = [
        "Age",
        "Employment Years",
        "Annual Income (USD)",
        "Down Payment (USD)",
        "Credit Score",
        "Existing Monthly Debt (USD)",
        "Loans Repaid",
        "DTI",
        "DownPayment_Income_Ratio",
    ]
    categorical_features = ["Gender", "Married", "Education", "Job", "Area"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
        ]
    )

    regressor = HistGradientBoostingRegressor(
        max_iter=150,
        learning_rate=0.08,
        max_leaf_nodes=31,
        random_state=42,
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", regressor),
        ]
    )

    return pipeline, numeric_features, categorical_features


def train():
    start_time = time.time()
    df = load_and_preprocess_data(DATA_PATH)

    # Features and Targets
    feature_cols = [
        "Gender",
        "Age",
        "Married",
        "Education",
        "Job",
        "Employment Years",
        "Annual Income (USD)",
        "Down Payment (USD)",
        "Credit Score",
        "Existing Monthly Debt (USD)",
        "Area",
        "Loans Repaid",
        "DTI",
        "DownPayment_Income_Ratio",
    ]

    X = df[feature_cols]
    y_loan = df["Max Loan Amount (USD)"]
    y_rate = df["Interest Rate"]

    print("[2/4] Splitting dataset (80% train, 20% test)...")
    X_train, X_test, y_loan_train, y_loan_test, y_rate_train, y_rate_test = train_test_split(
        X, y_loan, y_rate, test_size=0.20, random_state=42
    )

    print(f"      Train samples: {len(X_train):,}  |  Test samples: {len(X_test):,}")

    # 1. Train Max Loan Amount Model
    print("[3/4] Training Model 1: Max Loan Amount (USD)...")
    loan_pipeline, num_cols, cat_cols = build_pipeline()
    loan_pipeline.fit(X_train, y_loan_train)

    y_loan_pred = loan_pipeline.predict(X_test)
    loan_r2 = r2_score(y_loan_test, y_loan_pred)
    loan_mae = mean_absolute_error(y_loan_test, y_loan_pred)
    loan_rmse = np.sqrt(mean_squared_error(y_loan_test, y_loan_pred))

    print(f"      -> Max Loan Model R^2 Score : {loan_r2:.4f}")
    print(f"      -> Max Loan Model MAE       : ${loan_mae:,.2f}")
    print(f"      -> Max Loan Model RMSE      : ${loan_rmse:,.2f}")

    # 2. Train Interest Rate Model
    print("      Training Model 2: Interest Rate Tier...")
    rate_pipeline, _, _ = build_pipeline()
    rate_pipeline.fit(X_train, y_rate_train)

    y_rate_pred = rate_pipeline.predict(X_test)
    rate_r2 = r2_score(y_rate_test, y_rate_pred)
    rate_mae = mean_absolute_error(y_rate_test, y_rate_pred)
    rate_rmse = np.sqrt(mean_squared_error(y_rate_test, y_rate_pred))

    print(f"      -> Interest Rate Model R^2  : {rate_r2:.4f}")
    print(f"      -> Interest Rate Model MAE  : {rate_mae * 100:.3f}% ({rate_mae:.5f})")
    print(f"      -> Interest Rate Model RMSE : {rate_rmse * 100:.3f}%")

    # 3. Save Model Artifacts
    print(f"[4/4] Saving model bundle to: {MODEL_FILE}...")
    model_bundle = {
        "loan_model": loan_pipeline,
        "rate_model": rate_pipeline,
        "feature_cols": feature_cols,
        "num_cols": num_cols,
        "cat_cols": cat_cols,
        "dataset_records": len(df),
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metrics": {
            "max_loan": {
                "r2": round(loan_r2, 4),
                "mae_usd": round(loan_mae, 2),
                "rmse_usd": round(loan_rmse, 2),
            },
            "interest_rate": {
                "r2": round(rate_r2, 4),
                "mae_percent": round(rate_mae * 100, 3),
                "rmse_percent": round(rate_rmse * 100, 3),
            },
        },
        "summary_stats": {
            "mean_income": float(df["Annual Income (USD)"].mean()),
            "median_income": float(df["Annual Income (USD)"].median()),
            "mean_loan_amount": float(df["Max Loan Amount (USD)"].mean()),
            "median_loan_amount": float(df["Max Loan Amount (USD)"].median()),
            "mean_credit_score": float(df["Credit Score"].mean()),
            "median_credit_score": float(df["Credit Score"].median()),
            "mean_interest_rate": float(df["Interest Rate"].mean()),
            "mean_dti": float(df["DTI"].mean()),
        },
    }

    joblib.dump(model_bundle, MODEL_FILE)

    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "trained_at": model_bundle["trained_at"],
                "records": len(df),
                "metrics": model_bundle["metrics"],
                "summary_stats": model_bundle["summary_stats"],
            },
            f,
            indent=2,
        )

    elapsed = time.time() - start_time
    print(f"\n[SUCCESS] Training completed in {elapsed:.2f} seconds!")
    print(f"Model saved to: {MODEL_FILE}")
    print(f"Metrics saved to: {METRICS_FILE}")

    # Run quick sample inference demonstration
    print("\n--- SAMPLE INFERENCE VERIFICATION ---")
    sample_borrower = pd.DataFrame(
        [
            {
                "Gender": "Male",
                "Age": 36,
                "Married": "Yes",
                "Education": "Bachelor's",
                "Job": "Software Engineer",
                "Employment Years": 10,
                "Annual Income (USD)": 135000.0,
                "Down Payment (USD)": 60000.0,
                "Credit Score": 760,
                "Existing Monthly Debt (USD)": 1200.0,
                "Area": "Suburban",
                "Loans Repaid": 3,
                "DTI": (1200.0 * 12) / (135000.0 + 1),
                "DownPayment_Income_Ratio": 60000.0 / (135000.0 + 1),
            }
        ]
    )

    pred_loan = loan_pipeline.predict(sample_borrower)[0]
    pred_rate = rate_pipeline.predict(sample_borrower)[0]

    print(f"Profile: Software Engineer, Income: $135,000, Credit Score: 760, Monthly Debt: $1,200")
    print(f"  -> Predicted Max Loan Approval : ${pred_loan:,.2f}")
    print(f"  -> Predicted Interest Rate     : {pred_rate * 100:.2f}%")


if __name__ == "__main__":
    train()
