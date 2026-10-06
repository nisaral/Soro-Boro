"""Tests for Veyra Boundary Safe Retry Engine."""

import pytest
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import FailureClassification, FailureKind


class TestSafeRetryPolicy:
    def setup_method(self):
        self.policy = SafeRetryPolicy(max_attempts=3, base_backoff_sec=0.1, max_backoff_sec=2.0, jitter=False)

    def test_safe_retry_allowed_for_idempotent_transient(self):
        transient = FailureClassification(kind=FailureKind.TRANSIENT_ERROR, retryable=True, repairable=True, requires_agent=False, safe_to_retry=True)
        assert self.policy.is_safe_to_retry(
            classification=transient,
            is_idempotent=True,
            is_declared_retryable=True,
            current_attempt=1,
        ) is True

    def test_unsafe_retry_forbidden_if_not_idempotent(self):
        # Non-idempotent write operation should NEVER be retried on transient error!
        transient = FailureClassification(kind=FailureKind.TRANSIENT_ERROR, retryable=True, repairable=True, requires_agent=False, safe_to_retry=False)
        assert self.policy.is_safe_to_retry(
            classification=transient,
            is_idempotent=False,
            is_declared_retryable=True,
            current_attempt=1,
        ) is False

    def test_unsafe_retry_forbidden_if_not_declared_retryable(self):
        transient = FailureClassification(kind=FailureKind.TRANSIENT_ERROR, retryable=True, repairable=True, requires_agent=False, safe_to_retry=False)
        assert self.policy.is_safe_to_retry(
            classification=transient,
            is_idempotent=True,
            is_declared_retryable=False,
            current_attempt=1,
        ) is False

    def test_retry_forbidden_for_schema_auth_precondition_unknown_state(self):
        for kind in (
            FailureKind.SCHEMA_ERROR,
            FailureKind.AUTHORIZATION_ERROR,
            FailureKind.PRECONDITION_ERROR,
            FailureKind.UNKNOWN_STATE,
            FailureKind.UNKNOWN,
        ):
            clf = FailureClassification(kind=kind, retryable=False, repairable=False, requires_agent=True, safe_to_retry=False)
            assert self.policy.is_safe_to_retry(
                classification=clf,
                is_idempotent=True,
                is_declared_retryable=True,
                current_attempt=1,
            ) is False

    def test_max_attempts_exceeded(self):
        transient = FailureClassification(kind=FailureKind.TRANSIENT_ERROR, retryable=True, repairable=True, requires_agent=False, safe_to_retry=True)
        assert self.policy.is_safe_to_retry(
            classification=transient,
            is_idempotent=True,
            is_declared_retryable=True,
            current_attempt=3,
        ) is False

    def test_backoff_and_retry_after(self):
        # Obeys explicit retry-after
        rate_limit = FailureClassification(
            kind=FailureKind.RATE_LIMIT,
            retryable=True,
            repairable=True,
            requires_agent=False,
            safe_to_retry=True,
            retry_after_sec=1.5,
        )
        assert self.policy.calculate_delay(rate_limit, attempt=1) == 1.5

        # Exponential backoff when no retry-after
        transient = FailureClassification(kind=FailureKind.TRANSIENT_ERROR, retryable=True, repairable=True, requires_agent=False, safe_to_retry=True)
        delay_1 = self.policy.calculate_delay(transient, attempt=1)
        delay_2 = self.policy.calculate_delay(transient, attempt=2)
        assert delay_1 == 0.1
        assert delay_2 == 0.2
