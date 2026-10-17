"""No-LLM ranking arms: InfoNCE contrastive, TAGE ensemble, LinUCB."""

from __future__ import annotations

import math
import random
from typing import Any

from soro.lab.interface import RankedCandidate, ResolutionQuery
from soro.lab.strategies.tage import HISTORY_LENGTHS, TageHistoryStrategy
from soro.routing.scale import cosine_similarity, softmax, text_to_vector


class ContrastiveEncoder:
    """Hashed-vector encoder + linear map trained with in-batch InfoNCE. No LLM."""

    def __init__(self, dim: int = 256, lr: float = 0.05, steps: int = 40, seed: int = 0) -> None:
        self.dim = dim
        self.lr = lr
        self.steps = steps
        self.rng = random.Random(seed)
        self.scale = [1.0] * dim
        self._tool_vec: dict[str, list[float]] = {}

    def _proj(self, v: list[float]) -> list[float]:
        out = [self.scale[i] * v[i] for i in range(self.dim)]
        n = math.sqrt(sum(x * x for x in out)) or 1.0
        return [x / n for x in out]

    def fit(self, tools: list[dict[str, str]]) -> None:
        docs = [(t["name"], text_to_vector(f"{t['name']} {t.get('description', '')}", self.dim)) for t in tools]
        if not docs:
            return
        for _ in range(self.steps):
            self.rng.shuffle(docs)
            batch = docs[: min(16, len(docs))]
            q_raw = [
                text_to_vector(name.replace(".", " ").replace("_", " "), self.dim) for name, _ in batch
            ]
            q = [self._proj(v) for v in q_raw]
            t = [self._proj(v) for _, v in batch]
            logits = [[cosine_similarity(qi, tj) * 8.0 for tj in t] for qi in q]
            for i, row in enumerate(logits):
                p = softmax(row, 1.0)
                for j in range(len(batch)):
                    g = (p[j] - (1.0 if i == j else 0.0)) * self.lr
                    for a in range(self.dim):
                        self.scale[a] -= g * q_raw[i][a] * t[j][a]
        self._tool_vec = {name: self._proj(vec) for name, vec in docs}

    def rank(self, query: str, names: list[str] | None = None, top_k: int = 10) -> list[RankedCandidate]:
        q = self._proj(text_to_vector(query, self.dim))
        items = names or list(self._tool_vec)
        scored = [(n, cosine_similarity(q, self._tool_vec[n])) for n in items if n in self._tool_vec]
        scored.sort(key=lambda x: x[1], reverse=True)
        out = []
        for n, s in scored[:top_k]:
            out.append(RankedCandidate(tool=n, score=round(max(0.0, s), 6), confidence=round(max(0.0, s), 6), reason=f"infonce:{s:.3f}"))
        return out


class TageEnsemble:
    """Mean of several TAGE tables (different history geometry)."""

    def __init__(self) -> None:
        self.members = [
            TageHistoryStrategy([0, 1, 2]),
            TageHistoryStrategy([0, 2, 4]),
            TageHistoryStrategy([0, 1, 2, 4, 8]),
            TageHistoryStrategy([0, 4, 8]),
        ]

    def fit(self, traces: list[dict[str, Any]]) -> None:
        for m in self.members:
            m.fit(traces)

    def rank(self, query: ResolutionQuery, top_k: int = 10) -> list[RankedCandidate]:
        acc: dict[str, float] = {}
        for m in self.members:
            for c in m.rank(query, top_k=top_k * 2):
                acc[c.tool] = acc.get(c.tool, 0.0) + c.score / len(self.members)
        ranked = sorted(acc.items(), key=lambda x: x[1], reverse=True)
        return [
            RankedCandidate(tool=n, score=round(s, 6), confidence=round(s, 6), reason="tage_ensemble")
            for n, s in ranked[:top_k]
        ]


class LinUCBBandit:
    """Ridge LinUCB over hashed query vectors. Arms = tools."""

    def __init__(self, dim: int = 256, alpha: float = 0.4) -> None:
        self.dim = dim
        self.alpha = alpha
        self.A: dict[str, list[list[float]]] = {}
        self.b: dict[str, list[float]] = {}

    def _ensure(self, arm: str) -> None:
        if arm in self.A:
            return
        self.A[arm] = [[1.0 if i == j else 0.0 for j in range(self.dim)] for i in range(self.dim)]
        self.b[arm] = [0.0] * self.dim

    def update(self, arm: str, x: list[float], reward: float) -> None:
        self._ensure(arm)
        for i in range(self.dim):
            self.b[arm][i] += reward * x[i]
            for j in range(self.dim):
                self.A[arm][i][j] += x[i] * x[j]

    def fit_from_pairs(self, pairs: list[tuple[str, str]]) -> None:
        """pairs: (query, gold_tool). Reward 1 on gold, 0 on a random other seen arm."""
        arms = list({g for _, g in pairs})
        for q, gold in pairs:
            x = text_to_vector(q, self.dim)
            self.update(gold, x, 1.0)
            other = next((a for a in arms if a != gold), None)
            if other:
                self.update(other, x, 0.0)

    def score(self, arm: str, x: list[float]) -> float:
        self._ensure(arm)
        # theta ≈ diag inverse of A (Jacobi) for speed
        theta = [self.b[arm][i] / max(self.A[arm][i][i], 1e-6) for i in range(self.dim)]
        mean = sum(theta[i] * x[i] for i in range(self.dim))
        var = sum((x[i] * x[i]) / max(self.A[arm][i][i], 1e-6) for i in range(self.dim))
        return mean + self.alpha * math.sqrt(max(var, 0.0))

    def rank(self, query: str, arms: list[str], top_k: int = 10) -> list[RankedCandidate]:
        x = text_to_vector(query, self.dim)
        scored = [(a, self.score(a, x)) for a in arms]
        scored.sort(key=lambda t: t[1], reverse=True)
        return [
            RankedCandidate(tool=a, score=round(s, 6), confidence=round(max(0.0, s), 6), reason="linucb")
            for a, s in scored[:top_k]
        ]
