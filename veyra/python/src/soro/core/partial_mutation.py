"""Veyra Partial Mutation & Reconciliation Manager (Section 8).

Explicitly models PARTIAL_MUTATION execution state with contract hooks:
- pre_state witness
- post_condition probe
- reconciliation handler
- compensation hook

Invariant: If no safe reconciliation or compensation hook exists, resolution MUST return DEFER or DENY.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable


class PartialMutationStatus(str, enum.Enum):
    NOT_MUTATED = "NOT_MUTATED"
    PARTIALLY_COMMITTED = "PARTIALLY_COMMITTED"
    FULLY_COMMITTED = "FULLY_COMMITTED"
    RECONCILED = "RECONCILED"
    COMPENSATED = "COMPENSATED"
    UNRECOVERABLE = "UNRECOVERABLE"


@dataclass
class PartialMutationHook:
    """Contract hooks declared for handling partial mutations safely."""

    tool_name: str
    pre_state_witness: Callable[..., Any] | None = None
    post_condition_probe: Callable[..., Any] | None = None
    reconciliation_handler: Callable[..., Any] | None = None
    compensation_hook: Callable[..., Any] | None = None


@dataclass
class PartialMutationState:
    """State record tracking partial mutation progress and witnesses."""

    transaction_id: str
    entity_id: str
    steps_total: int
    steps_completed: int = 0
    pre_witness_data: dict[str, Any] = field(default_factory=dict)
    post_probe_data: dict[str, Any] = field(default_factory=dict)
    status: PartialMutationStatus = PartialMutationStatus.PARTIALLY_COMMITTED
    error_message: str = ""

    @property
    def is_partially_committed(self) -> bool:
        return 0 < self.steps_completed < self.steps_total


class PartialMutationManager:
    """Evaluates partial mutation safety and executes contract-aware reconciliation/compensation."""

    def __init__(self):
        self._hooks: dict[str, PartialMutationHook] = {}
        self._states: dict[str, PartialMutationState] = {}

    def register_hook(self, hook: PartialMutationHook) -> None:
        self._hooks[hook.tool_name] = hook

    def record_partial_state(self, state: PartialMutationState) -> None:
        self._states[state.transaction_id] = state

    def resolve_partial_mutation(
        self,
        transaction_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[PartialMutationStatus, str, Any]:
        """Resolve a partial mutation using declared hooks or abstain safely with DEFER/DENY."""
        state = self._states.get(transaction_id)
        if not state:
            return PartialMutationStatus.UNRECOVERABLE, "No transaction state witness found; denying replay", None

        hook = self._hooks.get(tool_name)
        if not hook:
            return PartialMutationStatus.UNRECOVERABLE, "No contract reconciliation or compensation hooks declared; deferring to agent", None

        # 1. Run post-condition probe if available
        if hook.post_condition_probe is not None:
            try:
                probe_res = hook.post_condition_probe(arguments)
                state.post_probe_data = probe_res if isinstance(probe_res, dict) else {"result": probe_res}
                if isinstance(probe_res, dict) and probe_res.get("fully_committed"):
                    state.status = PartialMutationStatus.FULLY_COMMITTED
                    return PartialMutationStatus.FULLY_COMMITTED, "Post-condition probe confirmed full commit", probe_res
            except Exception as e:
                state.error_message = f"Post-condition probe failed: {e}"

        # 2. Run reconciliation handler if available
        if hook.reconciliation_handler is not None:
            try:
                reconcile_res = hook.reconciliation_handler(arguments, state.steps_completed, state.steps_total)
                state.status = PartialMutationStatus.RECONCILED
                return PartialMutationStatus.RECONCILED, "Reconciliation handler successfully completed remaining steps", reconcile_res
            except Exception as e:
                state.error_message = f"Reconciliation handler failed: {e}"

        # 3. Run compensation hook if available
        if hook.compensation_hook is not None:
            try:
                comp_res = hook.compensation_hook(arguments, state.steps_completed)
                state.status = PartialMutationStatus.COMPENSATED
                return PartialMutationStatus.COMPENSATED, "Compensation hook successfully rolled back partial mutation", comp_res
            except Exception as e:
                state.status = PartialMutationStatus.UNRECOVERABLE
                return PartialMutationStatus.UNRECOVERABLE, f"Compensation hook failed: {e}", None

        return PartialMutationStatus.UNRECOVERABLE, "Reconciliation mismatch and no safe compensation available; deferring to agent", None
