"""Decision backends.

Every backend answers one question: given this state and these *legal*
candidates, what is the probability that each is the right next action?

Backends never invent candidates, never execute anything, and never widen the
action space. The kernel re-validates every choice regardless.
"""

from soro.decision.base import DecisionModel, decide, probabilities
from soro.decision.bandit import LinUCBBandit
from soro.decision.heuristic import HeuristicDecision
from soro.decision.oracle import OracleDecision
from soro.decision.kev import KevDecision
from soro.decision.von import VonDecision

BACKENDS: dict[str, type[DecisionModel]] = {
    "heuristic": HeuristicDecision,
    "kev": KevDecision,
    "von": VonDecision,
    "bandit": LinUCBBandit,
    "oracle": OracleDecision,
}


def get_backend(name: str, **kwargs) -> DecisionModel:
    key = name.split(":", 1)[0]
    cls = BACKENDS.get(key)
    if cls is None:
        raise KeyError(f"unknown decision backend {name!r}; known: {sorted(BACKENDS)}")
    return cls(**kwargs)


__all__ = [
    "DecisionModel",
    "HeuristicDecision",
    "VonDecision",
    "KevDecision",
    "LinUCBBandit",
    "OracleDecision",
    "BACKENDS",
    "get_backend",
    "decide",
    "probabilities",
]