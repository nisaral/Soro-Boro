"""In-process Kev (Apache-2.0). Uses local HF snapshot or model hub + kev.LocalPredictor.

Supports single-turn multi-question System-One evaluation:
- tool_route: choice over candidate tools + "__abstain__"
- arg_mapping: choice mapping unrecognized LLM argument keys to target schema property names
- is_mutation: noul/boolean predicting if a tool mutates state when MCP annotations are missing

Includes a fast deterministic fallback (dense hashed embeddings + token overlap)
when local Kev weights or GPU are unavailable, ensuring microsecond CI runs.
"""

from __future__ import annotations

import math
import os
import re
import sys
import types
from pathlib import Path
from typing import Any

if sys.platform == "win32" and "fcntl" not in sys.modules:
    sys.modules["fcntl"] = types.ModuleType("fcntl")

DEFAULT_MODEL = os.environ.get("SORO_KEV_MODEL", "jaredpalmer/kev-0.8b")
DEFAULT_KEV_PATH = os.environ.get("SORO_KEV_PATH")

MUTATION_TERMS = {
    "create", "update", "delete", "write", "drop", "post", "patch", "remove",
    "insert", "upsert", "modify", "cancel", "refund", "charge", "transfer",
    "send", "publish", "deploy", "kill", "terminate", "set", "reset"
}


def _hash_token(token: str, num_dims: int = 256) -> list[int]:
    h = hash(token)
    dims = [abs(h) % num_dims]
    if len(token) >= 3:
        for i in range(len(token) - 2):
            dims.append(abs(hash(token[i : i + 3])) % num_dims)
    return dims


def _text_to_vec(text: str, num_dims: int = 256) -> list[float]:
    vec = [0.0] * num_dims
    tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", text)
    for tok in tokens:
        w = tok.lower()
        for d in _hash_token(w, num_dims):
            vec[d] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0.0 else vec


def _cosine(v1: list[float], v2: list[float]) -> float:
    return sum(a * b for a, b in zip(v1, v2))


def resolve_kev_dir(path: str | None = None) -> Path | str:
    if path:
        p = Path(path)
        if p.exists():
            return p
        return path

    if DEFAULT_KEV_PATH:
        p = Path(DEFAULT_KEV_PATH)
        if p.exists():
            return p

    hub_root = Path.home() / ".cache" / "huggingface" / "hub"
    for candidate_model in ("models--jaredpalmer--kev-0.8b", "models--jaredpalmer--kev-4b"):
        snap_dir = hub_root / candidate_model / "snapshots"
        if snap_dir.is_dir():
            snaps = sorted(snap_dir.glob("*/head.pt"))
            if snaps:
                return snaps[-1].parent

    return DEFAULT_MODEL


class LocalKevScorer:
    """Multi-question System-One decision scorer with cached lazy weights and deterministic fallback."""

    _CACHED_PRED: Any = None
    _CACHED_RUN: str | None = None

    def __init__(self, run: str | None = None, device: str | None = None) -> None:
        self.run = str(resolve_kev_dir(run))
        self.device = device or os.environ.get("SORO_KEV_DEVICE", "cpu")
        self.error: str | None = None

    def load(self) -> bool:
        if LocalKevScorer._CACHED_PRED is not None and LocalKevScorer._CACHED_RUN == self.run:
            return True
        try:
            from kev.checkpoint import LoadOptions
            from kev.predictors import LocalPredictor

            LocalKevScorer._CACHED_PRED = LocalPredictor(self.run, self.device, LoadOptions())
            LocalKevScorer._CACHED_RUN = self.run
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    @property
    def is_available(self) -> bool:
        return self.load()

    def evaluate_turn(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Evaluate one or multiple System-One questions in a single forward pass."""
        if not questions:
            return {"probabilities": {}, "answers": {}}

        # If Kev weights are available, run in-process model
        if self.load() and LocalKevScorer._CACHED_PRED is not None:
            record = {
                "state": state,
                "questions": questions,
            }
            try:
                out = LocalKevScorer._CACHED_PRED(record)
                return {
                    "probabilities": out.get("probabilities", {}),
                    "answers": out.get("answers", {}),
                }
            except Exception as exc:
                self.error = f"Kev inference failed: {exc}"

        # Fast deterministic fallback (dense hashed embeddings + token overlap)
        return self._fallback_evaluate_turn(state, questions)

    def _fallback_evaluate_turn(self, state: str, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        probabilities: dict[str, dict[str, float]] = {}
        answers: dict[str, Any] = {}
        state_vec = _text_to_vec(state)
        state_tokens = set(re.findall(r"\w+", state.lower()))

        for q_name, q_spec in questions.items():
            q_type = q_spec.get("type", "choice")
            criteria: dict[str, str] = q_spec.get("criteria", {})

            if q_type == "choice":
                if not criteria:
                    probabilities[q_name] = {}
                    answers[q_name] = None
                    continue

                scores: dict[str, float] = {}
                for opt_k, opt_desc in criteria.items():
                    if opt_k == "__abstain__":
                        continue
                    opt_text = f"{opt_k} {opt_desc}"
                    opt_vec = _text_to_vec(opt_text)
                    c_sim = _cosine(state_vec, opt_vec)
                    # Name match boost
                    for tok in re.findall(r"\w+", opt_k.lower()):
                        if len(tok) >= 3 and tok in state_tokens:
                            c_sim += 0.35
                    scores[opt_k] = max(c_sim, 0.001)

                if "__abstain__" in criteria:
                    max_score = max(scores.values()) if scores else 0.0
                    scores["__abstain__"] = max(0.20 - max_score, 0.01)

                # Softmax over scores with temperature 0.20
                temp = 0.20
                mx = max(scores.values()) if scores else 0.0
                exps = {k: math.exp((v - mx) / temp) for k, v in scores.items()}
                total = sum(exps.values()) or 1.0
                q_probs = {k: v / total for k, v in exps.items()}
                probabilities[q_name] = q_probs
                answers[q_name] = max(q_probs.keys(), key=lambda k: q_probs[k])

            elif q_type in ("noul", "boolean"):
                # Check mutation indicators
                has_mutation = any(m in state_tokens for m in MUTATION_TERMS)
                if has_mutation:
                    probabilities[q_name] = {"yes": 0.95, "no": 0.05}
                    answers[q_name] = "yes"
                else:
                    probabilities[q_name] = {"yes": 0.05, "no": 0.95}
                    answers[q_name] = "no"

            else:
                probabilities[q_name] = {}
                answers[q_name] = None

        return {"probabilities": probabilities, "answers": answers}

    def probabilities(self, query: str, options: dict[str, str]) -> dict[str, float]:
        """Convenience method for tool choice probabilities."""
        if not options:
            return {}
        questions = {
            "tool": {
                "type": "choice",
                "instructions": "Which single tool should run for this request? Use only the listed tools.",
                "criteria": options,
            }
        }
        res = self.evaluate_turn(query, questions)
        probs = res.get("probabilities", {}).get("tool", {})
        return {k: float(probs.get(k, 0.0)) for k in options}
