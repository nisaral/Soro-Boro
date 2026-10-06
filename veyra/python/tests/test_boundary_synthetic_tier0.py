"""Benchmark Tier 0 — Unit / Synthetic Validation Suite.

Contains 200+ parameterized test cases covering:
- Schema type coercion (int, float, bool)
- Enum normalization and ambiguity
- ISO date formats
- Transient timeouts & network errors
- Rate limits with/without retry-after
- Authorization 401/403
- Precondition 404/409/locked
- Unknown state
- Idempotency invariants (safe vs unsafe retries)

Gate 0 Metrics Enforced:
- false intervention = 0
- unsafe retry = 0
- expected classification accuracy = 100%
"""

import pytest
from veyra.boundary.interceptor import Veyra
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    VeyraBoundaryError,
    classify_exception,
)
from veyra.boundary.validator import (
    SchemaValidationError,
    normalize_value,
    validate_and_normalize,
)


# ---------------------------------------------------------------------------
# Tier 0 Dataset Generation: 200+ Cases
# ---------------------------------------------------------------------------

SYNTHETIC_CLASSIFICATION_CASES = []

# 1. Schema Errors (30 cases)
for i in range(10):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (TypeError(f"arg 'count' expected integer, got str at idx {i}"), FailureKind.SCHEMA_ERROR, False)
    )
for i in range(10):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (ValueError(f"Invalid schema: missing argument 'token_{i}'"), FailureKind.SCHEMA_ERROR, False)
    )
for i in range(10):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (SchemaValidationError(f"Cannot coerce value to integer for param_{i}"), FailureKind.SCHEMA_ERROR, False)
    )

# 2. Transient Errors (50 cases: 25 idempotent, 25 non-idempotent)
for i in range(25):
    # Idempotent transient -> safe_to_retry should be TRUE
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (TimeoutError(f"Gateway timeout upstream server-{i}: 504"), FailureKind.TRANSIENT_ERROR, True, True, True)
    )
for i in range(25):
    # Non-idempotent transient -> safe_to_retry MUST be FALSE (unsafe retry prevention)
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (ConnectionError(f"Connection reset by peer during post payment-{i}"), FailureKind.TRANSIENT_ERROR, False, True, False)
    )

# 3. Rate Limit Errors (30 cases)
for i in range(15):
    # Idempotent rate limit
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (RuntimeError(f"HTTP 429 Too Many Requests: retry-after: {i + 1}"), FailureKind.RATE_LIMIT, True, True, True)
    )
for i in range(15):
    # Non-idempotent rate limit -> safe_to_retry MUST be FALSE
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (RuntimeError(f"HTTP 429 Rate limit quota exceeded for endpoint-{i}"), FailureKind.RATE_LIMIT, False, True, False)
    )

# 4. Precondition Errors (35 cases)
for i in range(15):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (ValueError(f"Customer #{i} does not exist: resource not found"), FailureKind.PRECONDITION_ERROR, False)
    )
for i in range(10):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (FileNotFoundError(f"/var/data/record_{i}.json does not exist"), FailureKind.PRECONDITION_ERROR, False)
    )
for i in range(10):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (RuntimeError(f"Precondition failed: order_{i} must be active, current state is locked"), FailureKind.PRECONDITION_ERROR, False)
    )

# 5. Authorization Errors (30 cases)
for i in range(15):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (PermissionError(f"403 Forbidden: user does not have write scope on resource_{i}"), FailureKind.AUTHORIZATION_ERROR, False)
    )
for i in range(15):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (RuntimeError(f"401 Unauthorized: token expired for client_{i}"), FailureKind.AUTHORIZATION_ERROR, False)
    )

# 6. Unknown State Errors (25 cases)
for i in range(25):
    SYNTHETIC_CLASSIFICATION_CASES.append(
        (RuntimeError(f"Unknown state: unconfirmed transaction {i} timed out during write lock"), FailureKind.UNKNOWN_STATE, False)
    )


