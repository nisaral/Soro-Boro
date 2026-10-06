"""Veyra Registry: CandidateResolver abstraction and Deterministic Implementation.

Generates candidate ExecutableActions from an agent proposal and applies Hard Constraints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from veyra.core.action import ExecutableAction
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolRegistry


class CandidateResolver(ABC):
    """Abstract interface for resolving proposed actions to executable candidate actions."""

    @abstractmethod
    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
    ) -> list[ExecutableAction]:
        """Resolve proposed action into candidate actions respecting hard constraints."""
        pass


class DeterministicCandidateResolver(CandidateResolver):
    """Resolves declared tools and declared equivalents subject to strict hard constraints.

    Safety Invariant:
    A routing/decision component must NEVER widen the policy-allowed action space.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
    ) -> list[ExecutableAction]:
        # 1. Determine candidate tool names (primary tool + explicit declared equivalents)
        candidate_names = self.registry.get_equivalents(proposal.tool)
        if proposal.tool not in candidate_names:
            candidate_names = [proposal.tool] + candidate_names

        # Hard Constraints Filter: Allowed tool set if declared in context
        allowed_tools = state.context.get("allowed_tools")
        if allowed_tools is not None:
            allowed_set = set(allowed_tools)
            candidate_names = [name for name in candidate_names if name in allowed_set]

        resolved_candidates: list[ExecutableAction] = []

        for name in candidate_names:
            tool_def = self.registry.get(name)

            # Metadata from definition or proposal
            if tool_def is not None:
                # Hard Constraint 1: Health check
                if not tool_def.healthy:
                    continue

                # Hard Constraint 2: Permission check
                if tool_def.permissions:
                    if not set(tool_def.permissions).issubset(state.permissions):
                        continue

                # Hard Constraint 3: Risk check against maximum allowed risk in state
                max_risk = state.context.get("max_risk")
                if max_risk == "low" and tool_def.risk_class in ("medium", "high", "destructive"):
                    continue

                metadata = {
                    "idempotent": tool_def.idempotent,
                    "retryable": tool_def.retryable,
                    "risk_class": tool_def.risk_class,
                    "capabilities": tool_def.capabilities,
                    "permissions": tool_def.permissions,
                    "protocol": tool_def.protocol,
                    "schema": tool_def.schema,
                    "equivalence_group": self.registry._canonical_lookup.get(name),
                }
                executable = tool_def.executable
            else:
                # If tool not registered in registry, fall back to proposal's own metadata
                metadata = dict(proposal.metadata)
                executable = proposal.executable

            resolved_candidates.append(
                ExecutableAction(
                    tool=name,
                    arguments=dict(proposal.arguments),
                    metadata=metadata,
                    executable=executable,
                )
            )

        return resolved_candidates
