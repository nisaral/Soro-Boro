"""Veyra Core Failure Taxonomy.

Every tool failure becomes a structured, classified object conforming to the
frozen failure taxonomy in docs/OBJECTIVE.md.
"""

from __future__ import annotations

import enum
import re
from dataclasses import asdict, dataclass, field
from typing import Any


class FailureProvenance(str, enum.Enum):
    AGENT_ARGUMENT_ERROR = "agent_argument_error"
    SCHEMA_VALIDATION_ERROR = "schema_validation_error"
    TOOL_IMPLEMENTATION_ERROR = "tool_implementation_error"
    NETWORK_ERROR = "network_error"
    AUTHORIZATION_ERROR = "authorization_error"
    PRECONDITION_ERROR = "precondition_error"
    UNKNOWN_STATE = "unknown_state"
    UNKNOWN = "unknown"


class FailureKind(str, enum.Enum):
    SCHEMA_ERROR = "schema_error"
    AGENT_ARGUMENT_ERROR = "agent_argument_error"
    SCHEMA_VALIDATION_ERROR = "schema_validation_error"
    TOOL_IMPLEMENTATION_ERROR = "tool_implementation_error"
    TRANSIENT_ERROR = "transient_error"
    NETWORK_ERROR = "network_error"
    RATE_LIMIT = "rate_limit"
    PRECONDITION_ERROR = "precondition_error"
    AUTHORIZATION_ERROR = "authorization_error"
    UNKNOWN_STATE = "unknown_state"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FailureClassification:
    kind: FailureKind
    retryable: bool
    repairable: bool
    requires_agent: bool
    safe_to_retry: bool
    provenance: FailureProvenance = FailureProvenance.UNKNOWN
    message: str = ""
    status_code: int | None = None
    retry_after_sec: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["provenance"] = self.provenance.value
        return d


class VeyraBoundaryError(Exception):
    """Structured error returned to the agent when Veyra cannot safely resolve a failure at the boundary."""

    def __init__(self, classification: FailureClassification, original_exc: Exception | None = None):
        self.classification = classification
        self.original_exc = original_exc
        super().__init__(f"[{classification.kind.value}] {classification.message}")


