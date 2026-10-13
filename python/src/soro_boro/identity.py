"""Soro-Boro: Durable Operation Identity and Intent Minting.

Invariants:
1. Operation Identity is minted ONCE per logical workflow intent (derived from the agent's
   workflow position / step trace, NOT solely from hashing the argument tokens).
2. The same logical intent MUST retain the same operation_id and idempotency_key across retries.
3. Arguments hash is stored to detect parameter drift / tampering (reusing the same operation
   with different parameters is an error, matching Stripe's exact idempotency specification).
4. Created_at timestamp is tracked to enforce provider retention windows.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


class MismatchedParametersError(ValueError):
    """Raised when an operation ID is reused with different arguments (intent drift)."""
    pass


@dataclass(frozen=True)
class OperationIdentity:
    """Durable identity for a consequential operation."""

    operation_id: str
    idempotency_key: str
    args_hash: str
    created_at: float
    scope: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)
    arguments: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def mint(
        cls,
        intent_id: str,
        arguments: dict[str, Any],
        scope: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> OperationIdentity:
        """Mint a fresh OperationIdentity bound to a logical workflow intent.
        
        Args:
            intent_id: Unique logical intent from workflow (e.g. 'wf_run_981_step_4').
            arguments: The arguments for the action.
            scope: Tenant or namespace scope.
            metadata: Custom metadata.
        """
        args_hash = cls.compute_args_hash(arguments)
        h = hashlib.sha256(f"{scope}:{intent_id}".encode()).hexdigest()[:24]
        idemp_key = f"sb_key_{h}"
        clean_args = {k: v for k, v in arguments.items() if k != "op" and not k.startswith("_sb_")}
        return cls(
            operation_id=intent_id,
            idempotency_key=idemp_key,
            args_hash=args_hash,
            created_at=time.time(),
            scope=scope,
            metadata=metadata or {},
            arguments=clean_args,
        )

    @classmethod
    def create(
        cls,
        operation_id: str,
        arguments: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        scope: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> OperationIdentity:
        """Create or bind an OperationIdentity with explicit ID and arguments."""
        args = arguments or {}
        args_hash = cls.compute_args_hash(args)
        if not idempotency_key:
            h = hashlib.sha256(f"{scope}:{operation_id}".encode()).hexdigest()[:24]
            idempotency_key = f"sb_key_{h}"
        clean_args = {k: v for k, v in args.items() if k != "op" and not k.startswith("_sb_")}
        return cls(
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            args_hash=args_hash,
            created_at=time.time(),
            scope=scope,
            metadata=metadata or {},
            arguments=clean_args,
        )

    @staticmethod
    def compute_args_hash(arguments: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash of arguments."""
        # Exclude 'op' or private framework keys from hash
        clean = {k: v for k, v in arguments.items() if k != "op" and not k.startswith("_sb_")}
        serialized = json.dumps(clean, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def verify_arguments_match(self, current_arguments: dict[str, Any]) -> None:
        """Verify that current call matches the originally minted arguments."""
        current_hash = self.compute_args_hash(current_arguments)
        if self.args_hash and self.args_hash != current_hash:
            raise MismatchedParametersError(
                f"Idempotency parameter mismatch: Operation '{self.operation_id}' was previously minted "
                f"with args_hash={self.args_hash}, but current call has args_hash={current_hash}. "
                f"Reusing an operation ID with modified parameters is strictly prohibited."
            )

    def is_expired(self, max_retention_window_sec: float) -> bool:
        """Check if the operation exceeds the provider's key retention window."""
        return (time.time() - self.created_at) > max_retention_window_sec
