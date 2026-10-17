"""Tests for Phase 0: Fair Competent Baseline and Standardized Trajectory Logging."""

import tempfile
from pathlib import Path

import pytest
from veyra.baseline.competent import CompetentBaselineMiddleware, coerce_argument_types, is_idempotent
from veyra.boundary.taxonomy import FailureProvenance
from veyra.core.trajectory import TrajectoryRecord, TrajectoryWriter


def test_is_idempotent_rules():
    assert is_idempotent("get_account") is True
    assert is_idempotent("read_file") is True
    assert is_idempotent("list_events") is True
    assert is_idempotent("search_documents") is True
    assert is_idempotent("check_heartbeat") is True

    # Mutations are non-idempotent
    assert is_idempotent("create_account") is False
    assert is_idempotent("close_account") is False
    assert is_idempotent("delete_file") is False
    assert is_idempotent("update_record") is False
    assert is_idempotent("charge_card") is False


def test_competent_coercion():
    schema = {
        "properties": {
            "account_id": {"type": "integer"},
            "is_active": {"type": "boolean"},
            "tag": {"type": "string"},
            "metadata": {"type": "object"},
        }
    }
    raw_args = {
        "account_id": " 42 ",
        "is_active": "true",
        "tag": 12345,
        "metadata": '{"tier": "gold"}',
    }
    coerced = coerce_argument_types(raw_args, schema)
    assert coerced["account_id"] == 42
    assert coerced["is_active"] is True
    assert coerced["tag"] == "12345"
    assert coerced["metadata"] == {"tier": "gold"}


def test_competent_never_retries_non_idempotent():
    middleware = CompetentBaselineMiddleware(max_retries=2, default_backoff_sec=0.001)

    calls = 0
    def failing_mutation(tool, args):
        nonlocal calls
        calls += 1
        raise TimeoutError("503 Service Unavailable")

    with pytest.raises(TimeoutError):
        # close_account is non-idempotent -> MUST fail on attempt 1 without retry!
        middleware.execute_with_safe_retry("close_account", {"id": "1"}, failing_mutation)

    assert calls == 1  # Exactly 1 attempt, 0 unsafe retries!


def test_competent_retries_idempotent_transient():
    middleware = CompetentBaselineMiddleware(max_retries=2, default_backoff_sec=0.001)

    calls = 0
    def transient_then_success(tool, args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("503 Service Unavailable")
        return {"status": "ok"}

    res, attempts, recovered = middleware.execute_with_safe_retry(
        "get_account", {"id": "1"}, transient_then_success
    )
    assert res == {"status": "ok"}
    assert attempts == 2
    assert recovered is True


def test_trajectory_record_serialization():
    rec = TrajectoryRecord(
        task_id="test_task_1",
        arm="veyra_deterministic",
        turn_index=1,
        proposed_action={"tool_name": "get_account", "args": {"id": "123"}},
        candidate_actions=[{"tool_name": "get_account", "args": {"id": 123}}],
        selected_action={"tool_name": "get_account", "args": {"id": 123}},
        resolution_reason="schema_coercion",
        policy_decision="SELECT",
        failure_kind=None,
        failure_provenance=None,
        retry_count=0,
        recovery_action=None,
        agent_replan=False,
        tool_result={"status": "active"},
        final_success=True,
        tokens={"prompt": 120, "completion": 25, "total": 145},
        latency=12.5,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = Path(tmp_dir) / "test_traces.jsonl"
        writer = TrajectoryWriter(log_file)
        writer.write(rec)

        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        loaded = TrajectoryRecord.from_dict(TrajectoryRecord.to_dict(rec))
        assert loaded.task_id == "test_task_1"
        assert loaded.policy_decision == "SELECT"
        assert loaded.final_success is True


def test_provenance_enum_values():
    expected_provenances = {
        "AGENT_ARGUMENT_ERROR",
        "SCHEMA_VALIDATION_ERROR",
        "TOOL_IMPLEMENTATION_ERROR",
        "NETWORK_ERROR",
        "RATE_LIMIT",
        "TIMEOUT",
        "AUTHORIZATION_ERROR",
        "PRECONDITION_ERROR",
        "UNKNOWN_STATE",
        "UNKNOWN",
    }
    actual = {p.value for p in FailureProvenance}
    assert expected_provenances == actual
