"""Soro-Boro: Execution Boundary for Consequential AI Agent Writes.

Prevents unsafe retries of consequential agent writes and gives teams
a clear, auditable outcome when the result is uncertain.
"""

from soro_boro.boundary import SoroBoundary, TimeoutException, soro_wrap
from soro_boro.identity import OperationIdentity
from soro_boro.lifecycle import (
    ProviderLifecycleState,
    ReconciliationResult,
    SideEffectClass,
    TerminalOutcome,
)
from soro_boro.wal import WALRecord, WriteAheadLog

__version__ = "0.1.0"
__all__ = [
    "SoroBoundary",
    "TimeoutException",
    "soro_wrap",
    "OperationIdentity",
    "ProviderLifecycleState",
    "ReconciliationResult",
    "SideEffectClass",
    "TerminalOutcome",
    "WriteAheadLog",
    "WALRecord",
]
