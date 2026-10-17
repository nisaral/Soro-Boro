"""Shared decision plumbing: scoring, softmax, and deterministic resolution.

This mirrors `internal/decision` in the Go kernel on purpose. The kernel needs a
zero-dependency fallback so the loop and the contract tests work with no Python
at all; the Python side implements the same resolution so behaviour is identical
whichever side answers.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from soro.v1 import runtime_pb2 as pb


class DecisionModel(ABC):
    name: str = "decision"

    @abstractmethod
    def score(self, state: pb.CommonExecutionState, allowed: list[pb.ActionCandidate]) -> dict[str, float]:
        """Return a score per candidate id. Higher is better."""

    def describe(self) -> str:
        return self.name


def probabilities(scores: dict[str, float], temperature: float = 1.0) -> dict[str, float]:
    if not scores:
        return {}
    temperature = temperature or 1.0
    scaled = {k: v / temperature for k, v in scores.items()}
    mx = max(scaled.values())
    exps = {k: math.exp(v - mx) for k, v in scaled.items()}
    total = sum(exps.values()) or 1.0
    return {k: v / total for k, v in exps.items()}


def decide(
    model: DecisionModel,
    req: pb.DecisionRequest,
    allowed: list[pb.ActionCandidate],
    dropped: dict[str, str] | None = None,
) -> pb.Decision:
    dropped = dropped or {}
    scores = model.score(req.state, allowed)
    probs = probabilities(scores)

    ids = sorted(c.id for c in allowed)
    chosen = max(ids, key=lambda i: probs.get(i, 0.0), default="")
    confidence = probs.get(chosen, 0.0)

    rationale = [f"{k}: dropped ({v})" for k, v in sorted(dropped.items())]
    rationale.append(f"chose {chosen} (p={confidence:.3f}) via {model.name}")
    return pb.Decision(
        candidate_ids=ids,
        probabilities=[probs.get(i, 0.0) for i in ids],
        chosen_id=chosen,
        confidence=confidence,
        policy_id=req.backend or "default-v0.1",
        backend=model.name,
        rationale="; ".join(rationale),
    )