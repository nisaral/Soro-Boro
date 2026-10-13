"""Local Kev router.

Kev is an Apache-2.0 decision model that speaks the System One HTTP shape
(``POST /v1/systemone``). Veyra asks one choice question whose options are the
candidates the policy already allowed. Kev returns a probability per option.
It does not call a tool.

If no endpoint is configured, scoring raises. The kernel records
``decision_fallback`` and uses its heuristic. The run is not labelled as Kev.
"""

from __future__ import annotations

import math
import os
from typing import Any

from soro.contract import summarize
from soro.decision.base import DecisionModel
from soro.v1 import runtime_pb2 as pb

DEFAULT_ENDPOINT_ENV = "VEYRA_KEV_ENDPOINT"


class KevUnavailable(RuntimeError):
    """The Kev server was requested and did not return a usable choice."""


class KevDecision(DecisionModel):
    name = "kev"

    def __init__(self, kev_endpoint: str | None = None, endpoint: str | None = None,
                 timeout: float = 60.0, model_name: str = "kev-latest", **_):
        self.endpoint = (kev_endpoint or endpoint or os.environ.get(DEFAULT_ENDPOINT_ENV) or "").rstrip("/")
        self.timeout = timeout
        self.model_name = model_name
        if not self.endpoint:
            self.name = "kev-unconfigured"

    def describe(self) -> str:
        if not self.endpoint:
            return "kev-unconfigured (set --kev-endpoint or VEYRA_KEV_ENDPOINT)"
        return f"kev(endpoint={self.endpoint}, model={self.model_name})"

    def score(self, state: pb.CommonExecutionState, allowed: list[pb.ActionCandidate]) -> dict[str, float]:
        if not self.endpoint:
            raise KevUnavailable("no Kev endpoint configured")
        if not allowed:
            return {}
        probs = self._choice_probabilities(state, allowed)
        # decide() applies softmax. log probabilities invert that, so the
        # recorded distribution matches Kev's.
        return {cid: math.log(max(p, 1e-9)) for cid, p in probs.items()}

    def _choice_probabilities(self, state: pb.CommonExecutionState, allowed: list[pb.ActionCandidate]) -> dict[str, float]:
        import httpx

        criteria = {
            c.id: (c.rationale or c.id)[:400]
            for c in allowed
        }
        body: dict[str, Any] = {
            "model": self.model_name,
            "state": _state_text(state),
            "questions": {
                "next_action": {
                    "type": "choice",
                    "instructions": "Which single next action should the harness take?",
                    "criteria": criteria,
                }
            },
        }
        url = self.endpoint if self.endpoint.endswith("/v1/systemone") else f"{self.endpoint}/v1/systemone"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
        except KevUnavailable:
            raise
        except Exception as exc:
            raise KevUnavailable(f"kev endpoint {url} failed: {exc}") from exc
        return probabilities_from_response(data, [c.id for c in allowed])


def probabilities_from_response(data: dict[str, Any], candidate_ids: list[str]) -> dict[str, float]:
    answers = data.get("answers") or {}
    answer = answers.get("next_action") or {}
    raw = answer.get("probabilities")
    if isinstance(raw, dict) and raw:
        out = {cid: float(raw.get(cid, 0.0)) for cid in candidate_ids}
        if sum(out.values()) <= 0 and answer.get("choice") in out:
            out[str(answer["choice"])] = 1.0
        return out
    choice = answer.get("choice")
    if choice in set(candidate_ids):
        return {cid: (1.0 if cid == choice else 0.0) for cid in candidate_ids}
    raise KevUnavailable("kev response had no usable next_action probabilities")


def _state_text(state: pb.CommonExecutionState) -> str:
    instruction = (state.instruction or "").strip()
    return f"task: {instruction}\n{summarize(state)}"


def available(endpoint: str | None = None) -> tuple[bool, str]:
    ep = (endpoint or os.environ.get(DEFAULT_ENDPOINT_ENV) or "").rstrip("/")
    if not ep:
        return False, "not configured (veyra compare --kev-endpoint http://127.0.0.1:8009)"
    import httpx

    health = ep if ep.endswith("/v1/models") else f"{ep}/v1/models"
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(health)
            resp.raise_for_status()
        return True, f"reachable at {ep}"
    except Exception as exc:
        return False, f"{ep} unreachable: {exc}"
