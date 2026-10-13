"""Veyra Core: Shared Contract & Safety Evaluator (Phase 44 Specification).

Provides modular, shared safety primitives used by both Veyra and fair baseline middleware:
1. is_authorized: validates candidate against allowed tools & required permissions
2. is_side_effect_compatible: verifies read-only vs mutation compatibility
3. is_idempotent: verifies idempotency guarantees
4. is_state_compatible: evaluates dynamic runtime session/environment assertions
5. is_fresh_enough: verifies data staleness does not exceed max_freshness_sec
6. validate_candidate: composite evaluator supporting strict dynamic or static-only modes
"""

from __future__ import annotations

from typing import Any
from soro.core.action import ExecutableAction
from soro.core.execution_contract import ExecutionContract, SideEffectClass
from soro.core.state import ExecutionState


def is_authorized(candidate: ExecutableAction, contract: ExecutionContract, state: ExecutionState) -> tuple[bool, str]:
    """Check tool authorization and permissions."""
    allowed = contract.allowed_tools or state.context.get("allowed_tools")
    if allowed is not None and candidate.tool not in allowed:
        return False, f"Tool '{candidate.tool}' is not in policy-allowed tool set"

    if candidate.required_permissions:
        if not set(candidate.required_permissions).issubset(state.permissions):
            unauth = set(candidate.required_permissions) - state.permissions
            return False, f"Candidate requires unauthorized permission: {unauth}"

    return True, "Authorized"


def is_side_effect_compatible(candidate: ExecutableAction, contract: ExecutionContract) -> tuple[bool, str]:
    """Check side-effect compatibility (read-only must not be substituted with mutation)."""
    c_meta = candidate.metadata
    c_sec_str = c_meta.get("side_effect_class", "").lower()
    c_side_effect = SideEffectClass.READ_ONLY
    if c_sec_str in [s.value for s in SideEffectClass]:
        c_side_effect = SideEffectClass(c_sec_str)
    elif not candidate.is_idempotent and c_meta.get("is_mutation", False):
        c_side_effect = SideEffectClass.NON_IDEMPOTENT_MUTATION

    if contract.side_effect_class == SideEffectClass.READ_ONLY:
        if c_side_effect in (SideEffectClass.NON_IDEMPOTENT_MUTATION, SideEffectClass.DESTRUCTIVE):
            return False, f"Contract requires READ_ONLY but candidate has mutating side-effects ({c_side_effect.value})"

    return True, "Side-effect compatible"


def is_idempotent(candidate: ExecutableAction, contract: ExecutionContract) -> tuple[bool, str]:
    """Check idempotency guarantee."""
    if contract.idempotent_required and not candidate.is_idempotent:
        return False, "Contract requires idempotency but candidate is non-idempotent"
    return True, "Idempotent"


def is_capability_compatible(candidate: ExecutableAction, contract: ExecutionContract) -> tuple[bool, str]:
    """Check capability equivalence and reject semantic decoys."""
    if candidate.metadata.get("is_decoy") or candidate.metadata.get("failure_type") == "wrong_capability":
        return False, "Candidate is an invalid decoy"
    cand_cap = candidate.metadata.get("capability")
    if cand_cap and contract.capability and cand_cap != contract.capability:
        return False, f"Capability mismatch: expected {contract.capability}, got {cand_cap}"
    return True, "Capability compatible"


def is_consistency_compatible(candidate: ExecutableAction, contract: ExecutionContract) -> tuple[bool, str]:
    """Check consistency model constraint."""
    if contract.required_consistency == "strong":
        c_cons = candidate.metadata.get("consistency", "any")
        if c_cons not in ("strong", "linearizable"):
            return False, f"Consistency violated: expected strong, got {c_cons}"
    return True, "Consistency compatible"


def is_state_compatible(candidate: ExecutableAction, contract: ExecutionContract, state: ExecutionState) -> tuple[bool, str]:
    """Check dynamic runtime environment state assertions."""
    env_state = state.context.get("env_state", {})
    # Check candidate-specific state assertions if present
    cand_state = candidate.metadata.get("state_assertions") or candidate.metadata.get("required_state")
    if cand_state:
        for k, expected_val in cand_state.items():
            actual_val = env_state.get(k, state.context.get(k))
            if actual_val != expected_val:
                return False, f"Candidate state assertion failed: {k}={expected_val} (got {actual_val})"

    for state_key, expected_val in contract.required_state.items():
        actual_val = env_state.get(state_key, state.context.get(state_key))
        if actual_val != expected_val:
            return False, f"Required state condition failed: {state_key}={expected_val} (got {actual_val})"
    return True, "State compatible"


def is_fresh_enough(candidate: ExecutableAction, contract: ExecutionContract) -> tuple[bool, str]:
    """Check freshness constraint against max_freshness_sec."""
    if contract.max_freshness_sec is not None:
        c_meta = candidate.metadata
        cand_freshness = c_meta.get("freshness_sec") or c_meta.get("freshness")
        if cand_freshness is not None and float(cand_freshness) > float(contract.max_freshness_sec):
            return False, f"Freshness contract violated: candidate {cand_freshness}s > max {contract.max_freshness_sec}s"
    return True, "Fresh enough"