def classify_exception(
    exc: Exception,
    is_idempotent: bool = False,
    is_declared_retryable: bool = False,
) -> FailureClassification:
    """Classify any Python or API exception into the frozen Veyra failure taxonomy."""
    msg = str(exc).strip()
    exc_type = type(exc).__name__

    # 1. Tool Implementation Errors (Range shadowing, AttributeError, NameError, internal callable bugs)
    # A broken tool is NOT an agent misuse event.
    if isinstance(exc, (AttributeError, NameError, UnboundLocalError, IndexError, ZeroDivisionError)) or (
        isinstance(exc, TypeError)
        and any(
            term in msg.lower()
            for term in (
                "object is not callable",
                "cannot unpack",
                "unsupported operand type",
                "takes no arguments",
                "takes 0 positional arguments",
                "takes from",
                "positional argument following keyword",
            )
        )
    ):
        return FailureClassification(
            kind=FailureKind.TOOL_IMPLEMENTATION_ERROR,
            provenance=FailureProvenance.TOOL_IMPLEMENTATION_ERROR,
            retryable=False,
            repairable=False,
            requires_agent=True,
            safe_to_retry=False,
            message=msg or "Internal tool implementation error",
            status_code=500,
            details={"exception_type": exc_type},
        )

    # 2. Authorization Errors (401, 403, PermissionError, Scope)
    # Never retry, never guess.
    if isinstance(exc, PermissionError) or any(
        term in msg.lower() for term in ("unauthorized", "forbidden", "permission denied", "access denied", "invalid token", "401", "403")
    ):
        status = 403 if "403" in msg or "forbidden" in msg.lower() else 401
        return FailureClassification(
            kind=FailureKind.AUTHORIZATION_ERROR,
            provenance=FailureProvenance.AUTHORIZATION_ERROR,
            retryable=False,
            repairable=False,
            requires_agent=True,
            safe_to_retry=False,
            message=msg or "Authorization or permission denied",
            status_code=status,
            details={"exception_type": exc_type},
        )

    # 3. Rate Limit (429, Quota exceeded, Too Many Requests)
    if any(term in msg.lower() for term in ("rate limit", "too many requests", "429", "quota exceeded")):
        retry_after = None
        match = re.search(r"retry[-_ ]after[:= ]*([0-9.]+)", msg, re.IGNORECASE)
        if match:
            try:
                retry_after = float(match.group(1))
            except ValueError:
                pass

        safe = is_idempotent
        return FailureClassification(
            kind=FailureKind.RATE_LIMIT,
            provenance=FailureProvenance.NETWORK_ERROR,
            retryable=True,
            repairable=True,
            requires_agent=False,
            safe_to_retry=safe,
            message=msg or "Rate limit or quota exceeded",
            status_code=429,
            retry_after_sec=retry_after or 1.0,
            details={"exception_type": exc_type},
        )

    # 4. Unknown State (Write operation timed out without confirmation, unconfirmed transaction)
    if any(term in msg.lower() for term in ("unknown state", "in doubt", "unconfirmed transaction")):
        return FailureClassification(
            kind=FailureKind.UNKNOWN_STATE,
            provenance=FailureProvenance.UNKNOWN_STATE,
            retryable=False,
            repairable=False,
            requires_agent=True,
            safe_to_retry=False,
            message=msg or "Operation status unknown after unconfirmed state transition",
            details={"exception_type": exc_type},
        )

    # 5. Precondition Errors (404, Not Found, Does not exist, Resource Locked, State conflict 409, 412, FileNotFoundError)
    if isinstance(exc, FileNotFoundError) or any(
        term in msg.lower() for term in (
            "not found", "does not exist", "already exists", "precondition failed",
            "precondition_error", "conflict", "locked", "404", "409", "412", "must be active", "inactive"
        )
    ):
        status = 404 if "not found" in msg.lower() or "404" in msg or "does not exist" in msg.lower() else 409
        return FailureClassification(
            kind=FailureKind.PRECONDITION_ERROR,
            provenance=FailureProvenance.PRECONDITION_ERROR,
            retryable=False,
            repairable=False,
            requires_agent=True,
            safe_to_retry=False,
            message=msg or "Precondition or resource state requirement not satisfied",
            status_code=status,
            details={"exception_type": exc_type},
        )

    # 6. Transient Network / Server Errors (Timeout, ConnectionReset, 502, 503, 504)
    if isinstance(exc, (TimeoutError, ConnectionError)) or any(
        term in msg.lower() for term in ("timeout", "timed out", "connection reset", "connection refused", "502", "503", "504", "service unavailable", "bad gateway")
    ):
        safe = is_idempotent and is_declared_retryable
        return FailureClassification(
            kind=FailureKind.TRANSIENT_ERROR,
            provenance=FailureProvenance.NETWORK_ERROR,
            retryable=True,
            repairable=True,
            requires_agent=False,
            safe_to_retry=safe,
            message=msg or "Transient connection or service timeout error",
            status_code=503,
            details={"exception_type": exc_type},
        )

    # 7. Agent Argument & Schema Validation Errors (TypeError, ValueError, KeyError, JSONDecodeError)
    if isinstance(exc, (TypeError, ValueError, KeyError)) or any(
        term in msg.lower() for term in ("schema", "validation error", "missing argument", "required property", "invalid type", "expected type", "unknown property")
    ):
        return FailureClassification(
            kind=FailureKind.SCHEMA_ERROR,
            provenance=FailureProvenance.AGENT_ARGUMENT_ERROR,
            retryable=False,
            repairable=True,
            requires_agent=False,
            safe_to_retry=False,
            message=msg or "Tool call argument schema validation failed",
            status_code=400,
            details={"exception_type": exc_type},
        )

    # 8. Default: UNKNOWN
    return FailureClassification(
        kind=FailureKind.UNKNOWN,
        provenance=FailureProvenance.UNKNOWN,
        retryable=False,
        repairable=False,
        requires_agent=True,
        safe_to_retry=False,
        message=msg or "Unclassified failure",
        details={"exception_type": exc_type},
    )