# ---------------------------------------------------------------------------
# Tests for Gate 0 Correctness Invariants
# ---------------------------------------------------------------------------

class TestBenchmarkTier0:
    """Benchmark Tier 0 - Synthetic engineering validation."""

    def test_synthetic_classification_accuracy_and_safety(self):
        """Verify 100% classification accuracy and 0 unsafe retries across 200 synthetic cases."""
        total_cases = len(SYNTHETIC_CLASSIFICATION_CASES)
        assert total_cases >= 200, f"Expected at least 200 synthetic cases, got {total_cases}"

        classification_correct = 0
        unsafe_retries_permitted = 0

        for case in SYNTHETIC_CLASSIFICATION_CASES:
            if len(case) == 3:
                exc, expected_kind, expected_safe = case
                is_idempotent = False
                is_retryable = False
            else:
                exc, expected_kind, is_idempotent, is_retryable, expected_safe = case

            res = classify_exception(exc, is_idempotent=is_idempotent, is_declared_retryable=is_retryable)

            # Check kind classification accuracy
            if res.kind == expected_kind:
                classification_correct += 1

            # Invariant: Never allow unsafe retry
            if res.safe_to_retry and not expected_safe:
                unsafe_retries_permitted += 1

        accuracy = classification_correct / total_cases

        assert unsafe_retries_permitted == 0, f"Violation! Permitted {unsafe_retries_permitted} unsafe retries!"
        assert accuracy == 1.0, f"Classification accuracy {accuracy*100:.1f}% below 100%"

    def test_false_interventions_zero(self):
        """Verify that valid inputs pass through with ZERO false interventions."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "active": {"type": "boolean"},
            },
            "required": ["id", "name"],
        }

        # 30 perfectly valid cases
        for i in range(30):
            valid_args = {"id": i, "name": f"User_{i}", "active": True}
            normalized, corrections = validate_and_normalize(valid_args, schema=schema)
            assert normalized == valid_args
            assert len(corrections) == 0  # 0 interventions applied when input is already correct!

    def test_safe_semantic_repairs_coverage(self):
        """Verify that safe coercions work across all supported scalar and enum types."""
        schema = {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "score": {"type": "number"},
                "enabled": {"type": "boolean"},
                "status": {"type": "string", "enum": ["active", "paused", "retired"]},
                "date": {"type": "string", "format": "date"},
            },
            "required": ["user_id"],
        }

        raw_args = {
            "user_id": "4096",
            "score": "98.5",
            "enabled": "true",
            "status": "ACTIVE",
            "date": "2026/10/06",
        }

        normalized, corrections = validate_and_normalize(raw_args, schema=schema)
        assert normalized["user_id"] == 4096
        assert normalized["score"] == 98.5
        assert normalized["enabled"] is True
        assert normalized["status"] == "active"
        assert normalized["date"] == "2026-10-06"
        assert len(corrections) == 5

    def test_end_to_end_interceptor_safety_invariants(self):
        """Verify that Veyra interceptor guarantees zero unsafe retries end-to-end."""
        veyra = Veyra(retry_policy=SafeRetryPolicy(max_attempts=3, base_backoff_sec=0.001))

        # 1. Non-idempotent transient error must never be retried
        non_idempotent_calls = 0

        @veyra.tool(retryable=True, idempotent=False)
        def process_wire_transfer(amount: float):
            nonlocal non_idempotent_calls
            non_idempotent_calls += 1
            raise TimeoutError("Timeout waiting for ACH settlement")

        with pytest.raises(VeyraBoundaryError):
            process_wire_transfer(amount=1000.0)

        assert non_idempotent_calls == 1  # 0 retries!

        # 2. Authorization error must never be retried
        auth_calls = 0

        @veyra.tool(retryable=True, idempotent=True)
        def delete_database():
            nonlocal auth_calls
            auth_calls += 1
            raise PermissionError("403 Forbidden: Insufficient IAM privilege")

        with pytest.raises(VeyraBoundaryError):
            delete_database()

        assert auth_calls == 1  # 0 retries!
