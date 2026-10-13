"""Veyra Tool Boundary Reliability Layer (v0.1)."""

from soro.boundary.audit import AuditSummary, audit_from_file, run_audit
from soro.boundary.interceptor import Veyra
from soro.boundary.mcp import MCPToolMiddleware
from soro.boundary.retry import SafeRetryPolicy
from soro.boundary.taxonomy import (
    FailureClassification,
    FailureKind,
    FailureProvenance,
    VeyraBoundaryError,
    classify_exception,
)
from soro.boundary.trace import TraceRecord, TraceRecorder
from soro.boundary.validator import SchemaValidationError, validate_and_normalize

__all__ = [
    "Veyra",
    "SafeRetryPolicy",
    "FailureKind",
    "FailureClassification",
    "FailureProvenance",
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
