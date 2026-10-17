# Constrained Belief-State Recovery Controller — Architectural Design

**Status:** EXPERIMENTAL / LAB  
**Module:** [`python/src/veyra/core/recovery_controller.py`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/python/src/veyra/core/recovery_controller.py)  
**Directive Reference:** Veyra Algorithmic Upgrade (§1 - §5)  

---

## 1. Problem Formulation: The Abstention Trap

Previous Veyra validation proved:
1. Under `UNKNOWN_ACK` when a verification probe is present, Veyra matches B6/B2 (0% DER).
2. Under ambiguous state without verification hooks or idempotency keys, Veyra enforces safe abstention (`DEFER`/`DENY`), preserving 0% DER while naive systems cause 100% duplicate writes.
3. **The Limitation:** Current Veyra maximizes safe abstention at the expense of recoverable task completion. When uncertainty is reducible via safe read-only probes, pre-condition checks, or idempotency keys, current Veyra often abstained unconditionally (unnecessary abstention rate ~50%).

**The Objective:** Maximize safe recovery, not merely maximize safe abstention:
$$\max_{\text{action} \in \mathcal{A}_{\text{safe}}} \mathbb{E}[U(\text{action})] \quad \text{subject to} \quad P(\text{unsafe external effect}) \le \epsilon$$

---

## 2. Hidden Execution States

The controller maintains a calibrated discrete probability distribution $B(s) = P(S = s \mid \mathcal{O})$ over six mutually exclusive execution states:

| State | Semantic Meaning |
| :--- | :--- |
| **`NOT_COMMITTED`** | The action never executed on the external service (e.g., DNS error, pre-dispatch socket refusal). |
| **`IN_FLIGHT`** | The action was dispatched to the network but commit status has not yet resolved. |
| **`COMMITTED`** | The action successfully persisted its mutations on the external service. |
| **`PARTIAL`** | A multi-step or batch mutation partially succeeded before an unexpected interruption. |
| **`DUPLICATED`** | The mutation has executed more than once (contract invariant violation). |
| **`UNKNOWN`** | Irreducible ambiguity prior to evidence acquisition. |

---

## 3. Safe Evidence Acquisition Loop

Rather than guessing or immediately defaulting to `DEFER`, the controller executes a non-mutating evidence acquisition stage:

```text
               [Tool Execution Failure / Timeout]
                               │
                               ▼
               [Form Initial Prior Belief B0(s)]
                               │
               Can safe read-only evidence probe
                    reduce state uncertainty?
                     ├── YES ──► [Acquire Evidence] (GET status / journal probe)
                     │                 │
                     │                 ▼
                     │          [Update Posterior B(s)]
                     └── NO ───────────┤
                                       ▼
                       [Generate Safe Candidates]
                 (VERIFY, IDEMPOTENCY_REPLAY, RECONCILE,
                  COMPENSATE, RETRY, FALLBACK, DEFER, DENY)
                                       │
                                       ▼
              [Filter Candidates: P(unsafe effect) <= epsilon]
                                       │
                                       ▼
               [Select Action Maximizing Expected Utility]
                                       │
                      If no candidate passes constraint:
                                       ▼
                               [Safe DEFER / DENY]
```

### Constraints on Evidence Probes:
- Probes must be **strictly read-only** (`SideEffectClass.READ_ONLY`).
- Probes must be bounded by explicit timeouts ($< 500\,\text{ms}$).
- Probes must not alter server state or consume mutations.

---

## 4. Constrained Expected Utility Formulation

For each candidate recovery action $a \in \mathcal{A}$:
$$\mathbb{E}[U(a)] = P(\text{success} \mid B) \cdot V_{\text{rec}} - P(\text{duplicate} \mid B) \cdot C_{\text{dup}} - C_{\text{cost}}(a)$$

Subject to:
$$P(\text{unsafe external effect} \mid B, a) \le \epsilon_{\text{unsafe}} \quad (\text{default } \epsilon = 0.01)$$

- If $a = \text{VERIFY}$: $P(\text{unsafe}) = 0.0$.
- If $a = \text{IDEMPOTENCY_REPLAY}$ with valid client key: $P(\text{unsafe}) = 0.0$.
- If $a = \text{RETRY}$ on a non-idempotent mutation:
  $$P(\text{unsafe}) = P(\text{COMMITTED}) + P(\text{IN_FLIGHT}) + P(\text{UNKNOWN})$$
  *(If this exceeds $\epsilon$, RETRY is strictly prohibited).*
- If no candidate satisfies the safety constraint, the controller outputs **`DEFER`** with a structured diagnostic explanation.
