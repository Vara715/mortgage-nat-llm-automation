"""
audit_logger.py
================

Starter implementation of the "Compliance Black-Box Recorder" concept from
the project deck: every tool call gets appended to an audit-ready JSONL log
with a timestamp, the tool name, its input, and its output.

SCOPE NOTE — read before presenting this as "done":
This captures the *tool-call* layer of the audit trail (what was retrieved,
what was computed) — the part that's simple to log correctly from inside
`tools.py`. The deck's fuller vision is a complete per-question record
including the LLM's own Thought/Action reasoning text and the final answer,
end to end. That fuller trace lives inside NAT's `react_agent` internals,
not in your tool code, and NAT does have an observability/tracing layer for
exactly this (OpenTelemetry-based exporters, configurable under an `general.telemetry`
block in workflow.yaml) — wiring that up is a good "Phase 3" follow-on, and
worth checking NAT's current Observability docs for the exact config schema
before you build it, since it wasn't verified as part of this pass.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIT_LOG_PATH = BASE_DIR / "logs" / "audit_log.jsonl"

_lock = Lock()


def log_tool_call(tool_name: str, tool_input: dict, tool_output: str) -> None:
    """Append one audit record. Best-effort: logging failures never break the tool call."""
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "input": tool_input,
            "output": tool_output,
        }
        with _lock:
            with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Auditing must never take down the actual tool response.
        pass
