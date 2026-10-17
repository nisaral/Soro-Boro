"""Veyra Registry: CandidateResolver abstraction and Deterministic Implementation.

Generates candidate ExecutableActions from an agent proposal and applies Hard Constraints.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from soro.core.action import ExecutableAction
from soro.core.execution_contract import ExecutionContract
from soro.core.state import ExecutionState
from soro.registry.tool_registry import ToolRegistry


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


from soro.baseline.competent import coerce_argument_types


class DeterministicCandidateResolver(CandidateResolver):
    """Resolves declared tools and declared equivalents subject to strict hard constraints and safety invariants.

    Safety Invariants:
    1. NEVER semantically guess arguments.
    2. NEVER expand the allowed action set.
    3. NEVER substitute undeclared side-effecting tools.
    4. NEVER retry uncertain-state writes without strict idempotency.
    5. NEVER bypass authorization/policy.
    6. NEVER silently change user intent.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def resolve(
        self,
        proposal: ExecutableAction,
        state: ExecutionState,
    ) -> list[ExecutableAction]:
        # 1. Determine candidate tool names (registered primary tool or declared equivalents + bounded fallbacks)
        equivs = list(self.registry.get_equivalents(proposal.tool))
        if self.registry.get(proposal.tool) is not None:
            candidate_names = [proposal.tool] + [e for e in equivs if e != proposal.tool]
        else:
            candidate_names = list(equivs)
            if proposal.executable is not None or not equivs:
                candidate_names.append(proposal.tool)

        # Add declared bounded fallbacks
        fallbacks = self.registry.get_fallback_chain(proposal.tool)
        for fb in fallbacks:
            if fb not in candidate_names:
                candidate_names.append(fb)

        # Hard Constraints Filter: Allowed tool set if declared in context
        allowed_tools = state.context.get("allowed_tools")
        if allowed_tools is not None:
            allowed_set = set(allowed_tools)
            candidate_names = [name for name in candidate_names if name in allowed_set]

        resolved_candidates: list[ExecutableAction] = []

        for name in candidate_names:
            tool_def = self.registry.get(name)

            if tool_def is not None:
                # Invariant 3 & 6: Never substitute undeclared side-effecting tools and never silently change intent
                prop_def = self.registry.get(proposal.tool)
                canon_name = self.registry._canonical_lookup.get(proposal.tool, proposal.tool)
                canon_def = self.registry.get(canon_name)
                if "idempotent" in proposal.metadata:
                    prop_idempotent = proposal.is_idempotent
                elif prop_def is not None:
                    prop_idempotent = prop_def.idempotent
                elif canon_def is not None:
                    prop_idempotent = canon_def.idempotent
                else:
                    prop_idempotent = proposal.is_idempotent

                if tool_def.idempotent != prop_idempotent:
                    # Cannot substitute read for mutation or mutation for read
                    continue

                if not tool_def.idempotent and name != proposal.tool:
                    declared_equivs = self.registry.get_equivalents(proposal.tool)
                    if name not in declared_equivs:
                        # Deny undeclared mutation substitution!
                        continue

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

                # Parameter alias mapping for this candidate
                alias_map = self.registry.get_parameter_aliases(name)
                remapped_args = dict(proposal.arguments)
                for prop_arg, canon_arg in alias_map.items():
                    if prop_arg in remapped_args and canon_arg not in remapped_args:
                        remapped_args[canon_arg] = remapped_args.pop(prop_arg)

                # Schema compatibility & safe coercion
                schema = tool_def.schema
                coerced_args = coerce_argument_types(remapped_args, schema)

                # Check required arguments
                if schema:
                    required = schema.get("required") or schema.get("parameters", {}).get("required", [])
                    # Invariant 1: NEVER semantically guess arguments!
                    if any(req not in coerced_args for req in required):
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
                    # Phase 14 Execution Contract metadata fields
                    "required_state": tool_def.required_state,
                    "freshness_sec": tool_def.freshness_sec,
                    "consistency": tool_def.consistency,
                    "side_effect_class": tool_def.side_effect_class,
                    "expected_output": tool_def.expected_output,
                    "cost": tool_def.cost,
                    "latency_ms": tool_def.latency_ms,
                    "reliability": tool_def.reliability,
                    "provenance": tool_def.provenance,
                }
                executable = tool_def.executable
                final_args = remapped_args
            else:
                # Tool not registered, fall back to proposal's own metadata
                metadata = dict(proposal.metadata)
                executable = proposal.executable
                final_args = dict(proposal.arguments)

            cand = ExecutableAction(
                tool=name,
                arguments=final_args,
                metadata=metadata,
                executable=executable,
            )

            # Phase 14: ExecutionContract validation
            contract = ExecutionContract.from_action(proposal)
            is_valid, _ = contract.validate_candidate(cand, state)
            if not is_valid:
                continue

            resolved_candidates.append(cand)

        return resolved_candidates

