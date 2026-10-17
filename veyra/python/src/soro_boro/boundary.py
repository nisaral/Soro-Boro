"""Soro-Boro: Execution Boundary Interceptor and @soro_wrap Decorator.

Ensures:
1. Consequential writes have stable OperationIdentity minted per workflow intent.
2. Cross-process mutual exclusion via atomic claim store (preventing parallel racing).
3. Parameter mismatch validation preventing intent drift.
4. Provider retention window expiration guard (preventing stale key re-dispatch).
5. Synchronous Write-Ahead Intent logging before tool dispatch.
6. UNKNOWN_ACK interceptor trapping timeouts and connection drops.
7. Authoritative reconciliation evaluating rich provider lifecycle states.
8. Fail-closed AMBIGUOUS_DEFERRED terminal state when state is eventual or ambiguous.
"""

from __future__ import annotations

import functools
import inspect
import uuid
from pathlib import Path
from typing import Any, Callable, TypeVar

from soro_boro.claim import ClaimStatus, ConcurrentExecutionBlocked, SQLiteClaimStore
from soro_boro.identity import MismatchedParametersError, OperationIdentity
from soro_boro.lifecycle import (
    ProviderLifecycleState,
    ReconciliationResult,
    SideEffectClass,
    TerminalOutcome,
)
from soro_boro.wal import WriteAheadLog

R = TypeVar("R")


class TimeoutException(Exception):
    """Simulated or actual connection/gateway timeout."""
    pass


