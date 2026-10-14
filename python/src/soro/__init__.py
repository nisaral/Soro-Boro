"""Soro: middleware between the agent and tools.

Deterministic filter. Verify-before-replay on unknown ack.
No LLM on the mutating path. Abstain when unsure.
"""

from soro.boundary import (
    FailureClassification,
    FailureKind,
    FailureProvenance,
    MCPToolMiddleware,
    SafeRetryPolicy,
    Veyra,
    VeyraBoundaryError,
)
from soro.core import (
    Decision,
    DecisionKind,
    ExecutableAction,
    ExecutionContract,
    ExecutionState,
    SideEffectClass,
)
from soro.framework import Agent, DeterministicRouter, RouteDecision, RouteKind
from soro.routing import ScaleRouter, ToolSpec
from soro.production.production_layer import Mode, ProductionConfig, Soro, VeyraMiddleware

from soro.harness.pipeline import SoroHarness
from soro_boro import soro_wrap, OperationIdentity, TerminalOutcome

__version__ = "0.2.0"

__all__ = [
    "SoroHarness",
    "soro_wrap",
    "OperationIdentity",
    "TerminalOutcome",
    "Soro",
    "VeyraMiddleware",
    "wrap",
    "Agent",
    "DeterministicRouter",
    "RouteDecision",
    "RouteKind",
    "ScaleRouter",
    "ToolSpec",
    "ProductionConfig",
    "Mode",
    "MCPToolMiddleware",
    "Veyra",
    "VeyraBoundaryError",
    "ExecutionContract",
    "ExecutableAction",
    "ExecutionState",
    "SideEffectClass",
    "Decision",
    "DecisionKind",
    "SafeRetryPolicy",
    "FailureKind",
    "FailureClassification",
    "FailureProvenance",
]


def wrap(fn, **kwargs):
    """Wrap a Python function with a default Soro instance."""
    return Soro().wrap(fn, **kwargs)

