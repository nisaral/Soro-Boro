"""No-LLM scale router: contract filter → cached dense/BM25 shortlist → TDM softmax → abstain.

Supports python, MCP, and HTTP tools in one catalog. Description hashes pin rug-pulls.
No generative model on this path. Optional hosted Kev/Jev is off unless an endpoint is set.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from soro.core.action import ExecutableAction
from soro.core.contract_evaluator import validate_candidate_shared
from soro.core.execution_contract import ExecutionContract, SideEffectClass
from soro.core.state import ExecutionState
from soro.framework.router import RouteDecision, RouteKind
from soro.lab.interface import RankedCandidate
from soro.lab.strategies.bm25 import BM25Strategy, tokenize_doc
from soro.lab.strategies.dense_embedding import cosine_similarity
from soro.lab.strategies.tage import TageHistoryStrategy
from soro.registry.tool_registry import ToolDefinition, ToolRegistry

ProtocolKind = Literal["python", "mcp", "http"]


def describe_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def stable_token_hash(token: str, num_dims: int) -> list[int]:
    digest = hashlib.md5(token.encode("utf-8")).digest()
    a = int.from_bytes(digest[:4], "little")
    b = int.from_bytes(digest[4:8], "little")
    return [a % num_dims, b % num_dims]


def text_to_vector(text: str, num_dims: int = 256) -> list[float]:
    vec = [0.0] * num_dims
    for tok in tokenize_doc(text):
        for d in stable_token_hash(tok, num_dims):
            vec[d] += 1.0
        if len(tok) >= 3:
            for i in range(len(tok) - 2):
                for d in stable_token_hash(tok[i : i + 3], num_dims):
                    vec[d] += 0.5
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        return [v / norm for v in vec]
    return vec


def softmax(xs: list[float], temperature: float = 1.0) -> list[float]:
    t = max(temperature, 1e-6)
    m = max(xs) if xs else 0.0
    exps = [math.exp((x - m) / t) for x in xs]
    z = sum(exps) or 1.0
    return [e / z for e in exps]


def rrf_fuse(rank_lists: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rank_lists:
        for i, name in enumerate(ranking):
            scores[name] = scores.get(name, 0.0) + 1.0 / (k + i + 1)
    return scores


@dataclass
class ToolSpec:
    name: str
    description: str
    protocol: ProtocolKind = "python"
    side_effect_class: str = "read_only"
    permissions: list[str] = field(default_factory=list)
    schema: dict[str, Any] = field(default_factory=dict)
    endpoint: str | None = None
    mcp_server: str | None = None
    executable: Callable[..., Any] | None = None
    desc_hash: str = ""

    def __post_init__(self) -> None:
        if not self.desc_hash:
            self.desc_hash = describe_hash(self.description)


class ScaleRouter:
    """Production cascade for large mixed catalogs."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        top_k: int = 16,
        execute_min: float = 0.22,
        ask_min: float = 0.08,
        confusion_gap: float = 0.04,
        temperature: float = 0.12,
        pin_descriptions: bool = True,
        use_tage: bool = True,
    ) -> None:
        self.registry = registry or ToolRegistry()
        self.top_k = top_k
        self.execute_min = execute_min
        self.ask_min = ask_min
        self.confusion_gap = confusion_gap
        self.temperature = temperature
        self.pin_descriptions = pin_descriptions
        self.use_tage = use_tage
        self.specs: dict[str, ToolSpec] = {}
        self._pinned: dict[str, str] = {}
        self._vectors: dict[str, list[float]] = {}
        self._bm25 = BM25Strategy()
        self._tage = TageHistoryStrategy()
        self._contrastive = None
        self._tage_ens = None
        self._linucb = None
        self._kev = None
        self._stale = True
        self.last_latency_ms: float = 0.0

    def register_spec(self, spec: ToolSpec) -> None:
        self.specs[spec.name] = spec
        self.registry.register(
            ToolDefinition(
                name=spec.name,
                schema=spec.schema,
                executable=spec.executable,
                permissions=list(spec.permissions),
                protocol=spec.protocol,
                side_effect_class=spec.side_effect_class,
                metadata={
                    "description": spec.description,
                    "endpoint": spec.endpoint,
                    "mcp_server": spec.mcp_server,
                    "desc_hash": spec.desc_hash,
                },
            )
        )
        self._pinned[spec.name] = spec.desc_hash
        self._stale = True

    def register_mcp_tool(self, name: str, description: str, server: str, **kwargs: Any) -> None:
        self.register_spec(ToolSpec(name=name, description=description, protocol="mcp", mcp_server=server, **kwargs))

    def register_http_tool(self, name: str, description: str, endpoint: str, **kwargs: Any) -> None:
        self.register_spec(ToolSpec(name=name, description=description, protocol="http", endpoint=endpoint, **kwargs))

    def rebuild(self) -> None:
        catalog = []
        self._vectors.clear()
        for spec in self.specs.values():
            doc = f"{spec.name} {spec.description}"
            self._vectors[spec.name] = text_to_vector(doc)
            catalog.append({"name": spec.name, "description": spec.description, "parameters": spec.schema})
        self._bm25._index_catalog(catalog)
        from soro.routing.algs import ContrastiveEncoder, LinUCBBandit, TageEnsemble

        self._contrastive = ContrastiveEncoder(steps=12)
        self._contrastive.fit([{"name": s.name, "description": s.description} for s in self.specs.values()])
        self._tage_ens = TageEnsemble()
        traces = []
        for spec in self.specs.values():
            traces.append(
                {
                    "final_success": True,
                    "proposed_action": {"tool": spec.name.split(".")[0]},
                    "selected_action": {"tool": spec.name},
                    "previous_tools": [spec.protocol],
                }
            )
        self._tage_ens.fit(traces)
        self._tage.fit(traces)
        self._linucb = LinUCBBandit()
        pairs = [(spec.description, spec.name) for spec in self.specs.values()]
        self._linucb.fit_from_pairs(pairs)
        self._stale = False

    def _ensure_index(self) -> None:
        if self._stale or len(self._vectors) != len(self.specs):
            self.rebuild()

    def rug_pulls(self) -> list[str]:
        flagged = []
        for name, spec in self.specs.items():
            pinned = self._pinned.get(name)
            if pinned and pinned != describe_hash(spec.description):
                flagged.append(name)
        return flagged

    def rank(
        self,
        query_text: str,
        *,
        legal: set[str] | None = None,
        history: list[str] | None = None,
        method: str = "cascade",
        top_k: int | None = None,
    ) -> list[RankedCandidate]:
        self._ensure_index()
        k = top_k or self.top_k
        names = [n for n in self.specs if legal is None or n in legal]
        if not names:
            return []
        q_vec = text_to_vector(query_text)
        dense_pairs = sorted(
            ((n, cosine_similarity(q_vec, self._vectors[n])) for n in names),
            key=lambda x: x[1],
            reverse=True,
        )
        q_toks = tokenize_doc(query_text)
        bm25_pairs = sorted(((n, self._bm25._score(q_toks, n)) for n in names), key=lambda x: x[1], reverse=True)

        if method == "dense":
            scored = dense_pairs
        elif method == "bm25":
            scored = bm25_pairs
        elif method == "hybrid":
            fused = rrf_fuse([[n for n, _ in dense_pairs], [n for n, _ in bm25_pairs]])
            scored = sorted(((n, fused.get(n, 0.0)) for n in names), key=lambda x: x[1], reverse=True)
        elif method == "contrastive" and self._contrastive is not None:
            ranked_c = self._contrastive.rank(query_text, names=names, top_k=k)
            scored = [(c.tool, c.score) for c in ranked_c]
        elif method == "tage_ensemble" and self._tage_ens is not None:
            from soro.lab.interface import ResolutionQuery

            q = ResolutionQuery(
                proposed_tool=dense_pairs[0][0] if dense_pairs else "",
                proposed_arguments={},
                candidate_tools=[{"name": n, "description": self.specs[n].description} for n in names],
                history=history or [dense_pairs[0][0]] if dense_pairs else [],
                query_text=query_text,
            )
            scored = [(c.tool, c.score) for c in self._tage_ens.rank(q, top_k=k)]
        elif method == "linucb" and self._linucb is not None:
            scored = [(c.tool, c.score) for c in self._linucb.rank(query_text, names, top_k=k)]
        elif method == "kev":
            short_names = [n for n, _ in dense_pairs[: min(8, k)]]
            scored = self._kev_rescore(query_text, short_names)
        elif method == "ensemble":
            lists = [[n for n, _ in dense_pairs], [n for n, _ in bm25_pairs]]
            if self._contrastive is not None:
                lists.append([c.tool for c in self._contrastive.rank(query_text, names=names, top_k=k * 2)])
            if self._linucb is not None:
                lists.append([c.tool for c in self._linucb.rank(query_text, names, top_k=k * 2)])
            fused = rrf_fuse(lists)
            scored = sorted(((n, fused.get(n, 0.0)) for n in names), key=lambda x: x[1], reverse=True)
        else:
            dense_top = [n for n, _ in dense_pairs[: max(k * 4, 32)]]
            fused = rrf_fuse([[n for n, _ in dense_pairs], [n for n, _ in bm25_pairs]])
            scored = sorted(((n, fused.get(n, 0.0)) for n in dense_top), key=lambda x: x[1], reverse=True)

        short = scored[:k]
        if self.use_tage and method == "cascade" and history:
            from soro.lab.interface import ResolutionQuery

            q = ResolutionQuery(
                proposed_tool=history[-1] if history else "",
                proposed_arguments={},
                candidate_tools=[{"name": n, "description": self.specs[n].description} for n, _ in short],
                history=history,
                query_text=query_text,
            )
            tage_rank = {c.tool: c.score for c in self._tage.rank(q, top_k=k)}
            short = sorted(
                ((n, 0.7 * s + 0.3 * tage_rank.get(n, 0.0)) for n, s in short),
                key=lambda x: x[1],
                reverse=True,
            )

        raw = [s for _, s in short]
        probs = softmax(raw, self.temperature)
        out = []
        for (name, score), p in zip(short, probs):
            out.append(
                RankedCandidate(
                    tool=name,
                    score=round(p, 6),
                    confidence=round(p, 6),
                    reason=f"{method}:{score:.4f}",
                    metadata={"protocol": self.specs[name].protocol, "raw": score},
                )
            )
        return out

    def _kev_rescore(self, query_text: str, short_names: list[str]) -> list[tuple[str, float]]:
        if not short_names:
            return []
        try:
            from soro.routing.kev_local import LocalKevScorer

            if self._kev is None:
                self._kev = LocalKevScorer()
            options = {n: self.specs[n].description for n in short_names if n in self.specs}
            probs = self._kev.probabilities(query_text, options)
            return sorted(probs.items(), key=lambda x: x[1], reverse=True)
        except Exception:
            return [(n, 0.0) for n in short_names]

    def route(
        self,
        query_text: str,
        *,
        proposed_tool: str | None = None,
        arguments: dict[str, Any] | None = None,
        state: ExecutionState | None = None,
        history: list[str] | None = None,
        method: str = "cascade",
    ) -> RouteDecision:
        t0 = time.perf_counter()
        arguments = arguments or {}
        state = state or ExecutionState()
        if self.pin_descriptions:
            pulled = self.rug_pulls()
        else:
            pulled = []
        filtered_out: dict[str, str] = {n: "description hash mismatch (rug pull)" for n in pulled}
        legal: set[str] = set()
        for name, spec in self.specs.items():
            if name in pulled:
                continue
            action = ExecutableAction(
                tool=name,
                arguments=arguments,
                metadata={
                    "idempotent": spec.side_effect_class == "read_only",
                    "permissions": list(spec.permissions),
                    "side_effect_class": spec.side_effect_class,
                    "capability": name,
                },
            )
            contract = ExecutionContract(
                capability=name,
                side_effect_class=SideEffectClass(spec.side_effect_class)
                if spec.side_effect_class in {s.value for s in SideEffectClass}
                else SideEffectClass.READ_ONLY,
                required_permissions=list(spec.permissions),
            )
            ok, reason = validate_candidate_shared(action, contract, state, enforce_dynamic_state=False)
            if ok:
                legal.add(name)
            else:
                filtered_out[name] = reason

        ranked = self.rank(query_text, legal=legal, history=history, method=method)
        self.last_latency_ms = (time.perf_counter() - t0) * 1000.0
        if not ranked:
            return RouteDecision(RouteKind.DENY, None, 0.0, [], "empty legal catalog", filtered_out)

        if proposed_tool and proposed_tool not in legal:
            return RouteDecision(
                RouteKind.DENY,
                None,
                0.0,
                ranked,
                filtered_out.get(proposed_tool, f"illegal proposal {proposed_tool}"),
                filtered_out,
            )
        if proposed_tool and proposed_tool in {c.tool for c in ranked}:
            hit = next(c for c in ranked if c.tool == proposed_tool)
            return RouteDecision(RouteKind.EXECUTE, proposed_tool, hit.score, ranked, "legal proposal", filtered_out)

        top = ranked[0]
        second = ranked[1].score if len(ranked) > 1 else 0.0
        gap = top.score - second
        if top.score >= self.execute_min and gap >= self.confusion_gap:
            kind, reason = RouteKind.EXECUTE, f"tdm p={top.score:.3f} gap={gap:.3f}"
        elif top.score >= self.ask_min:
            kind, reason = RouteKind.ASK, f"confused p={top.score:.3f} gap={gap:.3f}"
        else:
            kind, reason = RouteKind.ABSTAIN, f"low p={top.score:.3f}"
        return RouteDecision(kind, top.tool if kind != RouteKind.ABSTAIN else None, top.score, ranked, reason, filtered_out)
