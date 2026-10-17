"""Baseline Evaluators for Recovery Controller Benchmark (Directive §1, §9, §10).

Implements paired evaluators for:
  1. Raw Agent (LLM-style blind retry on failure)
  2. Naive Retry (Blind replay on every exception)
  3. Verify-Before-Retry (Probe hook if present, else blind retry)
  4. Idempotency Keys (Replays if idempotency key supported, else blind retry)
  5. Current Veyra (Deterministic contract verify -> abstain DEFER/DENY)
  6. Belief-State Veyra (Constrained Belief-State Controller: Evidence -> Utility -> Action)
  7. Oracle (Optimal action with perfect access to ground truth)

CRITICAL INVARIANT: Only the Oracle and Evaluator have access to scenario.true_execution_state.
Baselines 1 through 6 ONLY access scenario.get_public_action_context().
"""

from __future__ import annotations

import time
from typing import Any

from benchmarks.recovery_controller.scenarios.schema import (
    Scenario,
    TrueExecutionState,
)
from veyra.core.action import ExecutableAction
from veyra.core.execution_contract import ExecutionContract, SideEffectClass
from veyra.core.recovery_controller import (
    ConstrainedBeliefStateRecoveryController,
    RecoveryActionType,
)


def evaluate_action_outcome(
    scenario: Scenario,
    selected_action: str,
) -> tuple[bool, bool, bool]:
    """Evaluates the outcome of a selected action against the ground truth state.
    
    Returns (is_recovered, is_duplicate, is_unsafe).
    """
    true_state = scenario.true_execution_state
    is_mutation = scenario.is_mutation

    if selected_action in ("DEFER", "DENY"):
        # Safe abstention: Never causes duplicate or unsafe external effects
        return False, False, False

    if not is_mutation:
        # Read-only operation: Retry is always safe and recovers
        return True, False, False

    # Handling mutations:
    if true_state == TrueExecutionState.COMMITTED:
        if selected_action == "VERIFY":
            # Successfully observed already-committed state
            return True, False, False
        if selected_action == "IDEMPOTENCY_REPLAY":
            # Idempotency deduplicates on server -> Safe recovery
            return True, False, False
        if selected_action in ("RETRY", "BLIND_RETRY"):
            # Mutation committed + blind retry = DUPLICATE WRITE!
            return False, True, True
        if selected_action == "RECONCILE":
            return True, False, False

    elif true_state == TrueExecutionState.NOT_COMMITTED:
        if selected_action in ("RETRY", "SAFE_RETRY", "BLIND_RETRY", "IDEMPOTENCY_REPLAY"):
            # Mutation never occurred -> Replay completes the action safely
            return True, False, False
        if selected_action == "VERIFY":
            # Verified not committed, but did not replay
            return False, False, False

    elif true_state == TrueExecutionState.PARTIAL:
        if selected_action == "RECONCILE":
            # Reconciled partial batch
            return True, False, False
        if selected_action == "COMPENSATE":
            # Compensated partial state
            return True, False, False
        if selected_action in ("RETRY", "BLIND_RETRY"):
            # Replaying over partial state causes corruption / partial duplicate
            return False, True, True

    return False, False, False


# =========================================================================
# Baseline 1: Raw Agent
# =========================================================================
def run_raw_agent(scenario: Scenario) -> tuple[str, float]:
    t0 = time.perf_counter()
    # LLM typically replays the tool call after exception
    action = "BLIND_RETRY" if scenario.is_mutation else "RETRY"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat


# =========================================================================
# Baseline 2: Naive Retry
# =========================================================================
def run_naive_retry(scenario: Scenario) -> tuple[str, float]:
    t0 = time.perf_counter()
    action = "BLIND_RETRY" if scenario.is_mutation else "RETRY"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat


# =========================================================================
# =========================================================================
# Baseline 3: Verify-Before-Retry (UndoBench B6: Active Probes or Cautious Abstention)
# =========================================================================
def run_verify_before_retry(scenario: Scenario) -> tuple[str, float]:
    """Official UndoBench B6: Non-mutating active probes or cautious abstention.
    
    If probe is present: queries probe. If committed -> VERIFY; if not committed -> RETRY.
    If probe is missing on mutation: CAUTIOUS ABSTENTION (DEFER), avoiding blind duplicate risk.
    """
    t0 = time.perf_counter()
    if not scenario.is_mutation:
        action = "RETRY"
    elif scenario.verification_available and scenario.verification_fn:
        res = scenario.verification_fn(**scenario.arguments)
        if res.get("committed", False):
            action = "VERIFY"
        else:
            action = "RETRY"
    else:
        # Cautious abstention (Official UndoBench B6 specification)
        action = "DEFER"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat


def run_verify_before_retry_unconstrained(scenario: Scenario) -> tuple[str, float]:
    """Unconstrained / Aggressive B6 variant: Falls back to blind retry when probe is missing."""
    t0 = time.perf_counter()
    if not scenario.is_mutation:
        action = "RETRY"
    elif scenario.verification_available and scenario.verification_fn:
        res = scenario.verification_fn(**scenario.arguments)
        if res.get("committed", False):
            action = "VERIFY"
        else:
            action = "RETRY"
    else:
        action = "BLIND_RETRY"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat


