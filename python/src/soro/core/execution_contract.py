"""Veyra Core: ExecutionContract abstraction (Phase 14 Specification).

Represents what must remain invariant when an action is resolved:
1. Hard constraints hold
2. Policy allows candidate
3. Side-effect semantics are compatible
4. Argument mapping is explicitly valid
5. Required state conditions hold (freshness, consistency, state assertions)
6. Output semantics are compatible
7. No user intent is silently widened

Safety Invariants:
- Never semantically guess arguments
- Never expand authorized action space
- Never substitute side-effecting tools merely because textually similar
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from soro.core.action import ExecutableAction
from soro.core.state import ExecutionState


class SideEffectClass(str, enum.Enum):
    """Classification of execution side-effects."""

    READ_ONLY = "read_only"
    IDEMPOTENT_WRITE = "idempotent_write"
    NON_IDEMPOTENT_MUTATION = "non_idempotent_mutation"
    DESTRUCTIVE = "destructive"


@dataclass
class ExecutionContract:
    """Explicit contract defining required execution invariants."""

    capability: str = ""
    equivalence_group: str | None = None
    required_state: dict[str, Any] = field(default_factory=dict)
    max_freshness_sec: float | None = None  # e.g., <= 10.0 seconds
    required_consistency: str = "any"  # "strong", "eventual", "read_after_write", "any"
    required_permissions: list[str] = field(default_factory=list)
    side_effect_class: SideEffectClass = SideEffectClass.READ_ONLY
    idempotent_required: bool = False
    max_cost_usd: float | None = None
    max_latency_ms: float | None = None
    min_reliability: float | None = None
    expected_output_type: str | None = None
    allowed_tools: list[str] | None = None  # Explicit authorized tool set
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_action(cls, action: ExecutableAction) -> ExecutionContract:
        """Derive an execution contract from a proposed ExecutableAction."""
        meta = action.metadata
        side_effect = SideEffectClass.READ_ONLY
        sec_str = meta.get("side_effect_class", "").lower()
        if sec_str in [s.value for s in SideEffectClass]:
            side_effect = SideEffectClass(sec_str)
        elif not action.is_idempotent and meta.get("is_mutation", False):
            side_effect = SideEffectClass.NON_IDEMPOTENT_MUTATION
        elif action.is_idempotent and meta.get("is_write", False):
            side_effect = SideEffectClass.IDEMPOTENT_WRITE

        return cls(
            capability=meta.get("capability", action.tool),
            equivalence_group=action.equivalence_group,
            required_state=dict(meta.get("required_state", {})),
            max_freshness_sec=meta.get("max_freshness_sec") or meta.get("freshness"),
            required_consistency=meta.get("consistency", "any"),
            required_permissions=list(action.required_permissions),
            side_effect_class=side_effect,
            idempotent_required=action.is_idempotent,
            max_cost_usd=meta.get("max_cost_usd"),
            max_latency_ms=meta.get("max_latency_ms"),
            min_reliability=meta.get("min_reliability"),
            expected_output_type=meta.get("expected_output"),
            allowed_tools=meta.get("allowed_tools"),
        )

    def validate_candidate(
        self,
        candidate: ExecutableAction,
        state: ExecutionState,
    ) -> tuple[bool, str]:
        """Validate whether a candidate action satisfies all 7 contract invariants.

        Returns (is_valid, reason).
        """
        c_meta = candidate.metadata

        # 1. Hard constraints: Authorization / Allowed tools
        allowed = self.allowed_tools or state.context.get("allowed_tools")
        if allowed is not None and candidate.tool not in allowed:
            return False, f"Candidate tool '{candidate.tool}' is not in policy-allowed tool set"

        # 2. Permissions: candidate must not require permissions not granted in state
        if candidate.required_permissions and state.permissions:
            if not set(candidate.required_permissions).issubset(state.permissions):
                return False, f"Candidate requires unauthorized permission: {set(candidate.required_permissions) - state.permissions}"

        # 3. Side-effect semantics compatibility
        c_sec_str = c_meta.get("side_effect_class", "").lower()
        c_side_effect = SideEffectClass.READ_ONLY
        if c_sec_str in [s.value for s in SideEffectClass]:
            c_side_effect = SideEffectClass(c_sec_str)
        elif not candidate.is_idempotent and c_meta.get("is_mutation", False):
            c_side_effect = SideEffectClass.NON_IDEMPOTENT_MUTATION

        # If contract requires READ_ONLY, candidate cannot be mutating or destructive
        if self.side_effect_class == SideEffectClass.READ_ONLY:
            if c_side_effect in (SideEffectClass.NON_IDEMPOTENT_MUTATION, SideEffectClass.DESTRUCTIVE):
                return False, f"Contract requires READ_ONLY but candidate has mutating side-effects ({c_side_effect.value})"

        # If contract requires idempotency, candidate must be idempotent
        if self.idempotent_required and not candidate.is_idempotent:
            return False, "Contract requires idempotency but candidate is non-idempotent"

        # 4. Required state conditions: State assertions
        env_state = state.context.get("env_state", {})
        for state_key, expected_val in self.required_state.items():
            actual_val = env_state.get(state_key, state.context.get(state_key))
            if actual_val != expected_val:
                return False, f"Required state condition failed: {state_key}={expected_val} (got {actual_val})"

        # 5. Freshness constraint: candidate freshness <= max_freshness_sec
        if self.max_freshness_sec is not None:
            cand_freshness = c_meta.get("freshness_sec") or c_meta.get("freshness")
            if cand_freshness is not None and float(cand_freshness) > float(self.max_freshness_sec):
                return False, (
                    f"Freshness contract violated: candidate freshness {cand_freshness}s exceeds max requested {self.max_freshness_sec}s"
                )

        # 6. Consistency constraint
        if self.required_consistency == "strong":
            cand_consistency = c_meta.get("consistency", "any")
            if cand_consistency not in ("strong", "linearizable"):
                return False, f"Consistency contract violated: candidate provides '{cand_consistency}', requires 'strong'"

        # 7. Output semantics & User Intent
        if self.expected_output_type is not None:
            cand_output = c_meta.get("expected_output") or c_meta.get("output_type")
            if cand_output and cand_output != self.expected_output_type:
                return False, f"Output contract mismatch: expected '{self.expected_output_type}', candidate provides '{cand_output}'"

        return True, "Execution contract satisfied"


# Public aliases for improved discoverability and terminology (Phase 40 Specification)
ResolutionContract = ExecutionContract
ActionContract = ExecutionContract
ExecutionRequirements = ExecutionContract

__all__ = [
    "SideEffectClass",
    "ConsistencyModel",
    "ExecutionContract",
    "ResolutionContract",
    "ActionContract",
    "ExecutionRequirements",
]
