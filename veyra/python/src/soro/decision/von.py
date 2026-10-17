"""Adapter for a Jev-style typed decision model (Von / Kev / Laya / NanoJev).

The decision-model ecosystem converges on one shape:

    state + typed questions  ->  probabilities / scores per option

This adapter speaks a minimal HTTP form of that contract so any of those
runtimes can back the policy without Veyra depending on one of them:

    POST {endpoint}/decide
    {
      "question": "next_action",
      "context":  "<flat text summary of the state>",
      "candidates": [{"id": ..., "type": ..., "description": ...}, ...]
    }
    -> {"scores": {"<candidate id>": <float>}}
       or {"choice": "<candidate id>", "confidence": <float>}

IMPORTANT: if no endpoint is configured, this class falls back to a clearly
labelled surrogate. The surrogate is *not* a Jev model; it is a small
hand-tuned typed scorer that keeps the pipeline honest and runnable. Anything it
produces is reported with backend="von-surrogate" so it can never be mistaken
for a real model's output in the benchmark tables.
"""

from __future__ import annotations

import json
import os
from typing import Any

from soro.decision.base import DecisionModel
from soro.decision.heuristic import HeuristicDecision
from soro.v1 import runtime_pb2 as pb

DEFAULT_ENDPOINT_ENV = "VEYRA_VON_ENDPOINT"


class VonUnavailable(RuntimeError):
    """Raised when a Von endpoint is configured but cannot be reached."""


class VonDecision(DecisionModel):
    name = "von"

    def __init__(self, endpoint: str | None = None, timeout: float = 10.0,
                 question: str = "next_action", model_name: str = "von", **_):
        self.endpoint = (endpoint or os.environ.get(DEFAULT_ENDPOINT_ENV) or "").rstrip("/")
        self.timeout = timeout
        self.question = question
        self.model_name = model_name
        self._surrogate = HeuristicDecision()
        if not self.endpoint:
            self.name = "von-surrogate"

    # -- contract ----------------------------------------------------------

    def describe(self) -> str:
        if self.endpoint:
            return f"von(endpoint={self.endpoint}, model={self.model_name})"
        return "von-surrogate (no endpoint configured; NOT a real Jev model)"

    def score(self, state: pb.CommonExecutionState, allowed: list[pb.ActionCandidate]) -> dict[str, float]:
        if not self.endpoint:
            base = self._surrogate.score(state, allowed)
            # The surrogate biases away from terminating while recovery is
            # possible, which is the behaviour a typed decision model is being
            # asked to reproduce.
            for cand in allowed:
                if cand.type == pb.TERMINATE and not state.done:
                    base[cand.id] = base.get(cand.id, 0.0) - 0.4
            return base
        return self._remote_scores(state, allowed)

    def _remote_scores(self, state: pb.CommonExecutionState, allowed: list[pb.ActionCandidate]) -> dict[str, float]:
        import httpx

        from soro.contract import summarize

        payload: dict[str, Any] = {
            "question": self.question,
            "context": summarize(state),
            "candidates": [
                {
                    "id": c.id,
                    "type": pb.ActionType.Name(c.type),
                    "description": c.rationale or c.id,
                    "est_cost_usd": c.est_cost_usd,
                    "expected_success": c.expected_success,
                    "risk": c.risk,
                }
                for c in allowed
            ],
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.endpoint}/decide", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            raise VonUnavailable(f"von endpoint {self.endpoint} failed: {exc}") from exc

        if "scores" in data:
            raw = data["scores"]
            if not isinstance(raw, dict):
                raise VonUnavailable("von returned a non-object 'scores' field")
            return {str(k): float(v) for k, v in raw.items()}

        if "choice" in data:
            confidence = float(data.get("confidence", 1.0))
            out = {c.id: 0.0 for c in allowed}
            if str(data["choice"]) in out:
                out[str(data["choice"])] = confidence
            return out

        raise VonUnavailable(f"von response had neither 'scores' nor 'choice': {json.dumps(data)[:200]}")


def available(endpoint: str | None = None) -> tuple[bool, str]:
    ep = endpoint or os.environ.get(DEFAULT_ENDPOINT_ENV)
    if not ep:
        return False, "surrogate mode (no endpoint configured): NOT a real Jev-style model"
    import httpx

    try:
        with httpx.Client(timeout=3.0) as client:
            client.get(f"{ep.rstrip('/')}/health")
        return True, f"reachable at {ep}"
    except Exception as exc:
        return False, f"{ep} unreachable: {exc}"