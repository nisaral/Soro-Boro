"""Veyra Strategy Lab: Dense Embedding Strategy.

Semantic vector similarity over character n-gram and token hashed representations.
Projects query and candidate tool representations into a normalized dense feature space.
Fast, sub-millisecond, zero external heavy ML dependencies.
"""

from __future__ import annotations

import math
import re
import sys
from typing import Any

from soro.lab.interface import RankedCandidate, ResolutionQuery, ResolutionStrategy


def hash_token_to_dims(token: str, num_dims: int = 256) -> list[int]:
    """Map token and its sub-ngrams into dense projection buckets."""
    h = hash(token)
    dims = [abs(h) % num_dims]
    # Character 3-grams
    if len(token) >= 3:
        for i in range(len(token) - 2):
            sub = token[i : i + 3]
            dims.append(abs(hash(sub)) % num_dims)
    return dims


def text_to_vector(text: str, num_dims: int = 256) -> list[float]:
    """Build a normalized dense vector for input text."""
    vec = [0.0] * num_dims
    tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", text)
    for tok in tokens:
        w = tok.lower()
        for d in hash_token_to_dims(w, num_dims):
            vec[d] += 1.0

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        return [v / norm for v in vec]
    return vec


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    return sum(a * b for a, b in zip(v1, v2))


class DenseEmbeddingStrategy(ResolutionStrategy):
    """Dense embedding vector retrieval strategy."""

    def __init__(self, num_dims: int = 256):
        self.num_dims = num_dims
        self._tool_vectors: dict[str, list[float]] = {}

    @property
    def name(self) -> str:
        return "dense_embedding"

    def fit(self, training_traces: list[dict[str, Any]]) -> None:
        pass

    def _index_tools(self, candidate_tools: list[dict[str, Any]]) -> None:
        self._tool_vectors.clear()
        for t in candidate_tools:
            name = t["name"]
            desc = t.get("description", "")
            props = " ".join(t.get("parameters", {}).get("properties", {}).keys())
            doc_str = f"{name} {desc} {props}"
            self._tool_vectors[name] = text_to_vector(doc_str, self.num_dims)

    def rank(self, query: ResolutionQuery, top_k: int = 5) -> list[RankedCandidate]:
        self._index_tools(query.candidate_tools)

        q_str = f"{query.proposed_tool} {' '.join(query.proposed_arguments.keys())} {query.query_text}"
        q_vec = text_to_vector(q_str, self.num_dims)

        scored: list[RankedCandidate] = []
        for name, t_vec in self._tool_vectors.items():
            sim = cosine_similarity(q_vec, t_vec)
            # Bound to [0.0, 1.0]
            sim_bounded = max(0.0, min(1.0, sim))
            scored.append(
                RankedCandidate(
                    tool=name,
                    score=round(sim_bounded, 4),
                    confidence=round(sim_bounded, 4),
                    reason=f"cosine_sim={sim_bounded:.3f}",
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    def estimate_memory_bytes(self) -> int:
        mem = sys.getsizeof(self._tool_vectors)
        for k, v in self._tool_vectors.items():
            mem += sys.getsizeof(k) + sys.getsizeof(v)
        return mem
