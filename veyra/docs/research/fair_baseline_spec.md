# Fair Baseline Specification: Recovery Paradigm Protocol

**Document Version:** 1.0 (Frozen)  
**Date:** October 8, 2026

---

## 1. Motivation

To prevent manufactured wins, all baseline arms must be implemented according to their formal definitions in literature and granted access to identical environment observations and contract capabilities where conceptually valid.

---

## 2. Specification of Frozen Arms

### Arm A: Full-Mechanism Deterministic Heuristic
- **Capabilities Granted:** Verification probes, Idempotency keys, Batch reconciliation hooks, SAGA compensation hooks.
- **Rule Hierarchy:**
  1. If operation is non-mutating (`READ_ONLY`) $\to$ `RETRY`.
  2. If verification probe available $\to$ query probe; if probe reports committed $\to$ `VERIFY`, else `RETRY`.
  3. If idempotency key supported $\to$ `IDEMPOTENCY_REPLAY`.
  4. If reconciliation hook available $\to$ `RECONCILE`.
  5. If compensation hook available $\to$ `COMPENSATE`.
  6. Else $\to$ `DEFER`.
- **Key Property:** Deterministic priority ordering without Bayesian probability updating or risk threshold gating.

### Arm B: Belief-State Veyra
- **Capabilities Granted:** Byte-for-byte identical to Arm A.
- **Decision Engine:**
  1. Computes initial prior belief $P(S_0)$ based on failure mode, latency, and status code.
  2. If probe available, executes probe and performs Bayesian posterior update:
     $$P(S \mid \text{probe}) \propto P(\text{probe} \mid S) P(S)$$
  3. Evaluates all candidate recovery actions $a \in \mathcal{A}$.
  4. Computes probability of unsafe side-effect $P(\text{unsafe} \mid a)$.
  5. Filters out all actions violating the hard risk invariant:
     $$P(\text{unsafe} \mid a) > \epsilon_{\text{unsafe}}$$
  6. Ranks surviving actions by expected utility:
     $$\text{EU}(a) = P(\text{success} \mid a) \cdot V_{\text{rec}} - P(\text{dup} \mid a) \cdot C_{\text{dup}} - \text{Cost}(a)$$
  7. If no active recovery action satisfies $P(\text{unsafe}) \le \epsilon$, safely abstains (`DEFER`).

### Arm C: Simple Probabilistic Predictor + Hard Safety Gate
- **Architecture:** Pure logistic regression trained via SGD on featurized observable vectors.
- **Features:** Mutation flag, probe presence, probe outcome, one-hot failure mode, one-hot operation type, idempotency presence.
- **Decision Rule:**
  - If $P(\text{committed}) \le \epsilon$ and not mutating $\to$ `RETRY`.
  - If idempotency key supported $\to$ `IDEMPOTENCY_REPLAY`.
  - If probe confirms committed ($P > 0.5$) $\to$ `VERIFY`.
  - Else $\to$ `DEFER`.

### Arm D: Cautious Verify-Before-Retry (UndoBench B6 Cautious)
- **Protocol:**
  - If probe present $\to$ query probe: if committed $\to$ `VERIFY`, else `RETRY`.
  - If probe missing on mutation $\to$ `DEFER` (cautious abstention).
- **Scope Limit:** Cannot use idempotency keys or reconciliation hooks.

### Arm E: Cautious Idempotency-Key Baseline (UndoBench B2 Cautious)
- **Protocol:**
  - If idempotency key supported $\to$ `IDEMPOTENCY_REPLAY`.
  - If idempotency key missing on mutation $\to$ `DEFER` (cautious abstention).
- **Scope Limit:** Cannot query verification probes or execute reconciliation hooks.

### Arm F: Environment Oracle (Reference Bound)
- **Protocol:** Direct inspection of `scenario.true_execution_state`.
- **Role:** Sets the absolute theoretical upper bound of recovery achievable under perfect information.