# =========================================================================
# Baseline 4: Idempotency Keys (UndoBench B2: Scoped Key Replay or Cautious Abstention)
# =========================================================================
def run_idempotency_keys(scenario: Scenario) -> tuple[str, float]:
    """Official UndoBench B2: Key replay when supported; cautious abstention when unsupported.
    
    Cannot fairly penalize pure idempotency keys by forcing blind replays on unsupported endpoints.
    """
    t0 = time.perf_counter()
    if not scenario.is_mutation:
        action = "RETRY"
    elif scenario.idempotency_mode.value == "SUPPORTED" and scenario.idempotency_key:
        action = "IDEMPOTENCY_REPLAY"
    else:
        # Cautious abstention when endpoint does not support idempotency
        action = "DEFER"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat


def run_idempotency_keys_unconstrained(scenario: Scenario) -> tuple[str, float]:
    """Unconstrained B2 variant: Falls back to blind retry when key is unsupported."""
    t0 = time.perf_counter()
    if not scenario.is_mutation:
        action = "RETRY"
    elif scenario.idempotency_mode.value == "SUPPORTED" and scenario.idempotency_key:
        action = "IDEMPOTENCY_REPLAY"
    else:
        action = "BLIND_RETRY"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat


# =========================================================================
# Baseline 5: Current Veyra (Deterministic)
# =========================================================================
def run_current_veyra(scenario: Scenario) -> tuple[str, float]:
    t0 = time.perf_counter()
    if not scenario.is_mutation:
        action = "RETRY"
    elif scenario.verification_available and scenario.verification_fn:
        res = scenario.verification_fn(**scenario.arguments)
        if res.get("committed", False):
            action = "VERIFY"
        else:
            action = "DEFER"  # Strict invariant: no blind retry
    else:
        # No probe available on non-idempotent mutation -> Abstain DEFER
        action = "DEFER"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat


# =========================================================================
# Baseline 6: Belief-State Veyra (Experimental Controller)
# =========================================================================
def run_belief_state_veyra(
    scenario: Scenario,
    controller: ConstrainedBeliefStateRecoveryController | None = None,
) -> tuple[str, float]:
    ctrl = controller or ConstrainedBeliefStateRecoveryController(epsilon_unsafe=0.01)
    t0 = time.perf_counter()

    contract = ExecutionContract(
        capability=scenario.tool_name,
        side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION if scenario.is_mutation else SideEffectClass.READ_ONLY,
    )
    action_obj = ExecutableAction(
        tool=scenario.tool_name,
        arguments=scenario.arguments,
        metadata={"idempotent": not scenario.is_mutation},
    )

    decision = ctrl.decide_recovery(
        failed_action=action_obj,
        failure_type=scenario.failure_mode.value,
        contract=contract,
        verification_fn=scenario.verification_fn if scenario.verification_available else None,
        idempotency_key=scenario.idempotency_key,
        supports_idempotency_key=(scenario.idempotency_mode.value == "SUPPORTED"),
        reconcile_fn=scenario.reconciliation_fn if scenario.reconciliation_available else None,
        compensation_fn=scenario.compensation_fn if scenario.compensation_available else None,
    )
    lat = (time.perf_counter() - t0) * 1000.0
    return decision.action_type.value, lat



# =========================================================================
# Baseline 7: Full-Mechanism Deterministic Heuristic Controller
# =========================================================================
def run_full_mechanism_deterministic(scenario: Scenario) -> tuple[str, float]:
    """Strong deterministic heuristic baseline with access to the EXACT same mechanisms:
    idempotency keys, verification probes, reconciliation, and compensation.
    
    STRONG NON-STRAWMAN ORDERING:
      1. If non-mutation -> RETRY
      2. If idempotency key supported -> IDEMPOTENCY_REPLAY (Zero-risk deduplication)
      3. Else if verification probe available -> query probe: if True -> VERIFY, else -> DEFER (Safe abstention)
      4. Else if reconcile hook available -> RECONCILE
      5. Else if compensation hook available -> COMPENSATE
      6. Else -> DEFER
    """
    t0 = time.perf_counter()
    if not scenario.is_mutation:
        action = "RETRY"
    elif scenario.idempotency_mode.value == "SUPPORTED" and scenario.idempotency_key:
        action = "IDEMPOTENCY_REPLAY"
    elif scenario.verification_available and scenario.verification_fn:
        try:
            res = scenario.verification_fn(**scenario.arguments)
            if res.get("committed", False):
                action = "VERIFY"
            else:
                action = "DEFER"  # Strong deterministic engineer avoids blind retry
        except Exception:
            action = "DEFER"
    elif scenario.reconciliation_available and scenario.reconciliation_fn:
        action = "RECONCILE"
    elif scenario.compensation_available and scenario.compensation_fn:
        action = "COMPENSATE"
    else:
        action = "DEFER"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat


# =========================================================================
# Baseline 8: Oracle (Optimal Safe Action with Perfect Information)
# =========================================================================
def run_oracle(scenario: Scenario) -> tuple[str, float]:
    t0 = time.perf_counter()
    action = scenario.expected_safe_action or "DEFER"
    lat = (time.perf_counter() - t0) * 1000.0
    return action, lat
