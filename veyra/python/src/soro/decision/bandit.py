"""Contextual bandit policy (LinUCB) over the candidate action set.

This is the "does learning help?" arm of the experiment: same candidates, same
policy constraints, learned preferences instead of hand-written rules.

Persistence is a single JSON file so a trained policy is a reviewable artifact
rather than an opaque checkpoint.

Two honesty rules are enforced here:

* An **untrained** bandit does not invent a policy. It defers to the readable
  heuristic baseline and reports itself as ``bandit-untrained``, so an untrained
  arm can never be mistaken for a learned one (or for a lucky arbitrary one).
* Training reads the exact candidate set the kernel recorded in each decision
  event. It never fabricates a candidate, because a policy fit on a guessed
  context is worse than no policy at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from soro.decision.base import DecisionModel
from soro.decision.heuristic import HeuristicDecision
from soro.v1 import runtime_pb2 as pb

FEATURES = 14

_TYPE_BY_NAME = {pb.ActionType.Name(t): t for t in range(pb.ActionType.TERMINATE + 1)}


def features(state: pb.CommonExecutionState, cand: pb.ActionCandidate, fraction: float) -> np.ndarray:
    """A deliberately small, interpretable feature vector."""
    one_hot = [
        1.0 if cand.type == pb.MODEL_CALL and "cheap" in cand.id else 0.0,
        1.0 if cand.type == pb.MODEL_CALL and "strong" in cand.id else 0.0,
        1.0 if cand.type == pb.TOOL_CALL else 0.0,
        1.0 if cand.type == pb.VERIFY else 0.0,
        1.0 if cand.type == pb.SWITCH_HARNESS else 0.0,
        1.0 if cand.type == pb.RETRY else 0.0,
        1.0 if cand.type == pb.TERMINATE else 0.0,
    ]
    return np.array(
        [
            1.0,
            *one_hot,
            float(cand.est_cost_usd) * 100.0,
            float(cand.expected_success),
            float(cand.risk),
            min(float(state.step) / 20.0, 1.0),
            1.0 if state.failed else 0.0,
            float(state.usage.usd) if state.usage else 0.0,
            float(fraction),
        ][:FEATURES],
        dtype=float,
    )


class LinUCBBandit(DecisionModel):
    def __init__(self, alpha: float = 0.6, state_path: str | None = None, **_):
        self.alpha = alpha
        self.state_path = Path(state_path) if state_path else None
        self.theta: dict[str, np.ndarray] = {}
        self._fallback = HeuristicDecision()
        self._load()

    @property
    def name(self) -> str:  # type: ignore[override]
        return "bandit" if self.theta else "bandit-untrained"

    # -- persistence -------------------------------------------------------

    def _load(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return
        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.alpha = float(raw.get("alpha", self.alpha))
        self.theta = {k: np.array(v, dtype=float) for k, v in raw.get("theta", {}).items()}

    def save(self) -> None:
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({"alpha": self.alpha, "theta": {k: v.tolist() for k, v in self.theta.items()}}, indent=2),
            encoding="utf-8",
        )

    def describe(self) -> str:
        where = f", state={self.state_path}" if self.state_path else ""
        if not self.theta:
            return f"linucb(UNTRAINED{where}; defers to heuristic)"
        return f"linucb(alpha={self.alpha}, arms={len(self.theta)}{where})"

    # -- scoring -----------------------------------------------------------

    def score(self, state: pb.CommonExecutionState, allowed: list[pb.ActionCandidate]) -> dict[str, float]:
        if not self.theta:
            return self._fallback.score(state, allowed)
        out: dict[str, float] = {}
        for cand in allowed:
            th = self.theta.get(cand.id)
            out[cand.id] = 0.0 if th is None else float(np.dot(th, features(state, cand, 0.0)))
        return out


def candidate_from_event(ev: pb.RunEvent, chosen_id: str) -> pb.ActionCandidate | None:
    """Rebuild the chosen candidate from the metadata the kernel recorded."""
    payload = {}
    if ev.json_payload:
        try:
            payload = json.loads(ev.json_payload)
        except json.JSONDecodeError:
            payload = {}
    for meta in payload.get("candidates") or []:
        if str(meta.get("id")) != chosen_id:
            continue
        return pb.ActionCandidate(
            id=chosen_id,
            type=_TYPE_BY_NAME.get(str(meta.get("type", "")), pb.MODEL_CALL),
            provider=str(meta.get("provider", "")),
            est_cost_usd=float(meta.get("est_cost_usd", 0.0)),
            expected_success=float(meta.get("expected_success", 0.0)),
            risk=float(meta.get("risk", 0.0)),
        )
    return None


def train_from_events(paths: list[str], alpha: float = 0.6, ridge: float = 1.0) -> LinUCBBandit:
    """Offline ridge fit on recorded runs.

    Reward is shaped from what the log actually shows:
      +1.0  action was followed by an observation that did not report failure
      -1.0  action was followed by a failure
      +0.5  extra for actions inside a run that ended SUCCEEDED
      -0.5  extra for actions inside a run that ended FAILED

    This is offline policy *fitting*, not causal inference; the pre-registration
    document says so explicitly.
    """
    from google.protobuf import json_format

    samples: list[tuple[np.ndarray, str, float]] = []
    for path in paths:
        events: list[pb.RunEvent] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ev = pb.RunEvent()
            json_format.Parse(line, ev)
            events.append(ev)

        final = next((e for e in reversed(events) if e.kind == "run_finished"), None)
        succeeded = bool(final and final.status == pb.SUCCEEDED)
        failed_at = {
            i for i, e in enumerate(events)
            if e.kind in ("failure", "observation") and e.HasField("state") and e.state.failed
        }

        for i, ev in enumerate(events):
            if ev.kind != "decision" or not ev.HasField("decision") or not ev.decision.chosen_id:
                continue
            chosen = ev.decision.chosen_id
            if not ev.HasField("state"):
                continue
            cand = candidate_from_event(ev, chosen)
            if cand is None:
                continue
            reward = -1.0 if (i + 1) in failed_at else 1.0
            reward += 0.5 if succeeded else -0.5
            samples.append((features(ev.state, cand, 0.0), chosen, reward))

    model = LinUCBBandit(alpha=alpha)
    arms: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for x, arm, r in samples:
        A, b = arms.get(arm, (ridge * np.eye(FEATURES), np.zeros(FEATURES)))
        A += np.outer(x, x)
        b += r * x
        arms[arm] = (A, b)

    model.theta = {arm: np.linalg.solve(A, b) for arm, (A, b) in arms.items()}
    return model
