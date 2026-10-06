"""Veyra: drop-in tool-boundary reliability and resolution layer for AI agents."""

from veyra.boundary import (
    FailureClassification,
    FailureKind,
    MCPToolMiddleware,
    SafeRetryPolicy,
    Veyra,
    VeyraBoundaryError,
)
from veyra.core import (
    Decision,
    DecisionKind,
    ExecutableAction,
    ExecutionState,
    ExecutionTrace,
    ReplanEvent,
    RecoveryDecision,
    RecoveryDecisionKind,
    TraceSink,
)
from veyra.execution import ExecutionEngine
from veyra.policy import (
    DeterministicRoutePolicy,
    RecoveryPolicy,
    RoutePolicy,
    SafeRecoveryPolicy,
)
from veyra.registry import (
    CandidateResolver,
    DeterministicCandidateResolver,
    ToolDefinition,
    ToolRegistry,
)

__version__ = "0.2.0"

__all__ = [
    # Top-level boundary API
    "Veyra",
    "MCPToolMiddleware",
    "VeyraBoundaryError",
    # Core abstractions
    "ExecutableAction",
    "ExecutionState",
    "Decision",
    "DecisionKind",
    "RecoveryDecision",
    "RecoveryDecisionKind",
    "ExecutionTrace",
    "ReplanEvent",
    "TraceSink",
    # Runtime & Policies
    "ExecutionEngine",
    "RoutePolicy",
    "DeterministicRoutePolicy",
    "RecoveryPolicy",
    "SafeRecoveryPolicy",
    "SafeRetryPolicy",
    "FailureKind",
    "FailureClassification",
    # Tool Registry & Candidate Resolution
    "ToolRegistry",
    "ToolDefinition",
    "CandidateResolver",
    "DeterministicCandidateResolver",
]