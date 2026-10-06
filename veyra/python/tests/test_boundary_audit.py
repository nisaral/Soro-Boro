"""Tests for Veyra Boundary Audit Surface."""

import json
from pathlib import Path
from veyra.boundary.audit import audit_from_file, run_audit
from veyra.boundary.taxonomy import FailureKind
from veyra.boundary.trace import TraceRecord


def test_audit_summary_calculation(tmp_path: Path):
    log_file = tmp_path / "traces.jsonl"

    records = [
        # Normal success
        TraceRecord(
            trace_id="t1", agent="a", tool_proposed="get_user", arguments_proposed={"id": 1},
            tool_resolved="get_user", arguments_resolved={"id": 1}, decision="direct_execution",
            failure=None, latency_ms=10.0, attempt=1, safe=True, outcome="success"
        ),
        # Argument correction (safe repair)
        TraceRecord(
            trace_id="t2", agent="a", tool_proposed="get_user", arguments_proposed={"id": "2"},
            tool_resolved="get_user", arguments_resolved={"id": 2}, decision="corrected_and_executed",
            failure=None, latency_ms=12.0, attempt=1, safe=True, outcome="success", corrections=["Coerced id to int"]
        ),
        # Retried and succeeded
        TraceRecord(
            trace_id="t3", agent="a", tool_proposed="get_user", arguments_proposed={"id": 3},
            tool_resolved="get_user", arguments_resolved={"id": 3}, decision="retried_and_succeeded",
            failure={"kind": FailureKind.TRANSIENT_ERROR.value}, latency_ms=50.0, attempt=2, safe=True, outcome="success"
        ),
        # Unrecoverable precondition failure
        TraceRecord(
            trace_id="t4", agent="a", tool_proposed="cancel_order", arguments_proposed={"order_id": 99},
            tool_resolved="cancel_order", arguments_resolved={"order_id": 99}, decision="failed_escalated",
            failure={"kind": FailureKind.PRECONDITION_ERROR.value}, latency_ms=15.0, attempt=1, safe=True, outcome="failure"
        ),
    ]

    with open(log_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r.to_dict()) + "\n")

    summary = audit_from_file(log_file)
    assert summary.total_calls == 4
    assert summary.total_failures == 2
    assert summary.total_recoveries == 2
    assert summary.agent_replans_avoided == 2
    assert summary.unsafe_retries == 0
    assert summary.failure_distribution[FailureKind.TRANSIENT_ERROR.value] == 1
    assert summary.failure_distribution[FailureKind.PRECONDITION_ERROR.value] == 1

    text = summary.format_text()
    assert "VEYRA EXECUTION AUDIT" in text
    assert "Unsafe Retry Attempts:        0" in text
