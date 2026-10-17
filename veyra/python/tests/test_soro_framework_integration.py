"""Tests for Soro Integration Surface: HTTP Service, Python SDK, Shadow Mode, and Sandbox Discovery."""

import pytest
from fastapi.testclient import TestClient

from soro.framework.http_service import app
from soro.framework.models import ToolCandidate, ToolDecisionType
from soro.framework.sdk import OpenAIWrap, SoroClient
from soro.framework.audit import SandboxToolAudit, synthesize_arguments_from_schema


@pytest.fixture
def client():
    return TestClient(app)


def test_http_service_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_http_service_route_read_only_singleton(client):
    payload = {
        "query": "read file contents",
        "candidate_tools": [
            {"name": "read_file", "description": "Read file", "score": 0.95, "inferred_class": "read_only"},
            {"name": "write_file", "description": "Write file", "score": 0.20, "inferred_class": "non_idempotent_mutation"},
        ],
        "alpha": 0.05,
    }
    resp = client.post("/route", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "EXECUTE"
    assert len(data["shortlist"]) == 1
    assert data["shortlist"][0]["name"] == "read_file"
    assert data["trace"]["prediction_set_size"] == 1


def test_http_service_route_mutation_requires_ask(client):
    payload = {
        "query": "send money transfer",
        "candidate_tools": [
            {"name": "transfer_funds", "description": "Transfer money", "score": 0.95, "inferred_class": "non_idempotent_mutation"},
        ],
        "alpha": 0.05,
    }
    resp = client.post("/route", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # Mutating singletons strictly require confirmation
    assert data["decision"] == "ASK"


def test_http_service_shadow_mode_logging(client):
    payload = {
        "query": "inspect logs",
        "candidate_tools": [
            {"name": "get_logs", "description": "Get logs", "score": 0.90, "inferred_class": "read_only"},
        ],
        "shadow_mode": True,
    }
    resp = client.post("/route", json=payload)
    assert resp.status_code == 200

    metrics = client.get("/shadow/metrics").json()
    assert metrics["total_observed"] > 0
    assert "recent_traces" in metrics


def test_http_service_execute_verify_before_replay(client):
    # Attempt 1 commits
    req1 = {"tool_name": "create_user", "arguments": {"name": "Alice"}, "action_id": "act_test_101"}
    resp1 = client.post("/execute", json=req1).json()
    assert resp1["status"] == "COMMITTED"
    assert resp1["was_replayed"] is False

    # Attempt 2 with same idempotency token retrieves cached verified outcome without double execution
    req2 = {"tool_name": "create_user", "arguments": {"name": "Alice"}, "action_id": "act_test_101"}
    resp2 = client.post("/execute", json=req2).json()
    assert resp2["status"] == "COMMITTED"
    assert resp2["was_replayed"] is True


def test_openai_wrapper_tool_filtering():
    sdk = SoroClient(base_url="http://testserver", local_fallback=True)
    wrap = OpenAIWrap(sdk)

    openai_tools = [
        {"type": "function", "function": {"name": "get_weather", "description": "Get current weather"}},
        {"type": "function", "function": {"name": "book_flight", "description": "Book airplane ticket"}},
        {"type": "function", "function": {"name": "delete_account", "description": "Delete user account"}},
    ]

    filtered = wrap.filter_tools("what is the weather in Tokyo?", openai_tools)
    assert len(filtered) > 0
    assert all("function" in t for t in filtered)


def test_sandbox_audit_discovery_resolves_confirmation_fatigue():
    audit = SandboxToolAudit(server_name="test_memory_server")

    # Mock environment: set deduplication semantics
    mock_db = {"observations": set()}

    def executor(name, args):
        mock_db["observations"].add(args.get("obs_text", "default"))
        return {"added": 1}

    def state_reader():
        return {"count": len(mock_db["observations"])}

    schema = {
        "type": "object",
        "properties": {"obs_text": {"type": "string"}},
        "required": ["obs_text"],
    }

    # Under name heuristic: 'add_observation' defaults to non_idempotent_mutation
    # Under sandbox state diff: Call 1 count=1, Call 2 count=1 (set dedup) -> verified idempotent_write!
    res = audit.audit_tool(
        tool_name="add_observation",
        input_schema=schema,
        executor=executor,
        state_reader=state_reader,
    )

    assert res["inferred_class"] == "non_idempotent_mutation"
    assert res["verified_class"] == "idempotent_write"
    assert res["confirmation_fatigue_avoided"] is True

    summary = audit.summarize()
    assert summary["confirmation_fatigue_cases_resolved"] == 1
