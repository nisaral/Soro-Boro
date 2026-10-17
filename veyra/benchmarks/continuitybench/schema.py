"""ContinuityBench Schema (Phase 13 & 14 Specification).

Defines paired perturbation tasks, execution contracts, tool specifications,
and generalization splits (repair, gate, scorecard).
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


class PerturbationType(str, enum.Enum):
    """The 10 perturbation types defined in Phase 13."""

    A_TOOL_UNAVAILABLE = "A_tool_unavailable"
    B_TRANSIENT_TIMEOUT = "B_transient_timeout"
    C_RATE_LIMIT = "C_rate_limit"
    D_SCHEMA_DRIFT = "D_schema_drift"
    E_PARAMETER_ALIAS_DRIFT = "E_parameter_alias_drift"
    F_ENDPOINT_DEGRADATION = "F_endpoint_degradation"
    G_STALE_IMPLEMENTATION = "G_stale_implementation"
    H_DECLARED_REPLICA = "H_declared_replica"
    I_STATE_CONDITIONAL_CHOICE = "I_state_conditional_choice"
    J_COMPOUND_PERTURBATION = "J_compound_perturbation"


class GeneralizationSplit(str, enum.Enum):
    """Held-out splits required by Phase 16 & 22."""

    REPAIR = "repair"          # Development set
    GATE = "gate"              # Policy & threshold selection set
    SCORECARD = "scorecard"    # Strictly untouched held-out evaluation set


class GeneralizationType(str, enum.Enum):
    """Generalization dimensions required by Phase 16."""

    IID = "iid_holdout"
    COMPOSITIONAL = "compositional_holdout"
    TOOL_HELD_OUT = "tool_held_out"
    STATE_HELD_OUT = "state_held_out"


@dataclass
class ExecutionContractSpec:
    """Ground-truth execution contract for a task."""

    capability: str
    max_freshness_sec: float | None = None
    required_consistency: str = "any"
    side_effect_class: str = "read_only"
    required_state: dict[str, Any] = field(default_factory=dict)
    required_permissions: list[str] = field(default_factory=list)
    idempotent_required: bool = False
    expected_output_type: str | None = None


@dataclass
class ToolSpec:
    """Specification of an available tool candidate in the catalog."""

    name: str
    schema: dict[str, Any] = field(default_factory=dict)
    side_effect_class: str = "read_only"
    freshness_sec: float | None = None
    consistency: str = "any"
    idempotent: bool = True
    permissions: list[str] = field(default_factory=list)
    failure_type: str | None = None  # None = healthy, or "timeout", "rate_limit", "schema_drift", "unavailable"
    is_decoy: bool = False
    is_unsafe: bool = False
    is_forbidden: bool = False
    is_stale: bool = False


@dataclass
class ContinuityTask:
    """A paired perturbation task unit in ContinuityBench."""

    task_id: str
    split: str  # "repair" | "gate" | "scorecard"
    generalization_type: str  # "iid_holdout" | "compositional_holdout" | "tool_held_out" | "state_held_out"
    perturbation_type: str
    intended_capability: str
    intended_tool: str
    intended_arguments: dict[str, Any]
    environment_state: dict[str, Any]
    execution_contract: ExecutionContractSpec
    tools: list[ToolSpec]
    declared_equivalences: list[str]  # Tools declared equivalent by developer
    declared_aliases: dict[str, dict[str, str]]  # tool -> {alias: canon}
    declared_fallbacks: list[str]  # Ordered fallback tool names
    valid_resolution_tools: list[str]  # Tools that satisfy contract under perturbation
    forbidden_resolution_tools: list[str]  # Tools that violate contract, decoys, or unsafe mutations

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
