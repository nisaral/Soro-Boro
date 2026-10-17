"""Deterministic tool routing: contract filter → dense shortlist → execute | ask | abstain | deny."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from soro.core.action import ExecutableAction
from soro.core.contract_evaluator import validate_candidate_shared
from soro.core.execution_contract import ExecutionContract, SideEffectClass
from soro.core.state import ExecutionState
from soro.lab.interface import RankedCandidate, ResolutionQuery
from soro.lab.strategies.dense_embedding import DenseEmbeddingStrategy

if TYPE_CHECKING:
    from soro.registry.tool_registry import ToolRegistry


class RouteKind(str, enum.Enum):
    EXECUTE = "EXECUTE"
    ASK = "ASK"
    ABSTAIN = "ABSTAIN"
    DENY = "DENY"


@dataclass
class RouteDecision:
    kind: RouteKind
    tool: str | None
    score: float
    shortlist: list[RankedCandidate]
    reason: str
    filtered_out: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "tool": self.tool,
            "score": self.score,
            "reason": self.reason,
            "shortlist": [{"tool": c.tool, "score": c.score} for c in self.shortlist],
            "filtered_out": self.filtered_out,
        }


def _side_effect(tool) -> SideEffectClass:
    raw = getattr(tool, "side_effect_class", "read_only")
    if isinstance(raw, SideEffectClass):
        return raw
    try:
        return SideEffectClass(str(raw))
    except ValueError:
        return SideEffectClass.READ_ONLY


class DeterministicRouter:
    """No LLM on the routing path. Scores are hashed dense vectors + contract checks."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        top_k: int = 10,
        execute_min: float = 0.55,
        ask_min: float = 0.28,
        confusion_gap: float = 0.08,
    ) -> None:
        self.registry = registry
        self.top_k = top_k
        self.execute_min = execute_min
        self.ask_min = ask_min
        self.confusion_gap = confusion_gap
        self._ranker = DenseEmbeddingStrategy()

    def route(
        self,
        query_text: str,
        *,
        proposed_tool: str | None = None,
        arguments: dict[str, Any] | None = None,
        state: ExecutionState | None = None,
        contract: ExecutionContract | None = None,
    ) -> RouteDecision:
        arguments = arguments or {}
        state = state or ExecutionState()
        filtered_out: dict[str, str] = {}
        catalog: list[dict[str, Any]] = []
        legal_names: set[str] = set()

        for name, tool in self.registry._tools.items():
            action = ExecutableAction(
                tool=name,
                arguments=arguments,
                metadata={
                    "idempotent": bool(tool.idempotent),
                    "permissions": list(tool.permissions),
                    "side_effect_class": _side_effect(tool).value,
                    "capability": (tool.capabilities[0] if tool.capabilities else name),
                },
            )
            tool_contract = contract or ExecutionContract(
                capability=name,
                side_effect_class=_side_effect(tool),
                required_permissions=list(tool.permissions),
                allowed_tools=None,
            )
            ok, reason = validate_candidate_shared(action, tool_contract, state, enforce_dynamic_state=False)
            if not ok:
                filtered_out[name] = reason
                continue
            legal_names.add(name)
            schema = tool.schema or {}
            catalog.append(
                {
                    "name": name,
                    "description": (tool.metadata or {}).get("description", "") or name,
                    "parameters": schema.get("parameters", schema) if isinstance(schema, dict) else {},
                }
            )

        if not catalog:
            return RouteDecision(
                kind=RouteKind.DENY,
                tool=None,
                score=0.0,
                shortlist=[],
                reason="No tool passed the contract filter",
                filtered_out=filtered_out,
            )

        query = ResolutionQuery(
            proposed_tool=proposed_tool or "",
            proposed_arguments=arguments,
            candidate_tools=catalog,
            query_text=query_text,
        )
        ranked = [c for c in self._ranker.rank(query, top_k=self.top_k) if c.tool in legal_names]
        if not ranked:
            return RouteDecision(
                kind=RouteKind.ABSTAIN,
                tool=None,
                score=0.0,
                shortlist=[],
                reason="Ranker returned no legal candidates",
                filtered_out=filtered_out,
            )

        if proposed_tool and proposed_tool in legal_names:
            hit = next((c for c in ranked if c.tool == proposed_tool), None)
            if hit is not None:
                return RouteDecision(
                    kind=RouteKind.EXECUTE,
                    tool=proposed_tool,
                    score=hit.score,
                    shortlist=ranked,
                    reason="Proposed tool is legal and in the shortlist",
                    filtered_out=filtered_out,
                )
            if proposed_tool not in legal_names:
                pass

        if proposed_tool and proposed_tool not in legal_names:
            return RouteDecision(
                kind=RouteKind.DENY,
                tool=None,
                score=0.0,
                shortlist=ranked,
                reason=filtered_out.get(proposed_tool, f"Proposed tool '{proposed_tool}' failed the contract filter"),
                filtered_out=filtered_out,
            )

        top = ranked[0]
        second = ranked[1].score if len(ranked) > 1 else 0.0
        gap = top.score - second

        if top.score >= self.execute_min and gap >= self.confusion_gap:
            return RouteDecision(
                kind=RouteKind.EXECUTE,
                tool=top.tool,
                score=top.score,
                shortlist=ranked,
                reason=f"Clear top-1 ({top.score:.3f}, gap={gap:.3f})",
                filtered_out=filtered_out,
            )
        if top.score >= self.ask_min:
            return RouteDecision(
                kind=RouteKind.ASK,
                tool=top.tool,
                score=top.score,
                shortlist=ranked,
                reason=f"Ambiguous shortlist (score={top.score:.3f}, gap={gap:.3f})",
                filtered_out=filtered_out,
            )
        return RouteDecision(
            kind=RouteKind.ABSTAIN,
            tool=None,
            score=top.score,
            shortlist=ranked,
            reason=f"Top score {top.score:.3f} below ask threshold {self.ask_min}",
            filtered_out=filtered_out,
        )
