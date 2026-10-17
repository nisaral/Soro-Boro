"""The unlearned baseline. Deliberately readable.

It exists three times for a reason: the Go kernel ships this backend so the loop
works with no sidecar, and the Python copy makes the benchmark able to compare
"hand-written rules" against "learned policy" without a language change.
"""

from __future__ import annotations

from soro.decision.base import DecisionModel
from soro.v1 import runtime_pb2 as pb


class HeuristicDecision(DecisionModel):
    name = "heuristic"

    def __init__(self, cost_aversion: float = 40.0, risk_aversion: float = 0.6, **_):
        self.lam = cost_aversion
        self.mu = risk_aversion

    def score(self, state: pb.CommonExecutionState, allowed: list[pb.ActionCandidate]) -> dict[str, float]:
        out: dict[str, float] = {}
        for cand in allowed:
            s = cand.expected_success - self.lam * cand.est_cost_usd - self.mu * cand.risk
            if cand.type == pb.TERMINATE:
                if state.done:
                    s = 10.0
                elif state.failed:
                    s = -0.15
                else:
                    s = -0.5
            elif cand.type == pb.RETRY:
                if state.failed:
                    s += 0.20
            elif cand.type == pb.VERIFY:
                s += 0.10 if state.step >= 3 else -0.45
                if state.done:
                    s += 0.30
            elif cand.type == pb.SWITCH_HARNESS:
                if state.failed:
                    s += 0.18
                else:
                    s -= 0.45
            elif cand.type == pb.TOOL_CALL:
                if not state.tool_results:
                    s += 0.05
            elif cand.type == pb.MODEL_CALL:
                if state.failed:
                    s -= 0.10
            out[cand.id] = s
        return out