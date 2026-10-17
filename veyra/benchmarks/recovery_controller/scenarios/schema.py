"""Formal Scenario Schema for Recovery Controller Evaluation (Phase 2).

Defines the ground truth scenario structure.
CRITICAL INVARIANT: The controller NEVER receives true_execution_state.
true_execution_state is evaluated ONLY by the independent evaluator.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable


class OperationType(str, enum.Enum):
    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    PAYMENT = "PAYMENT"
    DATABASE_WRITE = "DATABASE_WRITE"
    FILE_WRITE = "FILE_WRITE"
    BATCH_MUTATION = "BATCH_MUTATION"


class TrueExecutionState(str, enum.Enum):
    NOT_COMMITTED = "NOT_COMMITTED"
    IN_FLIGHT = "IN_FLIGHT"
    COMMITTED = "COMMITTED"
    PARTIAL = "PARTIAL"
    DUPLICATED = "DUPLICATED"
    UNKNOWN = "UNKNOWN"


class FailureMode(str, enum.Enum):
    TIMEOUT = "TIMEOUT"
    CONNECTION_RESET = "CONNECTION_RESET"
    DNS_FAILURE = "DNS_FAILURE"
    HTTP_5XX = "HTTP_5XX"
    RESPONSE_LOST = "RESPONSE_LOST"
    PROCESS_CRASH = "PROCESS_CRASH"
    TOOL_EXCEPTION = "TOOL_EXCEPTION"
    PARTIAL_RESPONSE = "PARTIAL_RESPONSE"
    SERIALIZATION_FAILURE = "SERIALIZATION_FAILURE"
    CLIENT_DISCONNECT = "CLIENT_DISCONNECT"


class EvidenceType(str, enum.Enum):
    NONE = "NONE"
    STATUS_PROBE = "STATUS_PROBE"
    JOURNAL_PROBE = "JOURNAL_PROBE"
    LEDGER_PROBE = "LEDGER_PROBE"
    RESOURCE_INSPECTION = "RESOURCE_INSPECTION"
    RECONCILIATION_PROBE = "RECONCILIATION_PROBE"


class IdempotencyMode(str, enum.Enum):
    NONE = "NONE"
    SUPPORTED = "SUPPORTED"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Observation:
    """Strict execution boundary observation.
    
    CRITICAL INVARIANT: Contains ONLY telemetry available to a real runtime client.
    Guaranteed zero access to true_execution_state or evaluator-only variables.
    """

    action_id: str
    tool_name: str
    arguments: dict[str, Any]
    failure_mode: str
    status_code: int | None
    latency_ms: float
    is_timeout: bool
    verification_available: bool
    idempotency_available: bool
    idempotency_key: str | None
    reconciliation_available: bool
    compensation_available: bool
    probe_result: dict[str, Any] | None = None
    probe_freshness_sec: float | None = None
    probe_latency_ms: float | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "failure_mode": self.failure_mode,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "is_timeout": self.is_timeout,
            "verification_available": self.verification_available,
            "idempotency_available": self.idempotency_available,
            "idempotency_key": self.idempotency_key,
            "reconciliation_available": self.reconciliation_available,
            "compensation_available": self.compensation_available,
            "probe_result": self.probe_result,
        }


@dataclass
class Scenario:
    """Rigorous evaluation scenario schema."""

    scenario_id: str
    domain: str
    operation_type: OperationType
    is_mutation: bool

    # Ground truth (EVALUATOR ONLY — Controller must NOT access this!)
    true_execution_state: TrueExecutionState
    failure_mode: FailureMode

    # Tool & execution details
    tool_name: str
    arguments: dict[str, Any]

    # Capabilities & Probes
    evidence_type: EvidenceType = EvidenceType.NONE
    verification_available: bool = False
    verification_reliability: float = 1.0  # P(probe correct)
    verification_fn: Callable[..., Any] | None = None

    idempotency_mode: IdempotencyMode = IdempotencyMode.NONE
    idempotency_key: str | None = None

    reconciliation_available: bool = False
    reconciliation_fn: Callable[..., Any] | None = None

    compensation_available: bool = False
    compensation_fn: Callable[..., Any] | None = None

    # Economics & Costs
    recovery_value: float = 100.0
    duplicate_cost: float = 500.0
    action_cost: float = 1.0
    probe_cost: float = 1.0

    # Ground truth optimal safe action (For Oracle evaluation)
    expected_safe_action: str = ""

    def to_observation(self, probe_result: dict[str, Any] | None = None) -> Observation:
        """Constructs the strictly observable client-side telemetry object.
        
        Zero leakage: true_execution_state is mathematically excluded.
        """
        is_timeout = (self.failure_mode == FailureMode.TIMEOUT)
        status_code = 504 if is_timeout else (500 if self.failure_mode == FailureMode.HTTP_5XX else None)
        return Observation(
            action_id=self.scenario_id,
            tool_name=self.tool_name,
            arguments=dict(self.arguments),
            failure_mode=self.failure_mode.value,
            status_code=status_code,
            latency_ms=10500.0 if is_timeout else 120.0,
            is_timeout=is_timeout,
            verification_available=self.verification_available,
            idempotency_available=(self.idempotency_mode == IdempotencyMode.SUPPORTED),
            idempotency_key=self.idempotency_key,
            reconciliation_available=self.reconciliation_available,
            compensation_available=self.compensation_available,
            probe_result=probe_result,
        )

    def get_public_action_context(self) -> dict[str, Any]:
        """Provides only the information available to the agent/controller at the execution boundary.
        
        Strictly excludes true_execution_state.
        """
        return self.to_observation().to_dict()
