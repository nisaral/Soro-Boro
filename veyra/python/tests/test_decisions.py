"""Decision backends: scoring, resolution, and honest self-labelling."""

import json

from veyra.decision import get_backend
from veyra.decision.base import decide, probabilities
from veyra.v1 import runtime_pb2 as pb


def cand(cid, ctype, cost=0.001, success=0.5, risk=0.1, provider=""):
    return pb.ActionCandidate(id=cid, type=ctype, est_cost_usd=cost, provider=provider,
                              expected_success=success, risk=risk)


def state(failed=False, done=False, step=1):
    return pb.CommonExecutionState(task_id="t", failed=failed, done=done, step=step,
                                   usage=pb.BudgetUsage())


def test_probabilities_are_a_distribution():
    p = probabilities({"a": 100.0, "b": -100.0})
    assert abs(sum(p.values()) - 1.0) < 1e-9
    assert p["a"] > p["b"]


def test_decide_picks_the_highest_scoring_candidate():
    allowed = [cand("model_call:cheap", pb.MODEL_CALL, success=0.5),
               cand("model_call:strong", pb.MODEL_CALL, success=0.9)]
    req = pb.DecisionRequest(backend="heuristic")
    d = decide(get_backend("heuristic"), req, allowed)
    assert d.chosen_id in {"model_call:cheap", "model_call:strong"}
    assert d.candidate_ids == ["model_call:cheap", "model_call:strong"]
    assert len(d.probabilities) == 2


def test_heuristic_prefers_switching_after_a_failure():
    allowed = [cand("model_call:cheap", pb.MODEL_CALL, success=0.55, risk=0.10),
               cand("switch_harness:langgraph", pb.SWITCH_HARNESS, success=0.72, risk=0.25, cost=0.003)]
    scores = get_backend("heuristic").score(state(failed=True), allowed)
    assert scores["switch_harness:langgraph"] > 0


def test_von_without_endpoint_labels_itself_as_a_surrogate():
    model = get_backend("von", endpoint=None)
    assert model.name == "von-surrogate"
    assert "NOT a real Jev model" in model.describe()
    scores = model.score(state(), [cand("model_call:cheap", pb.MODEL_CALL)])
    assert "model_call:cheap" in scores


def test_untrained_bandit_is_labelled_and_defers_to_heuristic():
    model = get_backend("bandit")
    assert model.name == "bandit-untrained"
    allowed = [cand("model_call:cheap", pb.MODEL_CALL), cand("terminate", pb.TERMINATE, cost=0.0, success=1.0)]
    assert model.score(state(), allowed) == get_backend("heuristic").score(state(), allowed)


def test_trained_bandit_uses_learned_weights(tmp_path):
    policy = tmp_path / "bandit.json"
    policy.write_text(json.dumps({"alpha": 0.6, "theta": {"model_call:cheap": [1.0] * 14}}), encoding="utf-8")
    model = get_backend("bandit", state_path=str(policy))
    assert model.name == "bandit"
    scores = model.score(state(), [cand("model_call:cheap", pb.MODEL_CALL)])
    assert scores["model_call:cheap"] != 0.0


def test_oracle_boosts_the_preferred_harness_only_after_failure():
    allowed = [cand("switch_harness:langgraph", pb.SWITCH_HARNESS, cost=0.003, provider="langgraph")]
    s = state(failed=True)
    s.variables["oracle.prefer_harness"] = "langgraph"
    hot = get_backend("oracle").score(s, allowed)["switch_harness:langgraph"]
    s2 = state(failed=False)
    s2.variables["oracle.prefer_harness"] = "langgraph"
    cold = get_backend("oracle").score(s2, allowed)["switch_harness:langgraph"]
    assert hot > cold, "the oracle must only boost the preferred harness after an observed failure"
