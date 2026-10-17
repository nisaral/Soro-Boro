"""Kev is a System One client. Without an endpoint it refuses, it does not imitate."""

import math

import pytest

from veyra.decision.base import decide
from veyra.decision.kev import KevUnavailable, probabilities_from_response
from veyra.decision import get_backend
from veyra.v1 import runtime_pb2 as pb


def test_kev_without_an_endpoint_refuses():
    model = get_backend("kev", kev_endpoint=None, endpoint=None)
    assert model.name == "kev-unconfigured"
    with pytest.raises(KevUnavailable):
        model.score(pb.CommonExecutionState(), [pb.ActionCandidate(id="a", type=pb.MODEL_CALL)])


def test_probabilities_become_the_choice(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"answers": {"next_action": {
                "type": "choice",
                "choice": "retry",
                "probabilities": {"model_call:cheap": 0.2, "retry": 0.8},
            }}}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json):
            captured["url"] = url
            captured["body"] = json
            return FakeResp()

    monkeypatch.setattr("httpx.Client", FakeClient)
    model = get_backend("kev", kev_endpoint="http://127.0.0.1:8009")
    allowed = [
        pb.ActionCandidate(id="model_call:cheap", type=pb.MODEL_CALL, rationale="cheap step"),
        pb.ActionCandidate(id="retry", type=pb.RETRY, rationale="retry"),
    ]
    req = pb.DecisionRequest(state=pb.CommonExecutionState(instruction="fix the invoice"), backend="kev")
    decision = decide(model, req, allowed)
    assert decision.chosen_id == "retry"
    assert decision.backend == "kev"
    assert captured["url"].endswith("/v1/systemone")
    assert set(captured["body"]["questions"]["next_action"]["criteria"]) == {"model_call:cheap", "retry"}
    # softmax(log p) recovers p
    ids = list(decision.candidate_ids)
    probs = dict(zip(ids, decision.probabilities))
    assert math.isclose(probs["retry"], 0.8, abs_tol=1e-6)


def test_response_parser_accepts_a_bare_choice():
    got = probabilities_from_response(
        {"answers": {"next_action": {"choice": "retry"}}},
        ["model_call:cheap", "retry"],
    )
    assert got["retry"] == 1.0
    assert got["model_call:cheap"] == 0.0
