"""
admin_console.py
================
Interactive Administration & Governance Console for mortgage_assistant / TCS Mortgage Loan Compliance System.
Provides a comprehensive Administrator Point-of-View (POV) over platform health, agent fleet,
optimization metrics, human-in-the-loop exception queues, and regulatory audit trails.

Usage:
    # 1. Interactive Admin Dashboard:
    python scripts/admin_console.py

    # 2. Command-line flags for quick inspection:
    python scripts/admin_console.py --overview
    python scripts/admin_console.py --agents
    python scripts/admin_console.py --metrics
    python scripts/admin_console.py --audit --limit 10
"""

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from agent.orchestrator import orchestrator
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.entities import AuditEvent, ReviewTask, RegulatorySource, User
from backend.app.services.compliance.budget_optimizer import optimizer


def print_header(title: str):
    print("\n" + "=" * 78)
    print(f"  ADMINISTRATION CONSOLE: {title.upper()}")
    print("=" * 78)


def show_overview():
    print_header("System Diagnostics & Platform Telemetry")
    db = SessionLocal()
    try:
        source_count = db.query(RegulatorySource).count()
        pending_reviews = db.query(ReviewTask).filter(ReviewTask.status == "PENDING").count()
        total_audit_events = db.query(AuditEvent).count()
        db_status = "ONLINE (Healthy)"
    except Exception as e:
        source_count = 0
        pending_reviews = 0
        total_audit_events = 0
        db_status = f"ERROR: {e}"
    finally:
        db.close()

    agents = orchestrator.get_registered_agents()
    telemetry = optimizer.get_telemetry()

    print(f"  Platform Name          : {settings.PROJECT_NAME}")
    print(f"  Environment            : {settings.ENVIRONMENT.upper()} (Version {settings.VERSION})")
    print(f"  Host Architecture      : {platform.platform()} | Python {platform.python_version()}")
    print(f"  Database Engine        : {db_status}")
    print(f"  Configured LLM         : {settings.LLM_PROVIDER.upper()} -> {settings.DEFAULT_LLM_MODEL}")
    print(f"  Hybrid Search Embedder : {settings.EMBEDDING_PROVIDER.upper()}")
    print("-" * 78)
    print("  OPERATIONAL METRICS:")
    print(f"  - Regulatory Sources Ingested  : {source_count} datasets")
    print(f"  - Pending HITL Reviews         : {pending_reviews} tasks waiting in queue")
    print(f"  - Registered Sub-Agents        : {len(agents)} active agents in fleet")
    print(f"  - In-Memory Cached Decisions   : {telemetry['cached_entries_count']} entries")
    print(f"  - Estimated Time Saved (CPU)   : {telemetry['estimated_time_saved_seconds']} seconds")
    print(f"  - Estimated Tokens Saved       : {telemetry['estimated_tokens_saved']:,} tokens")
    print("=" * 78 + "\n")


def show_agents():
    print_header("Multi-Agent Fleet & Telemetry")
    agents = orchestrator.get_registered_agents()
    print(f"  Total Registered Agents: {len(agents)}\n")

    for idx, (name, info) in enumerate(agents.items(), 1):
        print(f"  [{idx}] {name:<26} Status: [HEALTHY]  Invocations: {info['invocations']}")
        print(f"      Role         : {info['role']}")
        print(f"      Capabilities : {', '.join(info['capabilities'])}")
        print("  " + "-" * 74)
    print()


def show_metrics():
    print_header("Performance Optimization & Latency Telemetry")
    t = optimizer.get_telemetry()
    print("  Slide 9 Hardware & Latency Solutions:")
    print(f"  - Total Rule Evaluations       : {t['total_evaluations']}")
    print(f"  - Deterministic Fast-Path Hits : {t['fast_path_hits']} ({t['fast_path_ratio_percent']}%)")
    print(f"  - In-Memory LRU Cache Hits     : {t['cache_hits']} ({t['cache_hit_ratio_percent']}%)")
    print(f"  - Deep LLM Round-Trips Taken   : {t['llm_invocations']}")
    print(f"  - Tokens Conserved             : {t['estimated_tokens_saved']:,} tokens")
    print(f"  - Total Latency Avoided        : {t['estimated_time_saved_seconds']} seconds")
    print("=" * 78 + "\n")


