"""Soro-Boro: Provider Lifecycle States, Side Effects, and Terminal Outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class SideEffectClass(str, Enum):
    """Classification of execution side-effects."""

    READ_ONLY = "READ_ONLY"
    IDEMPOTENT_WRITE = "IDEMPOTENT_WRITE"
    NON_IDEMPOTENT_MUTATION = "NON_IDEMPOTENT_MUTATION"
    DESTRUCTIVE = "DESTRUCTIVE"


class ProviderLifecycleState(str, Enum):
    """Rich multi-stage lifecycle states from external providers (e.g. Stripe, AWS, GitHub)."""

    SUCCEEDED = "SUCCEEDED"
    PENDING = "PENDING"
    FAILED = "FAILED"
    REQUIRES_ACTION = "REQUIRES_ACTION"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"


@dataclass
class ReconciliationResult:
    """Result of an authoritative or best-effort inspection of provider state.
    
    SAFETY INVARIANT:
    authoritative MUST be False by default. A negative lookup (NOT_FOUND) only authorizes
    retrying when authoritative=True AND consistency_observed='strong' (linearizable read-after-write).
    """

    state: ProviderLifecycleState
    authoritative: bool = False  # NEVER authoritative by default
    raw_response: Any = None
    error: str | None = None
    consistency_observed: str = "eventual"  # Default to eventual replication


@dataclass
class TerminalOutcome(Generic[T]):
    """Explicit, typed terminal outcome returned to the agent runtime."""

    status: str  # "COMMITTED" | "PREVENTED_DUPLICATE" | "AMBIGUOUS_DEFERRED" | "DENIED" | "FAILED"
    data: T | None
    provider_state: ProviderLifecycleState
    operation_id: str
    idempotency_key: str
    audit_hash: str
    reason: str
    reconciliation: ReconciliationResult | None = None
    attempts: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status in ("COMMITTED", "PREVENTED_DUPLICATE")

    @property
    def is_ambiguous(self) -> bool:
        return self.status == "AMBIGUOUS_DEFERRED"
