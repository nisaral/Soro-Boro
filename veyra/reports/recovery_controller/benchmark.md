# Constrained Belief-State Recovery Controller — Heterogeneous Benchmark Protocol

**Benchmark Runner:** [`benchmarks/recovery_controller/runner.py`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/benchmarks/recovery_controller/runner.py)  
**Results Artifact:** [`benchmarks/recovery_controller/results.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/benchmarks/recovery_controller/results.json)  
**Directive Reference:** Veyra Algorithmic Upgrade (§7 - §12)  

---

## 1. Experimental Arms

We evaluate 6 distinct recovery arms across identical heterogeneous failure scenarios:

1. **`A0: Raw Agent`**: Autonomous agent directly observes the tool exception and attempts an unstructured LLM-driven replan.
2. **`A1: Naive Retry`**: Opaque framework retry loop that blindly replays the failed tool call.
3. **`A2: Verify-Before-Retry (B6)`**: Bespoke check: runs verification probe if present; if probe is missing, falls back to blind retry.
4. **`A3: Idempotency Keys (B2)`**: Server-side idempotency: replays with client token if supported; if unsupported, falls back to blind retry.
5. **`A4: Current Veyra (Deterministic)`**: Strict contract invariants: verifies if hook exists, otherwise safely abstains (`DEFER`/`DENY`).
6. **`A5: Belief-State Veyra (New Experimental)`**: Constrained Belief-State Controller: forms state belief, acquires non-mutating evidence, evaluates expected utility under $P(\text{unsafe}) \le 0.01$, and executes the safe recovery action.

---

## 2. Heterogeneous Scenario Suite

To prevent designing data that artificially favors one system, the suite includes scenarios where different recovery mechanisms are optimal, as well as scenarios where abstention is the only safe outcome:

| Scenario ID | Failure Class & Tool Context | Optimal System / Action |
| :--- | :--- | :--- |
| **`S1`** | **UNKNOWN_ACK with Verification Hook**: Payment mutation committed, response packet dropped. Verification probe available. | Verify-Before-Retry (B6) / Veyra |
| **`S2`** | **UNKNOWN_ACK with Idempotency Support**: Order created on database, response dropped. No verify hook, but idempotency key supported. | Idempotency Keys (B2) / New Veyra |
| **`S3`** | **Ambiguous State (No Hook, No Key)**: Legacy mutating write times out. No verification probe, no idempotency key. | **Safe Abstention (`DEFER`)** *(Abstain wins)* |
| **`S4`** | **Transient Read Glitch**: Temporary network dropped during read-only SQL query (`SELECT`). | **Simple Retry** *(All retry systems win)* |
| **`S5`** | **Partial Batch Mutation**: Half of batch committed before failure. Reconciliation probe exists. | **Reconciliation** *(Belief-State Veyra wins)* |
| **`S6`** | **Pre-Execution Timeout**: Socket connection dropped before dispatch. Read-only probe confirms zero records committed. | **Safe Retry** *(Belief-State Veyra wins)* |

---

## 3. Metrics Computed

- **Safe Recovery Rate**: Percentage of scenarios successfully recovered to correct external state without duplicate effects.
- **Duplicate Effect Rate (DER)**: Percentage of scenarios resulting in duplicate mutations (e.g., double charge, duplicate rows).
- **Unnecessary Abstention Rate**: Percentage of scenarios where the system abstained despite safe recovery being mathematically possible.