class SoroBoundary:
    """The Soro-Boro Execution Boundary Controller."""

    def __init__(
        self,
        wal: WriteAheadLog | None = None,
        claim_store: SQLiteClaimStore | None = None,
    ):
        self.wal = wal or WriteAheadLog()
        self.claim_store = claim_store or SQLiteClaimStore()

    def execute_with_boundary(
        self,
        fn: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        side_effect_class: SideEffectClass = SideEffectClass.READ_ONLY,
        op_identity: OperationIdentity | None = None,
        reconciler: Callable[[OperationIdentity], ReconciliationResult] | None = None,
        max_retries: int = 1,
        max_retry_window_sec: float = 3600.0,
        lease_ttl_sec: float = 30.0,
        supports_native_idempotency: bool = False,
        dedupe_mode: str = "loop_guard",
        window_sec: float = 120.0,
    ) -> TerminalOutcome[Any]:
        tool_name = getattr(fn, "__name__", "anonymous_tool")
        bound_kwargs = dict(kwargs)

        # 1. Resolve or Mint Operation Identity
        if op_identity is None:
            if "op" in bound_kwargs and isinstance(bound_kwargs["op"], OperationIdentity):
                op_identity = bound_kwargs["op"]
            else:
                intent_id = bound_kwargs.pop("_sb_intent_id", None)
                op_identity = OperationIdentity.mint(
                    intent_id=intent_id,
                    arguments=bound_kwargs,
                    tool_name=tool_name,
                    dedupe_mode=dedupe_mode,
                    window_sec=window_sec,
                )

        # Inject operation identity if function expects it
        sig = inspect.signature(fn)
        if "op" in sig.parameters:
            bound_kwargs["op"] = op_identity

        # 2. Validate Parameters Match & Key Expiration
        op_identity.verify_arguments_match(bound_kwargs)

        if side_effect_class != SideEffectClass.READ_ONLY:
            if op_identity.is_expired(max_retry_window_sec):
                # Provider key retention window exceeded!
                wal_rec = self.wal.record_outcome(
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    tool_name=tool_name,
                    status="AMBIGUOUS_DEFERRED",
                    provider_state=ProviderLifecycleState.UNKNOWN.value,
                    reason=f"Operation expired past provider retention window ({max_retry_window_sec}s). Replay blocked.",
                )
                return TerminalOutcome(
                    status="AMBIGUOUS_DEFERRED",
                    data=None,
                    provider_state=ProviderLifecycleState.UNKNOWN,
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    audit_hash=wal_rec.record_hash,
                    reason="Operation expired past key retention window; human triage required.",
                )

        # 3. Read-Only Pass-Through
        if side_effect_class == SideEffectClass.READ_ONLY:
            try:
                res = fn(*args, **bound_kwargs)
                wal_rec = self.wal.record_outcome(
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    tool_name=tool_name,
                    status="COMMITTED",
                    provider_state=ProviderLifecycleState.SUCCEEDED.value,
                    reason="Read-only operation executed successfully",
                    data=res,
                )
                return TerminalOutcome(
                    status="COMMITTED",
                    data=res,
                    provider_state=ProviderLifecycleState.SUCCEEDED,
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    audit_hash=wal_rec.record_hash,
                    reason="Success",
                )
            except Exception as ex:
                wal_rec = self.wal.record_outcome(
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    tool_name=tool_name,
                    status="FAILED",
                    provider_state=ProviderLifecycleState.FAILED.value,
                    reason=str(ex),
                )
                return TerminalOutcome(
                    status="FAILED",
                    data=None,
                    provider_state=ProviderLifecycleState.FAILED,
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    audit_hash=wal_rec.record_hash,
                    reason=str(ex),
                )

        # 4. Atomic Concurrency Claim (Mutating Actions)
        owner_token = str(uuid.uuid4())
        acquired, claim_state, cached_result = self.claim_store.acquire_claim(
            operation_id=op_identity.operation_id,
            idempotency_key=op_identity.idempotency_key,
            owner_token=owner_token,
            lease_ttl_sec=lease_ttl_sec,
            window_sec=window_sec,
        )

        if not acquired and claim_state == ClaimStatus.COMMITTED.value:
            # Operation was already committed by another worker! Return cached duplicate prevention.
            wal_rec = self.wal.record_outcome(
                operation_id=op_identity.operation_id,
                idempotency_key=op_identity.idempotency_key,
                tool_name=tool_name,
                status="PREVENTED_DUPLICATE",
                provider_state=ProviderLifecycleState.SUCCEEDED.value,
                reason="Atomic claim store confirmed operation was already committed. Replay suppressed.",
                data=cached_result,
            )
            return TerminalOutcome(
                status="PREVENTED_DUPLICATE",
                data=cached_result,
                provider_state=ProviderLifecycleState.SUCCEEDED,
                operation_id=op_identity.operation_id,
                idempotency_key=op_identity.idempotency_key,
                audit_hash=wal_rec.record_hash,
                reason="Operation already committed in atomic claim store; duplicate execution prevented.",
            )

        # 5. Synchronous Write-Ahead Intent (Durability Guarantee)
        wal_intent = self.wal.record_intent(
            operation_id=op_identity.operation_id,
            idempotency_key=op_identity.idempotency_key,
            tool_name=tool_name,
            arguments=bound_kwargs,
            metadata={
                "side_effect_class": side_effect_class.value,
                "args_hash": op_identity.args_hash,
                "owner_token": owner_token,
            },
        )

        # 6. Execution Loop
        attempt = 1
        last_error = None

        while attempt <= (max_retries + 1):
            try:
                result = fn(*args, **bound_kwargs)
                self.claim_store.release_claim(
                    operation_id=op_identity.operation_id,
                    owner_token=owner_token,
                    status=ClaimStatus.COMMITTED,
                    result_data=result,
                )
                wal_rec = self.wal.record_outcome(
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    tool_name=tool_name,
                    status="COMMITTED",
                    provider_state=ProviderLifecycleState.SUCCEEDED.value,
                    reason="Mutating write committed successfully",
                    data=result,
                    attempts=attempt,
                )
                return TerminalOutcome(
                    status="COMMITTED",
                    data=result,
                    provider_state=ProviderLifecycleState.SUCCEEDED,
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    audit_hash=wal_rec.record_hash,
                    reason="Mutating write committed successfully",
                    attempts=attempt,
                )
            except (TimeoutException, TimeoutError) as ex:
                last_error = ex
                # Timeout occurred -> UNKNOWN_ACK!
                # Do NOT blind retry! Enter Reconciliation Path.
                if reconciler is not None:
                    recon = reconciler(op_identity)

                    # Case A: Provider already committed the mutation!
                    if recon.state in (ProviderLifecycleState.SUCCEEDED, ProviderLifecycleState.PENDING):
                        self.claim_store.release_claim(
                            operation_id=op_identity.operation_id,
                            owner_token=owner_token,
                            status=ClaimStatus.COMMITTED,
                            result_data=recon.raw_response,
                        )
                        wal_rec = self.wal.record_outcome(
                            operation_id=op_identity.operation_id,
                            idempotency_key=op_identity.idempotency_key,
                            tool_name=tool_name,
                            status="PREVENTED_DUPLICATE",
                            provider_state=recon.state.value,
                            reason="Reconciliation proved action already committed on remote provider; duplicate retry suppressed",
                            data=recon.raw_response,
                            attempts=attempt,
                        )
                        return TerminalOutcome(
                            status="PREVENTED_DUPLICATE",
                            data=recon.raw_response,
                            provider_state=recon.state,
                            operation_id=op_identity.operation_id,
                            idempotency_key=op_identity.idempotency_key,
                            audit_hash=wal_rec.record_hash,
                            reason="Action already committed upstream; duplicate retry suppressed",
                            reconciliation=recon,
                            attempts=attempt,
                        )

                    # Case B: Provider says NOT_FOUND
                    if recon.state == ProviderLifecycleState.NOT_FOUND:
                        # CRITICAL DISTRIBUTED SYSTEMS SAFETY CHECK:
                        # Only retry if probe is explicitly authoritative AND consistency is strong
                        if not recon.authoritative or recon.consistency_observed != "strong":
                            self.claim_store.release_claim(
                                operation_id=op_identity.operation_id,
                                owner_token=owner_token,
                                status=ClaimStatus.DEFERRED,
                            )
                            wal_rec = self.wal.record_outcome(
                                operation_id=op_identity.operation_id,
                                idempotency_key=op_identity.idempotency_key,
                                tool_name=tool_name,
                                status="AMBIGUOUS_DEFERRED",
                                provider_state=recon.state.value,
                                reason="Reconciliation observed NOT_FOUND on non-authoritative/eventual replica; cannot prove uncommitted. Safe deferral enforced.",
                                attempts=attempt,
                            )
                            return TerminalOutcome(
                                status="AMBIGUOUS_DEFERRED",
                                data=None,
                                provider_state=ProviderLifecycleState.UNKNOWN,
                                operation_id=op_identity.operation_id,
                                idempotency_key=op_identity.idempotency_key,
                                audit_hash=wal_rec.record_hash,
                                reason="Reconciliation probe on eventual consistency cannot rule out in-flight commit; halted safely",
                                reconciliation=recon,
                                attempts=attempt,
                            )

                        # Reconciler is authoritative and linearizable -> Safe to retry with SAME KEY!
                        if attempt < (max_retries + 1):
                            attempt += 1
                            continue

                    # Case C: Reconciler itself failed or returned UNKNOWN
                    self.claim_store.release_claim(
                        operation_id=op_identity.operation_id,
                        owner_token=owner_token,
                        status=ClaimStatus.DEFERRED,
                    )
                    wal_rec = self.wal.record_outcome(
                        operation_id=op_identity.operation_id,
                        idempotency_key=op_identity.idempotency_key,
                        tool_name=tool_name,
                        status="AMBIGUOUS_DEFERRED",
                        provider_state=ProviderLifecycleState.UNKNOWN.value,
                        reason=f"Reconciliation inconclusive or failed ({recon.error}); fail-closed to prevent duplicate write",
                        attempts=attempt,
                    )
                    return TerminalOutcome(
                        status="AMBIGUOUS_DEFERRED",
                        data=None,
                        provider_state=ProviderLifecycleState.UNKNOWN,
                        operation_id=op_identity.operation_id,
                        idempotency_key=op_identity.idempotency_key,
                        audit_hash=wal_rec.record_hash,
                        reason="Reconciliation inconclusive; halted safely as AMBIGUOUS_DEFERRED",
                        reconciliation=recon,
                        attempts=attempt,
                    )

                # No reconciler provided:
                if supports_native_idempotency and attempt < (max_retries + 1):
                    # Provider natively deduplicates via stable idempotency key
                    attempt += 1
                    continue

                # Without reconciler or native deduplication, halt safely!
                self.claim_store.release_claim(
                    operation_id=op_identity.operation_id,
                    owner_token=owner_token,
                    status=ClaimStatus.DEFERRED,
                )
                wal_rec = self.wal.record_outcome(
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    tool_name=tool_name,
                    status="AMBIGUOUS_DEFERRED",
                    provider_state=ProviderLifecycleState.UNKNOWN.value,
                    reason=f"Timeout on consequential write without authoritative reconciler: {ex}",
                    attempts=attempt,
                )
                return TerminalOutcome(
                    status="AMBIGUOUS_DEFERRED",
                    data=None,
                    provider_state=ProviderLifecycleState.UNKNOWN,
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    audit_hash=wal_rec.record_hash,
                    reason="Timeout on consequential write without authoritative reconciler; halted safely",
                    attempts=attempt,
                )

            except Exception as ex:
                self.claim_store.release_claim(
                    operation_id=op_identity.operation_id,
                    owner_token=owner_token,
                    status=ClaimStatus.FAILED,
                )
                wal_rec = self.wal.record_outcome(
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    tool_name=tool_name,
                    status="FAILED",
                    provider_state=ProviderLifecycleState.FAILED.value,
                    reason=str(ex),
                    attempts=attempt,
                )
                return TerminalOutcome(
                    status="FAILED",
                    data=None,
                    provider_state=ProviderLifecycleState.FAILED,
                    operation_id=op_identity.operation_id,
                    idempotency_key=op_identity.idempotency_key,
                    audit_hash=wal_rec.record_hash,
                    reason=str(ex),
                    attempts=attempt,
                )

        # Exhausted retries
        self.claim_store.release_claim(
            operation_id=op_identity.operation_id,
            owner_token=owner_token,
            status=ClaimStatus.DEFERRED,
        )
        wal_rec = self.wal.record_outcome(
            operation_id=op_identity.operation_id,
            idempotency_key=op_identity.idempotency_key,
            tool_name=tool_name,
            status="AMBIGUOUS_DEFERRED",
            provider_state=ProviderLifecycleState.UNKNOWN.value,
            reason=f"Exhausted retries ({max_retries}) without confirmation",
            attempts=attempt,
        )
        return TerminalOutcome(
            status="AMBIGUOUS_DEFERRED",
            data=None,
            provider_state=ProviderLifecycleState.UNKNOWN,
            operation_id=op_identity.operation_id,
            idempotency_key=op_identity.idempotency_key,
            audit_hash=wal_rec.record_hash,
            reason="Exhausted retries without confirmation",
            attempts=attempt,
        )


