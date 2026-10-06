"""Veyra Tool Boundary Reliability Layer (v0.1)."""

from veyra.boundary.audit import AuditSummary, audit_from_file, run_audit
from veyra.boundary.interceptor import Veyra
from veyra.boundary.mcp import MCPToolMiddleware
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    VeyraBoundaryError,
    classify_exception,
)
from veyra.boundary.trace import TraceRecord, TraceRecorder
from veyra.boundary.validator import SchemaValidationError, validate_and_normalize

__all__ = [
    "Veyra",
    "SafeRetryPolicy",
    "FailureKind",
    "FailureClassification",
    "VeyraBoundaryError",
    "classify_exception",
    "validate_and_normalize",
    "SchemaValidationError",
    "TraceRecord",
    "TraceRecorder",
    "MCPToolMiddleware",
    "AuditSummary",
    "run_audit",
    "audit_from_file",
]