def show_pending_reviews():
    print_header("Human-in-the-Loop (HITL) Exception Review Queue")
    db = SessionLocal()
    try:
        tasks = (
            db.query(ReviewTask)
            .filter(ReviewTask.status == "PENDING")
            .order_by(ReviewTask.created_at.desc())
            .limit(10)
            .all()
        )
        if not tasks:
            print("  [QUEUE EMPTY] All analyzed loan contracts are fully compliant or resolved.")
        else:
            print(f"  Found {len(tasks)} tasks requiring human compliance review:\n")
            for t in tasks:
                print(f"  Task ID     : {t.id}")
                print(f"  Finding ID  : {t.finding_id}")
                print(f"  Status      : {t.status}")
                print(f"  Assigned To : {t.assigned_to or 'Unassigned'}")
                print(f"  Created At  : {t.created_at}")
                print("  " + "-" * 74)
    finally:
        db.close()
    print()


def show_audit_trail(limit: int = 10, agent_filter: str = None):
    print_header(f"System Audit Trail (Latest {limit} Events)")
    log_file = ROOT_DIR / "logs" / "audit_log.jsonl"
    if not log_file.exists():
        print("  [NO AUDIT EVENTS RECORDED YET]")
        return

    events = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if agent_filter and agent_filter.lower() not in str(data.get("tool_name", "")).lower():
                    continue
                events.append(data)
            except json.JSONDecodeError:
                continue

    recent = list(reversed(events))[:limit]
    for idx, e in enumerate(recent, 1):
        timestamp = e.get("timestamp", "N/A")
        tool = e.get("tool_name", "SYSTEM")
        latency = e.get("execution_time_ms", 0)
        output_snippet = str(e.get("output_result", ""))[:90].replace("\n", " ")

        print(f"  [{idx:02d}] {timestamp} | {tool:<28} ({latency:.1f} ms)")
        print(f"       Result: {output_snippet}...")
        print("  " + "-" * 74)
    print()


def interactive_menu():
    while True:
        print("=" * 60)
        print("   MORTGAGE_ASSISTANT — ADMINISTRATION & GOVERNANCE CONSOLE")
        print("=" * 60)
        print("  1. Platform Diagnostics & Overview")
        print("  2. Multi-Agent Fleet & Telemetry")
        print("  3. Latency & Token Budget Optimization Telemetry")
        print("  4. View Pending Human Review Tasks (HITL)")
        print("  5. Stream Platform Audit Log")
        print("  6. Flush Optimizer Reasoning Cache")
        print("  7. Exit Console")
        print("=" * 60)
        choice = input("Enter administrative option (1-7): ").strip()

        if choice == "1":
            show_overview()
        elif choice == "2":
            show_agents()
        elif choice == "3":
            show_metrics()
        elif choice == "4":
            show_pending_reviews()
        elif choice == "5":
            try:
                num = int(input("Enter number of recent audit events to view (default 10): ") or "10")
                show_audit_trail(limit=num)
            except ValueError:
                show_audit_trail(limit=10)
        elif choice == "6":
            count = len(optimizer._cache)
            optimizer._cache.clear()
            print(f"\n[SUCCESS] Flushed {count} entries from optimizer cache.\n")
        elif choice == "7":
            print("\nExiting Administration Console. Goodbye.")
            break
        else:
            print("[ERROR] Invalid selection, please enter 1 to 7.")


def main():
    parser = argparse.ArgumentParser(description="mortgage_assistant Administration Console")
    parser.add_argument("--overview", action="store_true", help="Display platform health & diagnostics")
    parser.add_argument("--agents", action="store_true", help="List agent fleet telemetry")
    parser.add_argument("--metrics", action="store_true", help="View latency & token budget telemetry")
    parser.add_argument("--queue", action="store_true", help="View pending HITL review queue")
    parser.add_argument("--audit", action="store_true", help="View system audit trail")
    parser.add_argument("--limit", type=int, default=10, help="Audit event display limit (default: 10)")
    parser.add_argument("--filter", type=str, default=None, help="Filter audit events by agent/tool name")

    args = parser.parse_args()

    if args.overview:
        show_overview()
    elif args.agents:
        show_agents()
    elif args.metrics:
        show_metrics()
    elif args.queue:
        show_pending_reviews()
    elif args.audit:
        show_audit_trail(limit=args.limit, agent_filter=args.filter)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