def soro_wrap(
    side_effect_class: SideEffectClass = SideEffectClass.NON_IDEMPOTENT_MUTATION,
    reconciler: Callable[[OperationIdentity], ReconciliationResult] | None = None,
    max_retries: int = 1,
    max_retry_window_sec: float = 3600.0,
    lease_ttl_sec: float = 30.0,
    supports_native_idempotency: bool = False,
    dedupe_mode: str = "loop_guard",
    window_sec: float = 120.0,
    wal_path: str | Path | None = None,
    claims_db_path: str | Path | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., TerminalOutcome[Any]]]:
    """Decorator wrapping any agent tool with Soro-Boro execution boundary protection."""
    wal = WriteAheadLog(wal_path)
    claim_store = SQLiteClaimStore(claims_db_path)
    boundary = SoroBoundary(wal=wal, claim_store=claim_store)

    def decorator(fn: Callable[..., Any]) -> Callable[..., TerminalOutcome[Any]]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> TerminalOutcome[Any]:
            return boundary.execute_with_boundary(
                fn=fn,
                args=args,
                kwargs=kwargs,
                side_effect_class=side_effect_class,
                reconciler=reconciler,
                max_retries=max_retries,
                max_retry_window_sec=max_retry_window_sec,
                lease_ttl_sec=lease_ttl_sec,
                supports_native_idempotency=supports_native_idempotency,
                dedupe_mode=dedupe_mode,
                window_sec=window_sec,
            )

        return wrapper

    return decorator
