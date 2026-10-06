"""Tests for Veyra Failure Taxonomy."""

import pytest
from veyra.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    VeyraBoundaryError,
    classify_exception,
)


def test_classify_authorization_errors():
    exc = PermissionError("403 Forbidden: access denied to customer ledger")
    res = classify_exception(exc, is_idempotent=True, is_declared_retryable=True)

    assert res.kind == FailureKind.AUTHORIZATION_ERROR
    assert res.retryable is False
    assert res.safe_to_retry is False
    assert res.requires_agent is True
    assert res.status_code == 403


def test_classify_rate_limit_with_retry_after():
    exc = RuntimeError("HTTP 429 Too Many Requests: retry-after: 2.5 seconds")
    # Idempotent -> safe to retry
    res_idempotent = classify_exception(exc, is_idempotent=True, is_declared_retryable=True)
    assert res_idempotent.kind == FailureKind.RATE_LIMIT
    assert res_idempotent.retryable is True
    assert res_idempotent.safe_to_retry is True
    assert res_idempotent.retry_after_sec == 2.5

    # Non-idempotent -> unsafe to retry!
    res_non_idempotent = classify_exception(exc, is_idempotent=False, is_declared_retryable=True)
    assert res_non_idempotent.safe_to_retry is False


def test_classify_transient_error():
    exc = TimeoutError("Connection timed out after 30000ms")

    # Safe only when both idempotent AND declared retryable
    safe_res = classify_exception(exc, is_idempotent=True, is_declared_retryable=True)
    assert safe_res.kind == FailureKind.TRANSIENT_ERROR
    assert safe_res.retryable is True
    assert safe_res.safe_to_retry is True

    # Unsafe when non-idempotent
    unsafe_res = classify_exception(exc, is_idempotent=False, is_declared_retryable=True)
    assert unsafe_res.kind == FailureKind.TRANSIENT_ERROR
    assert unsafe_res.safe_to_retry is False

    # Unsafe when not declared retryable
    unsafe_res2 = classify_exception(exc, is_idempotent=True, is_declared_retryable=False)
    assert unsafe_res2.safe_to_retry is False


def test_classify_precondition_error():
    exc = ValueError("Customer 9928 does not exist: resource not found")
    res = classify_exception(exc, is_idempotent=True, is_declared_retryable=True)

    assert res.kind == FailureKind.PRECONDITION_ERROR
    assert res.retryable is False
    assert res.safe_to_retry is False
    assert res.requires_agent is True


def test_classify_schema_error():
    exc = TypeError("Missing required argument 'customer_id'")
    res = classify_exception(exc, is_idempotent=True, is_declared_retryable=True)

    assert res.kind == FailureKind.SCHEMA_ERROR
    assert res.retryable is False
    assert res.safe_to_retry is False


def test_classify_unknown_state():
    exc = RuntimeError("Write transaction in doubt: unknown state after database disconnect")
    res = classify_exception(exc, is_idempotent=True, is_declared_retryable=True)

    assert res.kind == FailureKind.UNKNOWN_STATE
    assert res.retryable is False
    assert res.safe_to_retry is False
    assert res.requires_agent is True


def test_classify_unknown():
    exc = Exception("Custom internal error xyz")
    res = classify_exception(exc)

    assert res.kind == FailureKind.UNKNOWN
    assert res.retryable is False
    assert res.safe_to_retry is False
