"""Veyra Policy: RecoveryPolicy and SafeRecoveryPolicy.

Enforces strict boundary recovery invariants:
- Only retry TRANSIENT_ERROR and RATE_LIMIT
- Only retry when action is explicitly retryable AND idempotent
- Never retry unknown state, 401/403, or preconditions
- Max attempts strictly bounded
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from soro.boundary.retry import SafeRetryPolicy
from soro.boundary.taxonomy import FailureClassification, FailureKind, FailureProvenance
from soro.core.action import ExecutableAction
from soro.core.decision import RecoveryDecision, RecoveryDecisionKind
from soro.core.state import ExecutionState


class RecoveryPolicy(ABC):
    """Abstract recovery policy interface."""

    @abstractmethod
    def recover(
        self,
        failed_action: ExecutableAction,
        failure: FailureClassification,
        state: ExecutionState,
        attempt: int,
        fallbacks: list[ExecutableAction] | None = None,
    ) -> RecoveryDecision:
        """Decide recovery action upon execution failure."""
        pass


class SafeRecoveryPolicy(RecoveryPolicy):
    """Safe, provable boundary recovery policy adhering to frozen safety invariants."""

    def __init__(self, retry_policy: SafeRetryPolicy | None = None):
        self.retry_policy = retry_policy or SafeRetryPolicy()

    def recover(
        self,
        failed_action: ExecutableAction,
        failure: FailureClassification,
        state: ExecutionState,
        attempt: int,
        fallbacks: list[ExecutableAction] | None = None,
    ) -> RecoveryDecision:
        # Check safety invariants via retry policy for the failed action
        is_safe = self.retry_policy.is_safe_to_retry(
            classification=failure,
            is_idempotent=failed_action.is_idempotent,
            is_declared_retryable=failed_action.is_retryable,
            current_attempt=attempt,
        )

        if is_safe:
            delay = self.retry_policy.calculate_delay(failure, attempt)
            return RecoveryDecision.retry(
                action=failed_action,
                delay_sec=delay,
                reason=f"safe retry allowed ({failure.kind.value}) on attempt {attempt}",
            )

        # If primary retry is not safe or exhausted, check if safe fallback is available
        if fallbacks:
            for candidate in fallbacks:
                # Safety Invariant 4: Never retry/substitute uncertain-state writes without strict idempotency
                if not failed_action.is_idempotent and (
                    failure.provenance in (FailureProvenance.TIMEOUT, FailureProvenance.UNKNOWN_STATE, FailureProvenance.UNKNOWN)
                    or failure.kind == FailureKind.UNKNOWN_STATE
                ):
                    # Write may have partially succeeded; cannot safely fall back to another mutating call!
                    break

                # Safety Invariant 3: Never substitute undeclared side-effecting tools
                if not candidate.is_idempotent:
                    # Side-effecting candidates must match the declared equivalence group
                    if candidate.equivalence_group != failed_action.equivalence_group:
                        continue

                # Candidate must not be the failed tool itself
                if candidate.tool == failed_action.tool:
                    continue

                return RecoveryDecision.fallback(
                    action=candidate,
                    reason=f"safe fallback from failed '{failed_action.tool}' ({failure.kind.value}) to declared candidate '{candidate.tool}'",
                )

        # Unsafe or non-retryable failure with no valid fallback -> strictly escalate to agent
        return RecoveryDecision.escalate(
            reason=f"failure [{failure.kind.value}] is unrecoverable at boundary: {failure.message}"
        )
