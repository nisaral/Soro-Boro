"""Veyra Core: Transaction State & Execution Boundary Safety (Phase 60 Specification).

Models transaction execution states:
- PRE: Before tool execution begins
- IN_FLIGHT: Action dispatched to network/environment
- PARTIAL: Tool performed partial mutation before connection died or timed out
- COMMITTED: Action successfully committed to environment
- UNKNOWN_ACK: Connection dropped after commit or timeout before ACK received
- VERIFIED: External oracle or idempotent status check verified actual state
- FAILED: Execution failed with no mutations committed

Allowed Recovery Actions:
- VERIFY: Read-only check against state oracle or verification tool
- IDEMPOTENCY_REPLAY: Safe replay using client idempotency key
- COMPENSATE: Explicit rollback / compensation transaction
- DEFER: Hold execution for external confirmation
- ASK: Escalate to human user
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

from soro.core.action import ExecutableAction
from soro.core.execution_contract import ExecutionContract, SideEffectClass


class TransactionState(str, enum.Enum):
    PRE = "PRE"
    IN_FLIGHT = "IN_FLIGHT"
    PARTIAL = "PARTIAL"
    COMMITTED = "COMMITTED"
    UNKNOWN_ACK = "UNKNOWN_ACK"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class RecoveryActionType(str, enum.Enum):
    VERIFY = "VERIFY"
    IDEMPOTENCY_REPLAY = "IDEMPOTENCY_REPLAY"
    COMPENSATE = "COMPENSATE"
    DEFER = "DEFER"
    ASK = "ASK"
    BLIND_RETRY = "BLIND_RETRY"  # Unsafe under non-idempotent mutation!


@dataclass
class TransactionSafetyPolicy:
    """Enforces recovery invariants across uncertain execution states."""

    allow_blind_retries: bool = False

    def evaluate_transition(
        self,
        current_state: TransactionState,
        candidate_action: ExecutableAction,
        contract: ExecutionContract,
        has_idempotency_key: bool = False,
    ) -> tuple[bool, RecoveryActionType | None, str]:
        """Validates whether candidate action is safe given transaction state.

        Returns (is_safe, action_type, reason).
        """
        is_mutation = (
            contract.side_effect_class in (SideEffectClass.NON_IDEMPOTENT_MUTATION, SideEffectClass.DESTRUCTIVE)
            or not candidate_action.is_idempotent
        )

        if current_state == TransactionState.UNKNOWN_ACK:
            if is_mutation:
                # Blind retry is strictly prohibited
                if not candidate_action.metadata.get("is_verification_tool", False):
                    if has_idempotency_key and candidate_action.metadata.get("supports_idempotency_key", False):
                        return True, RecoveryActionType.IDEMPOTENCY_REPLAY, "Safe idempotent replay with client idempotency key"
                    return False, RecoveryActionType.BLIND_RETRY, (
                        "UNSAFE REPLAY REJECTED: State is UNKNOWN_ACK. "
                        "Blind retry of non-idempotent mutation causes duplicate writes. "
                        "Action must be VERIFY or specify idempotency key."
                    )
                return True, RecoveryActionType.VERIFY, "Safe read-only state verification in UNKNOWN_ACK"

        elif current_state == TransactionState.PARTIAL:
            if is_mutation:
                if candidate_action.metadata.get("is_compensating_action", False):
                    return True, RecoveryActionType.COMPENSATE, "Safe compensation of partial mutation"
                if not candidate_action.metadata.get("is_verification_tool", False):
                    return False, RecoveryActionType.BLIND_RETRY, (
                        "UNSAFE REPLAY REJECTED: State is PARTIAL. "
                        "Replay without rollback/compensation leaves corrupted state."
                    )
                return True, RecoveryActionType.VERIFY, "Safe verification of partial state"

        elif current_state == TransactionState.COMMITTED:
            if is_mutation and not candidate_action.is_idempotent:
                return False, RecoveryActionType.BLIND_RETRY, (
                    "DUPLICATE EXECUTION REJECTED: Action already committed."
                )

        # In PRE or FAILED, non-idempotent actions are safe to attempt
        return True, None, "Execution transition allowed"
