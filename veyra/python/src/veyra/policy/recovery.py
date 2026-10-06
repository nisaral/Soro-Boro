"""Veyra Policy: RecoveryPolicy and SafeRecoveryPolicy.

Enforces strict boundary recovery invariants:
- Only retry TRANSIENT_ERROR and RATE_LIMIT
- Only retry when action is explicitly retryable AND idempotent
- Never retry unknown state, 401/403, or preconditions
- Max attempts strictly bounded
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import FailureClassification, FailureKind
from veyra.core.action import ExecutableAction
from veyra.core.decision import RecoveryDecision, RecoveryDecisionKind
from veyra.core.state import ExecutionState


class RecoveryPolicy(ABC):
    """Abstract recovery policy interface."""

    @abstractmethod
    def recover(
        self,
        failed_action: ExecutableAction,
        failure: FailureClassification,
        state: ExecutionState,
        attempt: int,
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
    ) -> RecoveryDecision:
        # Check safety invariants via retry policy
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

        # Unsafe or non-retryable failure -> strictly escalate to agent
        return RecoveryDecision.escalate(
            reason=f"failure [{failure.kind.value}] is unrecoverable at boundary: {failure.message}"
        )
