"""
orchestrate_agents.py
=====================
CLI Multi-Agent Orchestrator runner for mortgage_assistant / TCS Mortgage Loan Compliance System.
Demonstrates Supervisor Pattern multi-agent coordination with full telemetry.

Usage:
    # 1. Audit a loan agreement via multi-agent orchestration:
    python scripts/orchestrate_agents.py audit --file data/real_docs/sample_loan_agreements/non_compliant_home_loan_agreement.txt

    # 2. Audit a PDF contract:
    python scripts/orchestrate_agents.py audit --file data/raw/sample_loans/bnpp_term_loan_agreement_india.pdf

    # 3. Assess a borrower application:
    python scripts/orchestrate_agents.py borrower --income 150000 --credit-score 740 --requested-loan 6000000 --rate 8.5 --tenure 20

    # 4. Inspect registered agents & orchestration health:
    python scripts/orchestrate_agents.py agents
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agent.orchestrator import orchestrator


def print_banner(title: str):
    print("\n" + "=" * 78)
    print(f"  {title.upper()}")
    print("=" * 78)


def run_audit(file_path: str, jurisdiction: str = "IN"):
    print_banner(f"Agent Orchestration Audit: {Path(file_path).name}")
    print(f"Target Document : {file_path}")
    print(f"Jurisdiction    : {jurisdiction}")
    print("Orchestrator    : Supervisor ReAct Pattern (6 Specialized Agents)\n")

    t0 = time.time()
    res = orchestrator.orchestrate_loan_audit(file_path, jurisdiction)
    elapsed = (time.time() - t0) * 1000

    print("-" * 78)
    print("  STEP-BY-STEP AGENT EXECUTION TRACE")
    print("-" * 78)

    for trace in res.step_traces:
        status_tag = f"[{trace.status}]"
        print(f"  Step {trace.step_number} | {trace.agent_name:<26} {status_tag:<12} ({trace.latency_ms:6.2f} ms)")
        print(f"         Action: {trace.action}")
        print(f"         Result: {trace.output_summary}\n")

    print("=" * 78)
    print(f"  ORCHESTRATION SUMMARY: {res.overall_status}")
    print("=" * 78)
    print(f"  Workflow ID       : {res.workflow_id}")
    print(f"  Total Latency     : {res.total_latency_ms:.2f} ms (CLI overhead: {elapsed:.2f} ms)")
    print(f"  Escalated to HITL : {'YES (Review Required)' if res.escalated_to_hitl else 'NO (Automated Pass)'}")
    if res.hitl_reasons:
        print("  Escalation Reasons:")
        for r in res.hitl_reasons:
            print(f"    * {r}")

    print("\n  Final Findings:")
    print(f"    * Document       : {res.final_output.get('document_name')}")
    print(f"    * Overall Status : {res.final_output.get('overall_status')}")
    print(f"    * Total Checks   : {res.final_output.get('total_checks')}")
    print(f"    * Violations     : {res.final_output.get('violations_count')}")
    print("=" * 78 + "\n")


def run_borrower(income: float, credit_score: int, requested_loan: float, rate: float, tenure: float, existing_debt: float):
    print_banner("Agent Orchestration: Borrower Risk & Eligibility Assessment")
    print(f"Gross Monthly Income : Rs. {income:,.2f}")
    print(f"Credit Score         : {credit_score}")
    print(f"Requested Principal  : Rs. {requested_loan:,.2f} ({rate:.2f}% for {tenure:.0f} yrs)\n")

    res = orchestrator.orchestrate_borrower_assessment(
        income=income,
        credit_score=credit_score,
        requested_loan=requested_loan,
        rate=rate,
        tenure=tenure,
        existing_debt=existing_debt,
    )

    print("-" * 78)
    print("  STEP-BY-STEP AGENT EXECUTION TRACE")
    print("-" * 78)

    for trace in res.step_traces:
        status_tag = f"[{trace.status}]"
        print(f"  Step {trace.step_number} | {trace.agent_name:<26} {status_tag:<12} ({trace.latency_ms:6.2f} ms)")
        print(f"         Action: {trace.action}")
        print(f"         Result: {trace.output_summary}\n")

    print("=" * 78)
    print(f"  ORCHESTRATION SUMMARY: {res.overall_status}")
    print("=" * 78)
    print(f"  Monthly Installment : Rs. {res.final_output.get('monthly_emi'):,.2f} / month")
    print(f"  FOIR Ratio          : {res.final_output.get('foir_percent')}%")
    print(f"  Eligible            : {'YES' if res.final_output.get('is_eligible') else 'NO'}")
    print(f"  Approved Capacity   : Rs. {res.final_output.get('approved_capacity_estimate'):,.2f}")
    print(f"  Escalated to HITL   : {'YES' if res.escalated_to_hitl else 'NO'}")
    print("=" * 78 + "\n")


def list_agents():
    print_banner("Multi-Agent Registry & Capability Roster")
    agents = orchestrator.get_registered_agents()
    for name, info in agents.items():
        print(f"  Agent: {name}")
        print(f"    Role         : {info['role']}")
        print(f"    Capabilities : {', '.join(info['capabilities'])}")
        print(f"    Invocations  : {info['invocations']}")
        print("  " + "-" * 74)
    print()


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Orchestrator CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Audit loan agreement using multi-agent workflow")
    audit_parser.add_argument("--file", type=str, required=True, help="Path to loan document (PDF or TXT)")
    audit_parser.add_argument("--jurisdiction", type=str, default="IN", help="Jurisdiction ('IN' or 'US')")

    # Borrower command
    borrower_parser = subparsers.add_parser("borrower", help="Assess borrower application via multi-agent workflow")
    borrower_parser.add_argument("--income", type=float, required=True, help="Gross monthly income in rupees")
    borrower_parser.add_argument("--credit-score", type=int, required=True, help="Credit score (300-850)")
    borrower_parser.add_argument("--requested-loan", type=float, required=True, help="Requested loan principal in rupees")
    borrower_parser.add_argument("--rate", type=float, default=8.5, help="Annual interest rate percent (default: 8.5)")
    borrower_parser.add_argument("--tenure", type=float, default=20.0, help="Loan tenure in years (default: 20)")
    borrower_parser.add_argument("--existing-debt", type=float, default=0.0, help="Existing monthly debt commitments")

    # Agents command
    subparsers.add_parser("agents", help="List registered agents and capabilities")

    args = parser.parse_args()

    if args.command == "audit":
        run_audit(args.file, args.jurisdiction)
    elif args.command == "borrower":
        run_borrower(args.income, args.credit_score, args.requested_loan, args.rate, args.tenure, args.existing_debt)
    elif args.command == "agents":
        list_agents()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
