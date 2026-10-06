"""Veyra Safe Retry Engine.

Rules:
1. Retries ONLY when failure is TRANSIENT_ERROR or RATE_LIMIT.
2. Retries ONLY when tool is explicitly declared retryable AND operation is idempotent.
3. NEVER retries UNKNOWN_STATE, PRECONDITION_ERROR, AUTHORIZATION_ERROR, or SCHEMA_ERROR.
4. Obeys retry-after headers or exponential backoff with jitter.
5. Max attempts strictly bounded.
"""

from __future__ import annotations

import math
import random
import time
from typing import Callable

from veyra.boundary.taxonomy import FailureClassification, FailureKind


class SafeRetryPolicy:
    """Configurable safe retry policy."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_backoff_sec: float = 0.5,
        max_backoff_sec: float = 5.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_backoff_sec = base_backoff_sec
        self.max_backoff_sec = max_backoff_sec
        self.jitter = jitter

    def is_safe_to_retry(
        self,
        classification: FailureClassification,
        is_idempotent: bool,
        is_declared_retryable: bool,
        current_attempt: int,
    ) -> bool:
        """Evaluate if an action is provably safe to retry."""
        if current_attempt >= self.max_attempts:
            return False

        # Invariant 1: Must be explicitly idempotent
        if not is_idempotent:
            return False

        # Invariant 2: Must be explicitly declared retryable
        if not is_declared_retryable:
            return False

        # Invariant 3: Only transient and rate limit errors are safe to retry
        if classification.kind not in (FailureKind.TRANSIENT_ERROR, FailureKind.RATE_LIMIT):
            return False

        return True

    def calculate_delay(self, classification: FailureClassification, attempt: int) -> float:
        """Calculate backoff delay obeying retry-after if present."""
        if classification.retry_after_sec is not None and classification.retry_after_sec > 0:
            return min(classification.retry_after_sec, self.max_backoff_sec)

        # Exponential backoff: base * 2^(attempt - 1)
        delay = self.base_backoff_sec * math.pow(2, max(0, attempt - 1))
        delay = min(delay, self.max_backoff_sec)

        if self.jitter:
            delay = delay * random.uniform(0.8, 1.2)

        return max(0.01, delay)
