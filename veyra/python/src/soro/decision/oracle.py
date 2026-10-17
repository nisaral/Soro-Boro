"""Offline oracle arm: an upper bound on the value of switching.

The oracle is *not* deployable and is never run online in the paper's sense. It
is given the realized outcome of every fixed-harness run for the same task and
may switch at a checkpoint to whichever harness actually did better.

It answers one question:

    If the runtime had known in advance which harness wins here,
    how much would switching have been worth?

That turns "adaptive routing helped" into a measurable gap between the adaptive
policy and an achievable ceiling.
"""

from __future__ import annotations

from soro.decision.base import DecisionModel
from soro.decision.heuristic import HeuristicDecision
from soro.v1 import runtime_pb2 as pb

PREFER_KEY = "oracle.prefer_harness"


class OracleDecision(DecisionModel):
    name = "oracle"

    def __init__(self, **_):
        self._base = HeuristicDecision()

    def describe(self) -> str:
        return "oracle(offline upper bound; needs recorder results)"

    def score(self, state: pb.CommonExecutionState, allowed: list[pb.ActionCandidate]) -> dict[str, float]:
        scores = self._base.score(state, allowed)
        prefer = state.variables.get(PREFER_KEY, "")
        # The oracle is only allowed to act on the same signal the adaptive
        # policy has: an observed failure. It is not a clairvoyant planner, it is
        # a ceiling on how well a failure-triggered switch could do.
        if not prefer or not state.failed or state.harness_id == prefer:
            return scores
        for cand in allowed:
            if cand.type == pb.SWITCH_HARNESS and cand.provider == prefer:
                scores[cand.id] = scores.get(cand.id, 0.0) + 1.0
            elif cand.type == pb.SWITCH_HARNESS:
                scores[cand.id] = scores.get(cand.id, 0.0) - 0.5
            elif cand.provider == prefer:
                scores[cand.id] = scores.get(cand.id, 0.0) + 0.15
        return scores