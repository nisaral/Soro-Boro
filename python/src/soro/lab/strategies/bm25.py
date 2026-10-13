"""Veyra Strategy Lab: BM25 Lexical Relevance Strategy.

Standard Okapi BM25 implementation (k1=1.5, b=0.75) for tool boundary retrieval.
Zero third-party dependencies, purely native Python implementation.
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from typing import Any

from soro.lab.interface import RankedCandidate, ResolutionQuery, ResolutionStrategy


def tokenize_doc(text: str) -> list[str]:
    """Tokenize arbitrary text, snake_case, camelCase, or json keys into words."""
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", text)
    return [w.lower() for w in words if len(w) > 1]


class BM25Strategy(ResolutionStrategy):
    """Okapi BM25 lexical ranking strategy over tool documentation and parameters."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._doc_lens: dict[str, int] = {}
        self._avg_dl: float = 1.0
        self._doc_freqs: dict[str, int] = {}
        self._term_freqs: dict[str, Counter[str]] = {}
        self._num_docs: int = 0

    @property
    def name(self) -> str:
        return "bm25"

    def fit(self, training_traces: list[dict[str, Any]]) -> None:
        # BM25 is catalog-driven per query or corpus-fitted
        pass

    def _index_catalog(self, candidate_tools: list[dict[str, Any]]) -> None:
        self._doc_lens.clear()
        self._doc_freqs.clear()
        self._term_freqs.clear()
        self._num_docs = len(candidate_tools)

        total_len = 0
        for tool_spec in candidate_tools:
            name = tool_spec["name"]
            desc = tool_spec.get("description", "")
            params = tool_spec.get("parameters", {})
            props = " ".join(params.get("properties", {}).keys())
            doc_text = f"{name} {name} {desc} {props}"  # Boost tool name
            tokens = tokenize_doc(doc_text)

            self._doc_lens[name] = len(tokens)
            total_len += len(tokens)

            tf = Counter(tokens)
            self._term_freqs[name] = tf

            for term in tf:
                self._doc_freqs[term] = self._doc_freqs.get(term, 0) + 1

        self._avg_dl = (total_len / self._num_docs) if self._num_docs > 0 else 1.0

    def _score(self, query_tokens: list[str], doc_name: str) -> float:
        score = 0.0
        doc_len = self._doc_lens.get(doc_name, 0)
        tf_map = self._term_freqs.get(doc_name, Counter())

        for q in query_tokens:
            if q not in tf_map:
                continue
            freq = tf_map[q]
            n_q = self._doc_freqs.get(q, 0)
            # Standard Lucene/BM25 IDF
            idf = math.log(1.0 + (self._num_docs - n_q + 0.5) / (n_q + 0.5))
            num = freq * (self.k1 + 1.0)
            den = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self._avg_dl))
            score += idf * (num / den)

        return score

    def rank(self, query: ResolutionQuery, top_k: int = 5) -> list[RankedCandidate]:
        self._index_catalog(query.candidate_tools)

        # Build query text from proposed tool, argument keys, and query text
        q_str = f"{query.proposed_tool} {query.proposed_tool} {' '.join(query.proposed_arguments.keys())} {query.query_text}"
        q_tokens = tokenize_doc(q_str)

        scored: list[RankedCandidate] = []
        max_score = 0.0

        raw_scores = []
        for tool_spec in query.candidate_tools:
            name = tool_spec["name"]
            s = self._score(q_tokens, name)
            raw_scores.append((name, s))
            if s > max_score:
                max_score = s

        for name, s in raw_scores:
            conf = (s / max_score) if max_score > 0 else 0.0
            scored.append(
                RankedCandidate(
                    tool=name,
                    score=round(s, 4),
                    confidence=round(conf, 4),
                    reason=f"bm25_score={s:.3f}",
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    def estimate_memory_bytes(self) -> int:
        mem = sys.getsizeof(self._doc_lens) + sys.getsizeof(self._doc_freqs) + sys.getsizeof(self._term_freqs)
        return mem
