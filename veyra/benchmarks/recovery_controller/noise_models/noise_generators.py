"""Comprehensive Observation Noise Matrix Generator (Phase 2).

Implements 12 distinct realistic fault and observation noise generators:
 1. False-negative probe (probe says NOT_COMMITTED, reality is COMMITTED)
 2. False-positive probe (probe says COMMITTED, reality is NOT_COMMITTED)
 3. Stale read replica (probe reflects older snapshot, not latest commit)
 4. Probe delay / lag (probe takes 5000ms+ or times out)
 5. Missing probes (endpoint lacks read-back capability)
 6. Contradictory evidence (probe A says True, status endpoint says Pending)
 7. Correlated probe errors (shared stale cache)
 8. Delayed/late commit (commit occurs after caller timeout)
 9. Transport redelivery (request duplicated at network layer)
10. Process crash after dispatch (crash before response serialized)
11. Partial batch commit (subset of items mutated)
12. Unknown in-flight duration (unbounded execution window)
"""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass
from typing import Any, Callable

from benchmarks.recovery_controller.scenarios.schema import (
    EvidenceType,
    FailureMode,
    IdempotencyMode,
    OperationType,
    Scenario,
    TrueExecutionState,
)


class NoiseMode(str, enum.Enum):
    CLEAN = "CLEAN"
    FALSE_NEGATIVE_PROBE = "FALSE_NEGATIVE_PROBE"
    FALSE_POSITIVE_PROBE = "FALSE_POSITIVE_PROBE"
    STALE_READ_REPLICA = "STALE_READ_REPLICA"
    PROBE_DELAY = "PROBE_DELAY"
    MISSING_PROBE = "MISSING_PROBE"
    CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
    CORRELATED_PROBE_ERROR = "CORRELATED_PROBE_ERROR"
    LATE_COMMIT = "LATE_COMMIT"
    TRANSPORT_REDELIVERY = "TRANSPORT_REDELIVERY"
    PROCESS_CRASH_POST_DISPATCH = "PROCESS_CRASH_POST_DISPATCH"
    PARTIAL_BATCH_COMMIT = "PARTIAL_BATCH_COMMIT"
    UNBOUNDED_IN_FLIGHT = "UNBOUNDED_IN_FLIGHT"


def generate_noisy_scenario_suite(
    n: int = 100,
    seed: int = 42,
    noise_mode: NoiseMode = NoiseMode.CLEAN,
    probe_reliability: float = 1.0,
) -> list[Scenario]:
    """Generates an evaluation suite parameterized by a specific realistic noise model."""
    from benchmarks.recovery_controller.scenarios.generators import generate_scenario_suite
    from dataclasses import asdict

    # Start from canonical diverse scenario suite
    base_scenarios = generate_scenario_suite(n=n, seed=seed, probe_reliability=probe_reliability)
    rng = random.Random(seed)
    noisy_scenarios: list[Scenario] = []

    for sc in base_scenarios:
        sc_dict = asdict(sc)
        orig_true = sc.true_execution_state
        has_probe = sc.verification_available

        if noise_mode == NoiseMode.CLEAN:
            # Baseline behavior
            noisy_scenarios.append(sc)
            continue

        elif noise_mode == NoiseMode.FALSE_NEGATIVE_PROBE:
            # When committed, probe falsely returns False
            if orig_true == TrueExecutionState.COMMITTED and has_probe:
                sc_dict["verification_fn"] = lambda **kw: {"committed": False, "count": 0, "status": "NOT_FOUND"}

        elif noise_mode == NoiseMode.FALSE_POSITIVE_PROBE:
            # When not committed, probe falsely returns True
            if orig_true == TrueExecutionState.NOT_COMMITTED and has_probe:
                sc_dict["verification_fn"] = lambda **kw: {"committed": True, "count": 1, "status": "VERIFIED"}

        elif noise_mode == NoiseMode.STALE_READ_REPLICA:
            # Replica lag: returns False 85% of time on committed mutations
            if orig_true == TrueExecutionState.COMMITTED and has_probe:
                def make_stale(rng_ref: random.Random):
                    def stale_fn(**kw: Any) -> dict[str, Any]:
                        is_fresh = rng_ref.random() < 0.15
                        return {"committed": is_fresh, "count": 1 if is_fresh else 0, "replica_lag_ms": 1500}
                    return stale_fn
                sc_dict["verification_fn"] = make_stale(rng)

        elif noise_mode == NoiseMode.PROBE_DELAY:
            # Probe timeout / network loss
            if has_probe:
                def delay_fn(**kw: Any) -> dict[str, Any]:
                    raise TimeoutError("Evidence probe socket timed out")
                sc_dict["verification_fn"] = delay_fn

        elif noise_mode == NoiseMode.MISSING_PROBE:
            sc_dict["verification_available"] = False
            sc_dict["verification_fn"] = None

        elif noise_mode == NoiseMode.CONTRADICTORY_EVIDENCE:
            if orig_true == TrueExecutionState.COMMITTED and has_probe:
                sc_dict["verification_fn"] = lambda **kw: {"committed": True, "status": "PENDING_VERIFICATION", "ambiguous": True}

        elif noise_mode == NoiseMode.CORRELATED_PROBE_ERROR:
            # Shared cache failure
            if orig_true == TrueExecutionState.COMMITTED and has_probe:
                sc_dict["verification_fn"] = lambda **kw: {"committed": False, "cached_result": True}

        elif noise_mode == NoiseMode.LATE_COMMIT:
            # Transaction commits late; probe sees pre-commit state
            if orig_true == TrueExecutionState.COMMITTED and has_probe:
                sc_dict["verification_fn"] = lambda **kw: {"committed": False, "late_commit": True}

        elif noise_mode == NoiseMode.TRANSPORT_REDELIVERY:
            if orig_true == TrueExecutionState.COMMITTED:
                sc_dict["true_execution_state"] = TrueExecutionState.DUPLICATED
                sc_dict["verification_fn"] = lambda **kw: {"committed": True, "count": 2, "status": "DUPLICATED"}

        elif noise_mode == NoiseMode.PROCESS_CRASH_POST_DISPATCH:
            if not sc.is_mutation:
                pass
            else:
                sc_dict["true_execution_state"] = TrueExecutionState.COMMITTED
                sc_dict["failure_mode"] = FailureMode.PROCESS_CRASH
                sc_dict["verification_available"] = False
                sc_dict["verification_fn"] = None

        elif noise_mode == NoiseMode.PARTIAL_BATCH_COMMIT:
            if sc.operation_type == OperationType.BATCH_MUTATION:
                sc_dict["true_execution_state"] = TrueExecutionState.PARTIAL
                sc_dict["verification_fn"] = lambda **kw: {"committed": False, "partial": True}

        elif noise_mode == NoiseMode.UNBOUNDED_IN_FLIGHT:
            if sc.failure_mode == FailureMode.TIMEOUT:
                sc_dict["true_execution_state"] = TrueExecutionState.IN_FLIGHT
                sc_dict["verification_fn"] = lambda **kw: {"committed": False, "in_flight": True}

        noisy_sc = Scenario(**sc_dict)
        noisy_scenarios.append(noisy_sc)

    return noisy_scenarios
