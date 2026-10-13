"""Deprecated package path. Prefer `import soro`."""

from veyra.boundary import (
    FailureClassification,
    FailureKind,
    FailureProvenance,
    MCPToolMiddleware,
    SafeRetryPolicy,
    Veyra,
    VeyraBoundaryError,
)
from veyra.config import CapabilityConfig, EquivalenceConfig, load_equivalence_config
from veyra.core import (
    Decision,
    DecisionKind,
    ExecutableAction,
    ExecutionContract,
    ResolutionContract,
    ActionContract,
    ExecutionRequirements,
    ExecutionState,
    ExecutionTrace,
    RecoveryDecision,
    RecoveryDecisionKind,
    ReplanEvent,
    SideEffectClass,
    TraceSink,
    TrajectoryRecord,
)
from veyra.execution import ExecutionEngine
from veyra.export import StructuredTraceExporter
from veyra.plugins import PolicyPluginRegistry, default_plugins
from veyra.policy import (
    AdaptiveHistoryRoutePolicy,
    CalibratedUncertaintyEstimator,
    DeterministicRoutePolicy,
    OnlineExecutionMemory,
    RecoveryPolicy,
    ReliabilityAwareRoutePolicy,
    RiskLevel,
    RoutePolicy,
    SafeRecoveryPolicy,
    SelectiveResolutionPolicy,
    ToolReliabilityTracker,
    classify_risk,
)
from veyra.production.production_layer import Mode, ProductionConfig, VeyraMiddleware
from veyra.registry import (
    CandidateResolver,
    DeterministicCandidateResolver,
    ToolDefinition,
    ToolRegistry,
)

try:
    from soro import Soro, wrap
except ImportError:
    Soro = VeyraMiddleware  # type: ignore[misc, assignment]

    def wrap(fn, **kwargs):
        return VeyraMiddleware().wrap_function(fn, **kwargs)

__version__ = "0.2.0"

__all__ = [
    "Soro",
    "wrap",
    "Veyra",
    "VeyraMiddleware",
    "ProductionConfig",
    "Mode",
    "MCPToolMiddleware",
    "VeyraBoundaryError",
    "ExecutableAction",
    "ExecutionContract",
    "ResolutionContract",
    "ActionContract",
    "ExecutionRequirements",
    "SideEffectClass",
    "ExecutionState",
    "Decision",
    "DecisionKind",
    "RecoveryDecision",
    "RecoveryDecisionKind",
    "ExecutionTrace",
    "ReplanEvent",
    "TrajectoryRecord",
    "TraceSink",
    "FailureKind",
    "FailureClassification",
    "FailureProvenance",
    "ToolRegistry",
    "ToolDefinition",
    "CandidateResolver",
    "DeterministicCandidateResolver",
    "ExecutionEngine",
    "RoutePolicy",
    "DeterministicRoutePolicy",
    "RecoveryPolicy",
    "SafeRecoveryPolicy",
    "SafeRetryPolicy",
    "OnlineExecutionMemory",
    "AdaptiveHistoryRoutePolicy",
    "ToolReliabilityTracker",
    "ReliabilityAwareRoutePolicy",
    "CalibratedUncertaintyEstimator",
    "SelectiveResolutionPolicy",
    "EquivalenceConfig",
    "CapabilityConfig",
    "load_equivalence_config",
    "StructuredTraceExporter",
    "PolicyPluginRegistry",
    "default_plugins",
    "RiskLevel",
    "classify_risk",
]
