"""Offline training must read recorded candidates, never invent them."""

import json

from google.protobuf import json_format

from veyra.decision.bandit import FEATURES, candidate_from_event, train_from_events
from veyra.v1 import runtime_pb2 as pb


def _log(tmp_path, with_metadata=True):
    st = pb.CommonExecutionState(task_id="t", step=1, usage=pb.BudgetUsage())
    dec = pb.RunEvent(kind="decision", decision=pb.Decision(chosen_id="model_call:cheap"), state=st)
    if with_metadata:
        dec.json_payload = json.dumps({"candidates": [{
            "id": "model_call:cheap", "type": "MODEL_CALL", "provider": "native",
            "est_cost_usd": 0.001, "expected_success": 0.55, "risk": 0.1}]})
    fin = pb.RunEvent(kind="run_finished", status=pb.SUCCEEDED)
    p = tmp_path / "events.jsonl"
    # one compact JSON object per line, exactly like the kernel's event log
    lines = [json.dumps(json_format.MessageToDict(e)) for e in (dec, fin)]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_training_reads_candidate_metadata(tmp_path):
    model = train_from_events([str(_log(tmp_path))])
    assert "model_call:cheap" in model.theta
    assert model.theta["model_call:cheap"].shape == (FEATURES,)
    assert model.name == "bandit"


def test_training_without_metadata_yields_no_samples(tmp_path):
    model = train_from_events([str(_log(tmp_path, with_metadata=False))])
    assert model.theta == {}
    assert model.name == "bandit-untrained"


def test_candidate_from_event_parses_type_and_economics():
    ev = pb.RunEvent(json_payload=json.dumps({"candidates": [{
        "id": "switch_harness:langgraph", "type": "SWITCH_HARNESS", "provider": "langgraph",
        "est_cost_usd": 0.003, "expected_success": 0.72, "risk": 0.25}]}))
    c = candidate_from_event(ev, "switch_harness:langgraph")
    assert c is not None and c.type == pb.SWITCH_HARNESS
    assert c.est_cost_usd == 0.003 and c.expected_success == 0.72


def test_candidate_from_event_returns_none_when_absent():
    assert candidate_from_event(pb.RunEvent(), "model_call:cheap") is None
