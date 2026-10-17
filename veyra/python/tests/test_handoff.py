import json
from pathlib import Path

from veyra.handoff import compile_handoff
from veyra.harbor_agent import VeyraHarborAgent


def test_handoff_extracts_decisions_and_failures(tmp_path: Path):
    p = tmp_path / "events.jsonl"
    p.write_text(
        json.dumps({"kind": "run_started", "json_payload": json.dumps({"task": "t1", "harness": "native"})})
        + "\n"
        + json.dumps({"kind": "decision", "decision": {"chosen_id": "retry", "rationale": "failed"}})
        + "\n"
        + json.dumps({"kind": "decision_fallback", "json_payload": "controller timeout",
                      "state": {"failed": True, "failure_kind": "tool"}, "usage": {"usd": 0.1, "actions": 2}})
        + "\n",
        encoding="utf-8",
    )
    doc = compile_handoff(p, shadow=True)
    assert doc["version"] == "1"
    assert doc["task_id"] == "t1"
    assert doc["shadow"] is True
    kinds = {i["kind"] for i in doc["items"]}
    assert "decision" in kinds
    assert "failed_action" in kinds


def test_harbor_agent_is_named_veyra():
    assert VeyraHarborAgent.name() == "veyra"
