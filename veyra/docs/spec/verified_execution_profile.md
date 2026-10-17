# Verified Execution Profile (VEP) Specification

**Specification Version:** `veyra.profile/v1alpha1`  
**Purpose:** Machine-readable verified execution semantics derived from active fault-injection testing.

---

## 1. Abstract

Developer-declared metadata (e.g. OpenAPI specs, MCP `ToolAnnotations` hints like `idempotentHint` or `readOnlyHint`) are declarations of intent, not guarantees of behavior. Under partial observability and network fault modes (lost ACKs, process disconnects, read-replica lag, delayed bank settlement), declared properties frequently fail.

A **Verified Execution Profile (VEP)** records empirically audited execution capabilities derived from black-box fault-injection experiments.

---

## 2. Core Provenance Model

Every semantic capability carries an explicit provenance status:
- **`DECLARED`**: Stated by tool author, OpenAPI manifest, or MCP annotation.
- **`OBSERVED`**: Observed during passive execution telemetry.
- **`VERIFIED`**: Proven under active, adversarial fault-injection testing by Veyra.
- **`CONTRADICTED`**: Explicitly violated during fault injection (e.g., claimed idempotent, but duplicate side effects observed).
- **`UNKNOWN`**: Untested capability.

---

## 3. Schema Structure (`yaml` / `json`)

```yaml
version: "veyra.profile/v1alpha1"
tool_name: "payments.create_charge"
audit_metadata:
  audit_id: "aud_9283f"
  tested_at: "2026-10-08T22:00:00Z"
  test_suite_version: "v0.3.0"
  total_fault_trials: 500
  conformance_status: "VERIFIED_WITH_CONDITIONS"

capabilities:
  idempotency:
    declared: true
    observed: true
    status: "VERIFIED"
    key_parameter: "idempotency_key"
    evidence:
      trials_evaluated: 100
      duplicates_detected: 0
      finite_sample_95_ucb_der: "3.00%"

  status_lookup:
    declared: true
    observed: true
    status: "VERIFIED"
    consistency_observed: "eventual"
    mean_propagation_lag_ms: 1200
    evidence:
      stale_probe_detection_rate: "100.0%"

  late_commit_tolerance:
    status: "CONTRADICTED"
    finding: "Misleading probe returns false during delayed upstream settlement; blind retry causes double charge."
    enforced_safe_recovery: "IDEMPOTENCY_REPLAY_ONLY"

autonomous_recommendation:
  grade: "Grade B"
  policy: "CONDITIONAL_AUTONOMOUS_EXECUTION"
  required_runtime_guard: "STRICT_IDEMPOTENCY_KEY_OR_ABSTAIN"
```
