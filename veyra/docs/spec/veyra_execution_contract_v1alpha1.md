# Veyra Execution Contract Specification (VEC)

**Specification Version:** `veyra.spec/v1alpha1`  
**Status:** Open Standard / Specification Draft  
**Target:** Tool-Using AI Agents, MCP Tool Providers, OpenAPI Gateways

---

## 1. Abstract

AI agents interacting with external APIs suffer from execution ambiguity: network timeouts, process disconnects, and dropped ACKs leave the agent unable to determine whether a mutation committed. When APIs lack explicit execution contracts, agents fall back to naive retries that trigger catastrophic duplicate mutations (e.g. duplicate payments, duplicate git commits, duplicate database insertions).

The **Veyra Execution Contract (VEC)** provides a standardized, machine-readable declaration of an operation's execution semantics, recovery hooks, and consistency boundaries.

---

## 2. Core Schema (`yaml`)

```yaml
version: "veyra.spec/v1alpha1"
operation: <string>               # Fully qualified operation name (e.g., "stripe.charges.create")
description: <string>           # Human-readable intent
side_effect_class: <enum>        # [read_only | idempotent_write | non_idempotent_mutation | destructive]
reversibility: <enum>            # [reversible | compensatable | irreversible]

idempotency:
  supported: <bool>              # Whether the server deduplicates via unique key
  key_parameter: <string>        # Field name where idempotency key is passed
  scope: <enum>                  # [payload_hash | client_key | session_id]
  retention_seconds: <int>       # How long the server remembers the key (e.g., 86400)

evidence_probes:
  status_lookup:
    supported: <bool>            # Whether a dedicated status lookup API exists
    tool: <string>               # Tool name to query status (e.g., "stripe.charges.get")
    parameter_mapping:
      <target_arg>: <source_arg> # Argument projection
  read_back_consistency: <enum>  # [strong | eventual | read_after_write | none]
  expected_propagation_lag_ms: <int> # Typical replica replication lag

compensation:
  supported: <bool>              # Whether a dedicated undo/rollback tool exists
  tool: <string>                 # Tool name to compensate (e.g., "stripe.refunds.create")
  parameter_mapping:
    <target_arg>: <source_arg>

reconciliation:
  supported: <bool>              # For batch or stream operations, whether reconcile hook exists
  tool: <string>
  parameter_mapping:
    <target_arg>: <source_arg>

execution_bounds:
  max_in_flight_timeout_ms: <int> # Maximum duration server will spend processing
  safe_recovery_policy: <enum>   # [strict_risk_bounded | probe_required | idempotent_only]
  max_acceptable_duplicate_risk: <float> # e.g., 0.00 or 0.01
```

---

## 3. The Contract Capability Model

Given a `VeyraExecutionContract`, Veyra computes the **Permissible Recovery Action Space**:

| Contract Guarantees Present | Permissible Recovery Actions | Prohibited Recovery Actions |
| :--- | :--- | :--- |
| `side_effect_class: read_only` | `RETRY`, `FALLBACK` | None |
| `idempotency.supported: true` | `IDEMPOTENCY_REPLAY`, `VERIFY`, `DEFER` | Blind `RETRY` without key |
| `evidence_probes.status_lookup: true` | `VERIFY`, `DEFER` | Blind `RETRY` |
| `compensation.supported: true` | `COMPENSATE`, `DEFER` | Blind `RETRY` |
| `reconciliation.supported: true` | `RECONCILE`, `DEFER` | Blind `RETRY` |
| **None of the above (Unprotected Mutation)** | `DEFER`, `DENY` | **ALL RETRIES AND REPLAYS PROHIBITED** |

---

## 4. Contract Analyzer Certification Levels

Tools audited by `veyra analyze-tool` receive an automated Certification Grade:

- **Grade A (Autonomous Execution Certified):**  
  `idempotency.supported == True` AND `evidence_probes.status_lookup == True` (Strong consistency).
- **Grade B (Conditionally Autonomous):**  
  `idempotency.supported == True` OR (`status_lookup == True` with `compensation.supported == True`).
- **Grade C (Verification-Required):**  
  No idempotency, but status lookup exists with eventual consistency.
- **Grade F (Autonomous Execution Prohibited):**  
  Non-idempotent mutation with no status lookup, no read-back, and no compensation. High risk of duplicate real-world harm.
