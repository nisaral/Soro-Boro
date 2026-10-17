# Veyra Evolution: The Four Generations of Execution-Boundary Recovery

```text
Version 0: Deterministic Rules
               ↓
Version 1: Evidence-Aware Recovery
               ↓
Version 2: Belief Over Hidden Execution State
               ↓
Version 3: Risk-Constrained Action Selection
               ↓
Real Tools / LIMBO / UndoBench
```

**Date:** October 8, 2026  
**Auditor / Core Architecture Team:** Veyra Research & Engineering  
**Repository:** [github.com/nisaral/Veyra](https://github.com/nisaral/Veyra)  

---

## 1. Architectural Evolution Roadmap

| Generation | Core Mechanism | Uncertainty Handling | Primary Failure / Limitation | Benchmark Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **Version 0: Deterministic Rules** | Static contract matching, fixed retry backoff, declared fallback chains. | Zero uncertainty modeling (assumes failures are deterministic exceptions). | **The Blind Replay Hazard:** Replays non-idempotent mutations on timeouts; duplicates writes or corrupts state. | 14.0% Safe Recovery<br>36.0% Duplicate Rate |
| **Version 1: Evidence-Aware Recovery** | Post-fault verification hooks, idempotency key checks, zero-privilege abstention. | Binary evidence check: Is verification probe present? If yes $\to$ verify. If no $\to$ `DEFER`. | **The Abstention Trap:** Over-abstains on ambiguous faults even when uncertainty could be safely resolved; no formal state estimation. | 42.0% Safe Recovery<br>0.0% Duplicate Rate<br>**44.0% Unnecessary Abstention** |
| **Version 2: Belief Over Execution State** | Bayesian / discrete belief state distribution $B(s) = P(S = s \mid \mathcal{O})$ over hidden states. | Multi-hypothesis state space: `COMMITTED`, `NOT_COMMITTED`, `IN_FLIGHT`, `PARTIAL`, `DUPLICATED`, `UNKNOWN`. | **Heuristic Action Selection:** Knows what might have happened, but lacks formal risk bounds when selecting among multiple competing recovery actions. | 64.0% Safe Recovery<br>0.0% Duplicate Rate<br>22.0% Unnecessary Abstention |
| **Version 3: Risk-Constrained Action Selection** | Constrained Expected Utility Optimization: $\max \mathbb{E}[U(a)]$ subject to $P(\text{unsafe effect}) \le \epsilon$. | Closed-loop evidence acquisition: queries read-only probes before decision; enforces hard safety threshold ($\epsilon = 0.01$). | **Information Lower Bound:** Irreducible ambiguity (APIs with zero observability or keys) still forces safe `DEFER`. | **83.3% Pilot / 64.0% Scaled Recovery**<br>**0.0% Duplicate Rate**<br>**Narrows Oracle Gap to 26%** |

---

## 2. Deep Dive: Generation by Generation

### Generation 0: Deterministic Rules (The Fragile RPC Era)
- **The Core Loop:** Agent proposes tool call $\to$ Tool executes $\to$ If exception, match status code against static retry/fallback table.
- **The Failure:** On network drops or timeouts (`UNKNOWN_ACK`), deterministic middleware cannot know if the commit succeeded on the server. If the operation is a non-idempotent mutation (e.g., payment charge, database write, Git commit), blind retry causes **36% to 100% duplicate effect rates**.

### Generation 1: Evidence-Aware Recovery (The Abstention Trap)
- **The Core Loop:** `Agent proposes → Veyra validates → Tool executes → If UNKNOWN_ACK, verify probe check`.
- **The Advance:** Established the invariant: *UNKNOWN_ACK on non-idempotent mutation MUST NEVER trigger blind replay*. If a verify probe exists, run it. If missing, strictly abstain (`DEFER`/`DENY`).
- **The Realization:** While it eliminated all duplicate writes (0% DER), it created the **Abstention Trap**: in our 500-scenario evaluation, Current Veyra abstained unnecessarily in **44.0%** of recoverable tasks. It lacked the capability to reason about partial commits, pre-execution drops, or whether acquiring non-mutating evidence could make recovery safe.

### Generation 2: Belief Over Hidden Execution State (Formal Uncertainty)
- **The Core Loop:** Upon boundary failure, initialize prior belief $B_0(s)$ over hidden states:
  $$\{\text{NOT\_COMMITTED}, \text{IN\_FLIGHT}, \text{COMMITTED}, \text{PARTIAL}, \text{DUPLICATED}, \text{UNKNOWN}\}$$
- **The Advance:** Uses fault signatures (e.g., DNS drop $\to P(\text{NOT\_COMMITTED}) \ge 0.95$, HTTP 504 $\to P(\text{COMMITTED}) = 0.55, P(\text{IN\_FLIGHT}) = 0.30$) to maintain calibrated uncertainty rather than treating failure as a binary scalar.

### Generation 3: Risk-Constrained Action Selection (The Current Frontier)
- **The Core Loop:**
  ```text
  FAILURE
    ↓
  Form Prior B0(s)
    ↓
  Can safe read-only evidence probe reduce uncertainty?
   ├── YES → Execute Probe (Status/Journal/Ledger) → Update Posterior B(s)
   └── NO  → Posterior = B0(s)
    ↓
  Candidate Recovery Actions:
  {VERIFY, IDEMPOTENCY_REPLAY, RECONCILE, COMPENSATE, RETRY, FALLBACK, DEFER, DENY}
    ↓
  Constrained Optimization:
  maximize E[U(a)] subject to P(unsafe external effect) <= epsilon (0.01)
    ↓
  If no candidate satisfies P(unsafe) <= epsilon → Safe DEFER / DENY
  ```
- **The Scaled Evidence ($N=500$ across 10 random seeds):**
  - **Safe Recovery Rate:** $64.00\%$ (vs $42.00\%$ for Current Veyra and $14.00\%$ for Naive Retry).
  - **Duplicate Effect Rate:** Strict **$0.00\%$** (vs $36.00\%$ for Naive Retry, $4.00\%$ for B6, $30.00\%$ for B2).
  - **Unnecessary Abstention Rate:** Cut in half ($44.00\% \to 22.00\%$).
  - **Oracle Gap:** Narrowed to $26.00\%$ (Oracle ceiling is $90.00\%$).

---

## 3. The Target: Real Tools / LIMBO / UndoBench

The trajectory now leads directly into real-world validation against live external benchmarks and production tools:

```text
                                [Version 3 Controller]
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
             [Real Tool Lab]       [UndoBench]         [LIMBO / MCP]
             (Postgres, Git,      (Official Fault      (Complex MCP
              Filesystem, HTTP)    Boundaries)          Stateful Servers)
```

### Next Milestones:
1. **Live Tool Lab Deployment:** Wire the Version 3 Controller into our transactional Postgres, Git ref, and stdio MCP Filesystem adapters.
2. **Official UndoBench Suite:** Execute Version 3 against official UndoBench task sets to measure conditional recovery on standard benchmark splits.
3. **LIMBO / MCP State-Aware Execution:** Evaluate whether the risk-constrained controller prevents state corruption in complex, multi-turn stateful MCP workflows.
