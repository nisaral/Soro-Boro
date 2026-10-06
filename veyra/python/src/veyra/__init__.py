"""Veyra: a drop-in tool-boundary reliability layer for AI agents."""

from veyra.boundary import (
    FailureClassification,
    FailureKind,
    MCPToolMiddleware,
    SafeRetryPolicy,
    Veyra,
    VeyraBoundaryError,
)

__version__ = "0.2.0"

__all__ = [
    "Veyra",
    "SafeRetryPolicy",
    "FailureKind",
    "FailureClassification",
    "VeyraBoundaryError",
    "MCPToolMiddleware",
]