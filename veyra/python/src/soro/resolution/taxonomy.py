"""Veyra Execution Failure Taxonomy (Section 14).

Conforms strictly to Section 14 formal taxonomy:
Every failed trajectory must be classified into one of the 15 standard failure kinds.
Addresses the distinction between Veyra-addressable boundary failures vs unaddressable
agent reasoning / semantic failures.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class TrajectoryFailureKind(str, enum.Enum):
    """15 Formal Trajectory Failure Classes (Section 14)."""

    AGENT_REASONING_FAILURE = "AGENT_REASONING_FAILURE"
    AGENT_ARGUMENT_FAILURE = "AGENT_ARGUMENT_FAILURE"
    TOOL_SELECTION_FAILURE = "TOOL_SELECTION_FAILURE"
    SCHEMA_FAILURE = "SCHEMA_FAILURE"
    AUTHORIZATION_FAILURE = "AUTHORIZATION_FAILURE"
    TENANT_FAILURE = "TENANT_FAILURE"
    PRECONDITION_FAILURE = "PRECONDITION_FAILURE"
    TOOL_IMPLEMENTATION_FAILURE = "TOOL_IMPLEMENTATION_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    RATE_LIMIT = "RATE_LIMIT"
    UNKNOWN_ACK = "UNKNOWN_ACK"
    PARTIAL_MUTATION = "PARTIAL_MUTATION"
    RECOVERY_FAILURE = "RECOVERY_FAILURE"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    UNRECOVERABLE_SEMANTIC_FAILURE = "UNRECOVERABLE_SEMANTIC_FAILURE"


# Map which failures are directly addressable or preventable by Veyra execution resolution:
VEYRA_ADDRESSABLE_FAILURES = {
    TrajectoryFailureKind.SCHEMA_FAILURE,
    TrajectoryFailureKind.AUTHORIZATION_FAILURE,
    TrajectoryFailureKind.TENANT_FAILURE,
    TrajectoryFailureKind.PRECONDITION_FAILURE,
    TrajectoryFailureKind.NETWORK_FAILURE,
    TrajectoryFailureKind.RATE_LIMIT,
    TrajectoryFailureKind.UNKNOWN_ACK,
    TrajectoryFailureKind.PARTIAL_MUTATION,
    TrajectoryFailureKind.RECOVERY_FAILURE,
    TrajectoryFailureKind.VERIFICATION_FAILURE,
}


@dataclass
class TrajectoryFailureRecord:
    """Structured record of a failure occurring during trajectory execution."""

    failure_kind: TrajectoryFailureKind
    message: str
    tool: str | None = None
    step: int = 0
    is_addressable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.is_addressable = self.failure_kind in VEYRA_ADDRESSABLE_FAILURES

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_kind": self.failure_kind.value,
            "message": self.message,
            "tool": self.tool,
            "step": self.step,
            "is_addressable": self.is_addressable,
            "details": self.details,
        }


def classify_trajectory_failure(
    error: Exception | str,
    context: dict[str, Any] | None = None,
) -> TrajectoryFailureRecord:
    """Classify an execution error or failure event into the formal 15-class taxonomy."""
    context = context or {}
    msg = str(error).strip()
    msg_lower = msg.lower()

    step = context.get("step", 0)
    tool = context.get("tool")

    # 1. Tenant mismatch
    if "tenant" in msg_lower or "isolation" in msg_lower:
        return TrajectoryFailureRecord(TrajectoryFailureKind.TENANT_FAILURE, msg, tool, step)

    # 2. Authorization
    if any(k in msg_lower for k in ("unauthorized", "permission denied", "forbidden", "403", "rbac")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.AUTHORIZATION_FAILURE, msg, tool, step)

    # 3. UNKNOWN_ACK (committed but lost ack / timeout during mutation)
    if any(k in msg_lower for k in ("unknown_ack", "lost ack", "unacknowledged mutation", "commit_lost")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.UNKNOWN_ACK, msg, tool, step)

    # 4. Partial Mutation
    if any(k in msg_lower for k in ("partial_mutation", "half committed", "partial commit", "split-brain")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.PARTIAL_MUTATION, msg, tool, step)

    # 5. Rate limit
    if any(k in msg_lower for k in ("429", "rate limit", "too many requests", "throttled")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.RATE_LIMIT, msg, tool, step)

    # 6. Network failure & Gateway/Server errors (500, 502, 503, 504)
    if any(k in msg_lower for k in ("timeout", "connection reset", "econnrefused", "network", "socket", "500", "502", "503", "504", "gateway", "server error")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.NETWORK_FAILURE, msg, tool, step)

    # 7. Schema / validation failure
    if any(k in msg_lower for k in ("schema", "type error", "validation error", "required argument", "invalid type")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.SCHEMA_FAILURE, msg, tool, step)

    # 8. Precondition failure (stale state, unmet required_state)
    if any(k in msg_lower for k in ("precondition", "stale", "freshness", "version mismatch", "state condition")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.PRECONDITION_FAILURE, msg, tool, step)

    # 9. Tool implementation failure (code crash in tool callable)
    if any(k in msg_lower for k in ("attributeerror", "nameerror", "zerodivisionerror", "indexerror")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.TOOL_IMPLEMENTATION_FAILURE, msg, tool, step)

    # 10. Verification failure
    if "verification" in msg_lower:
        return TrajectoryFailureRecord(TrajectoryFailureKind.VERIFICATION_FAILURE, msg, tool, step)

    # 11. Recovery failure
    if "recovery" in msg_lower or "rollback failed" in msg_lower:
        return TrajectoryFailureRecord(TrajectoryFailureKind.RECOVERY_FAILURE, msg, tool, step)

    # 12. Agent argument failure
    if any(k in msg_lower for k in ("wrong argument", "bad argument value", "invalid parameter")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.AGENT_ARGUMENT_FAILURE, msg, tool, step)

    # 13. Tool selection failure
    if any(k in msg_lower for k in ("wrong tool", "hallucinated tool", "tool not found", "no such tool")):
        return TrajectoryFailureRecord(TrajectoryFailureKind.TOOL_SELECTION_FAILURE, msg, tool, step)

    # 14. Unrecoverable semantic failure
    if "semantic" in msg_lower or "logic error" in msg_lower:
        return TrajectoryFailureRecord(TrajectoryFailureKind.UNRECOVERABLE_SEMANTIC_FAILURE, msg, tool, step)

    # Default fallback: Agent reasoning failure
    return TrajectoryFailureRecord(TrajectoryFailureKind.AGENT_REASONING_FAILURE, msg, tool, step)