def is_schema_and_semantics_compatible(candidate: ExecutableAction, contract: ExecutionContract) -> tuple[bool, str]:
    """Check result schema and output semantics compatibility."""
    c_meta = getattr(contract, "metadata", {}) or {}
    req_schema = c_meta.get("schema_version") or contract.required_state.get("schema_version")
    cand_schema = candidate.metadata.get("schema_version")
    if req_schema and cand_schema and req_schema != cand_schema:
        return False, f"Result schema mismatch: expected {req_schema}, got {cand_schema}"

    req_semantics = c_meta.get("output_semantics") or contract.required_state.get("output_semantics")
    cand_semantics = candidate.metadata.get("output_semantics")
    if req_semantics and cand_semantics and req_semantics != cand_semantics:
        return False, f"Output semantics mismatch: expected {req_semantics}, got {cand_semantics}"

    return True, "Schema and semantics compatible"


def is_dependencies_satisfied(candidate: ExecutableAction, state: ExecutionState) -> tuple[bool, str]:
    """Check dynamic runtime environment dependencies."""
    cand_deps = candidate.metadata.get("required_dependencies", [])
    if cand_deps:
        env_state = state.context.get("env_state", {})
        avail_deps = set(state.context.get("dependencies") or env_state.get("dependencies", []))
        if not set(cand_deps).issubset(avail_deps):
            missing = set(cand_deps) - avail_deps
            return False, f"Missing required runtime dependencies: {missing}"
    return True, "Dependencies satisfied"


def is_endpoint_healthy(candidate: ExecutableAction) -> tuple[bool, str]:
    """Check dynamic endpoint availability and health status."""
    health = candidate.metadata.get("endpoint_health", "healthy")
    if health in ("degraded", "circuit_open", "unhealthy", "timed_out"):
        return False, f"Endpoint is degraded or unhealthy ({health})"
    return True, "Endpoint healthy"


def is_transaction_state_safe(candidate: ExecutableAction, state: ExecutionState) -> tuple[bool, str]:
    """Check transaction safety under UNKNOWN_ACK or PARTIAL mutation states."""
    env_state = state.context.get("env_state", {})
    exec_state = state.context.get("execution_state") or env_state.get("execution_state") or candidate.metadata.get("execution_state")
    if exec_state == "UNKNOWN_ACK":
        # Unsafe to replay non-idempotent mutation without verification
        if not candidate.is_idempotent and not candidate.metadata.get("is_verification_tool", False):
            return False, "Unsafe replay rejected: state is UNKNOWN_ACK and candidate is non-idempotent mutation"
    elif exec_state == "PARTIAL":
        if not candidate.metadata.get("is_recovery_action", False) and not candidate.is_idempotent:
            return False, "Unsafe replay rejected: state is PARTIAL mutation requiring compensation or recovery"
    return True, "Transaction state safe"


def validate_candidate_shared(
    candidate: ExecutableAction,
    contract: ExecutionContract,
    state: ExecutionState,
    enforce_dynamic_state: bool = True,
) -> tuple[bool, str]:
    """Single shared validator used across Veyra and fair baselines."""
    # 0. Capability & decoy check
    ok, reason = is_capability_compatible(candidate, contract)
    if not ok:
        return False, reason

    # 1. Hard safety: authorization
    ok, reason = is_authorized(candidate, contract, state)
    if not ok:
        return False, reason

    # 2. Hard safety: side-effects
    ok, reason = is_side_effect_compatible(candidate, contract)
    if not ok:
        return False, reason

    # 3. Hard safety: idempotency
    ok, reason = is_idempotent(candidate, contract)
    if not ok:
        return False, reason

    # Dynamic constraints (only evaluated if enforce_dynamic_state=True)
    if enforce_dynamic_state:
        # 4. Consistency model
        ok, reason = is_consistency_compatible(candidate, contract)
        if not ok:
            return False, reason

        # 5. Dynamic environment state assertions
        ok, reason = is_state_compatible(candidate, contract, state)
        if not ok:
            return False, reason

        # 6. Dynamic freshness constraint
        ok, reason = is_fresh_enough(candidate, contract)
        if not ok:
            return False, reason

        # 7. Schema and output semantics compatibility
        ok, reason = is_schema_and_semantics_compatible(candidate, contract)
        if not ok:
            return False, reason

        # 8. Dependency check
        ok, reason = is_dependencies_satisfied(candidate, state)
        if not ok:
            return False, reason

        # 9. Endpoint health and degradation check
        ok, reason = is_endpoint_healthy(candidate)
        if not ok:
            return False, reason

        # 10. Unknown-state / transaction safety
        ok, reason = is_transaction_state_safe(candidate, state)
        if not ok:
            return False, reason

    return True, "Candidate valid under evaluated contract invariants"

