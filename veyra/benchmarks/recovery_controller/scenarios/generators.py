"""Deterministic Scenario Generator for Heterogeneous Recovery Evaluation (Phase 2 & Phase 3).

Generates scaled suites of deterministic scenarios spanning:
  - 6 Domains (Database, Filesystem, HTTP/API, Payments, Object Storage, Batch Processing)
  - 6 Hidden Execution States (COMMITTED, NOT_COMMITTED, IN_FLIGHT, PARTIAL, UNKNOWN, DUPLICATED)
  - 10 Failure Modes
  - 6 Evidence Types & Reliability Levels
  - Idempotency Modes & Reconciliation Hooks
"""

from __future__ import annotations

import random
from typing import Any

from benchmarks.recovery_controller.scenarios.schema import (
    EvidenceType,
    FailureMode,
    IdempotencyMode,
    OperationType,
    Scenario,
    TrueExecutionState,
)

DOMAINS = ["Payments", "Database", "Filesystem", "HTTP_API", "ObjectStorage", "BatchProcessing"]

FAILURE_MODES = [
    FailureMode.TIMEOUT,
    FailureMode.CONNECTION_RESET,
    FailureMode.DNS_FAILURE,
    FailureMode.HTTP_5XX,
    FailureMode.RESPONSE_LOST,
    FailureMode.PROCESS_CRASH,
    FailureMode.TOOL_EXCEPTION,
    FailureMode.PARTIAL_RESPONSE,
    FailureMode.SERIALIZATION_FAILURE,
    FailureMode.CLIENT_DISCONNECT,
]


def generate_scenario_suite(n: int = 100, seed: int = 42, probe_reliability: float = 1.0) -> list[Scenario]:
    """Generates n paired scenarios with controlled diversity."""
    rng = random.Random(seed)
    scenarios: list[Scenario] = []

    for i in range(n):
        sid = f"sc_{i:04d}"
        domain = DOMAINS[i % len(DOMAINS)]
        op_idx = i % 8
        
        # Operation type & mutation flag
        if op_idx == 0:
            op_type = OperationType.READ
            is_mutation = False
        elif op_idx == 1:
            op_type = OperationType.CREATE
            is_mutation = True
        elif op_idx == 2:
            op_type = OperationType.UPDATE
            is_mutation = True
        elif op_idx == 3:
            op_type = OperationType.DELETE
            is_mutation = True
        elif op_idx == 4:
            op_type = OperationType.PAYMENT
            is_mutation = True
        elif op_idx == 5:
            op_type = OperationType.DATABASE_WRITE
            is_mutation = True
        elif op_idx == 6:
            op_type = OperationType.FILE_WRITE
            is_mutation = True
        else:
            op_type = OperationType.BATCH_MUTATION
            is_mutation = True

        fail_mode = FAILURE_MODES[i % len(FAILURE_MODES)]

        # Determine ground truth execution state
        if not is_mutation:
            true_state = TrueExecutionState.NOT_COMMITTED
        elif fail_mode in (FailureMode.DNS_FAILURE, FailureMode.CLIENT_DISCONNECT):
            true_state = TrueExecutionState.NOT_COMMITTED
        elif fail_mode in (FailureMode.RESPONSE_LOST, FailureMode.TIMEOUT, FailureMode.HTTP_5XX):
            true_state = TrueExecutionState.COMMITTED if (i % 3 != 0) else TrueExecutionState.NOT_COMMITTED
        elif op_type == OperationType.BATCH_MUTATION and fail_mode == FailureMode.PARTIAL_RESPONSE:
            true_state = TrueExecutionState.PARTIAL
        else:
            true_state = TrueExecutionState.COMMITTED if (i % 2 == 0) else TrueExecutionState.NOT_COMMITTED

        # Evidence Availability (Probe exists in ~60% of cases)
        has_probe = (i % 5 != 0)  # 80% have probe
        ev_type = EvidenceType.STATUS_PROBE if has_probe else EvidenceType.NONE

        # Idempotency Availability (Supported in ~40% of cases)
        has_idemp = is_mutation and (i % 3 == 0)
        idemp_mode = IdempotencyMode.SUPPORTED if has_idemp else IdempotencyMode.NONE
        idemp_key = f"idemp_{sid}_{seed}" if has_idemp else None

        # Reconciliation (Available for batch mutations)
        has_reconcile = (op_type == OperationType.BATCH_MUTATION)
        has_compensation = is_mutation and (i % 4 == 0)

        # Simulation tool & probe closures with controlled reliability
        entity_id = f"ent_{sid}"
        committed_val = (true_state in (TrueExecutionState.COMMITTED, TrueExecutionState.PARTIAL))

        def make_probe(committed: bool, rel: float):
            def probe_fn(**kwargs: Any) -> dict[str, Any]:
                # Controlled probe reliability
                is_correct = rng.random() <= rel
                report_committed = committed if is_correct else (not committed)
                return {"committed": report_committed, "count": 1 if report_committed else 0, "status": "VERIFIED"}
            return probe_fn

        v_fn = make_probe(committed_val, probe_reliability) if has_probe else None
        r_fn = (lambda **kw: {"status": "RECONCILED", "recovered": True}) if has_reconcile else None
        c_fn = (lambda **kw: {"status": "COMPENSATED", "recovered": True}) if has_compensation else None

        # Determine expected optimal safe action (Oracle baseline)
        if not is_mutation:
            expected_safe = "RETRY"
        elif true_state == TrueExecutionState.COMMITTED:
            if has_probe:
                expected_safe = "VERIFY"
            elif has_idemp:
                expected_safe = "IDEMPOTENCY_REPLAY"
            else:
                expected_safe = "DEFER"  # Cannot safely replay without probe/key!
        elif true_state == TrueExecutionState.NOT_COMMITTED:
            if has_probe or fail_mode in (FailureMode.DNS_FAILURE, FailureMode.CLIENT_DISCONNECT):
                expected_safe = "RETRY"
            elif has_idemp:
                expected_safe = "IDEMPOTENCY_REPLAY"
            else:
                expected_safe = "DEFER"
        elif true_state == TrueExecutionState.PARTIAL:
            if has_reconcile:
                expected_safe = "RECONCILE"
            elif has_compensation:
                expected_safe = "COMPENSATE"
            else:
                expected_safe = "DEFER"
        else:
            expected_safe = "DEFER"

        scenario = Scenario(
            scenario_id=sid,
            domain=domain,
            operation_type=op_type,
            is_mutation=is_mutation,
            true_execution_state=true_state,
            failure_mode=fail_mode,
            tool_name=f"{domain.lower()}_{op_type.value.lower()}",
            arguments={"id": entity_id, "payload": "sample_data"},
            evidence_type=ev_type,
            verification_available=has_probe,
            verification_reliability=probe_reliability,
            verification_fn=v_fn,
            idempotency_mode=idemp_mode,
            idempotency_key=idemp_key,
            reconciliation_available=has_reconcile,
            reconciliation_fn=r_fn,
            compensation_available=has_compensation,
            compensation_fn=c_fn,
            expected_safe_action=expected_safe,
        )
        scenarios.append(scenario)

    return scenarios
