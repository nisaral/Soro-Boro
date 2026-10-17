# Pre-Registration: UndoBench v1.0.1 Evaluation Protocol

**Pre-Registration Date:** October 7, 2026  
**Status:** COMMITTED BEFORE DEV/TEST EVALUATION RUNS  
**Target Benchmark:** UndoBench v1.0.1  

---

## 1. Experimental Arms

All evaluation runs compare the following 10 arms under identical tasks, models, seeds, and environments:

1. `none` (Raw Unassisted Agent)
2. `B0` (Naive Retry)
3. `B1` (Checkpoint & Rollback)
4. `B2` (Idempotency Keys)
5. `B3` (Sagas)
6. `B4` (LangGraph Native)
7. `B5` (EvoUndo-Style Journaling)
8. `B6` (Verify-Before-Retry)
9. `veyra_zp` (Veyra Zero-Privilege Mode)
10. `veyra_contract` (Veyra Contract-Enabled Mode)

---

## 2. Pre-Registered Hypotheses & Decision Rules

### Safety Rule (Duplicate Effect Rate - DER)
Under `UNKNOWN_ACK` fault injection on non-idempotent mutations:
- **Expected Invariant:** `veyra_zp` and `veyra_contract` MUST achieve $\text{DER} = 0.0\%$.
- If $\text{DER} > 0.0\%$, the failure trajectory must be explicitly logged, classified, and reported with exact 95% confidence intervals.

### Veyra-ZP vs B6 Decision Rule
- If `veyra_zp` matches `B6` performance without statistical difference:
  - **Verdict:** Veyra-ZP reproduces the verify-before-retry strategy using standard tool surfaces. Product differentiation derives from system middleware packaging, trace auditability, and zero-code agent integration rather than algorithmic novelty.

### Veyra-Contract vs B2 Decision Rule
- Direct comparison against idempotency key baselines (`B2`):
  - Document exact tasks where `B2` wins (e.g., pure API support), where `veyra_contract` wins (e.g., post-condition state verification when idempotency keys are unacknowledged or un-persisted), and where both tie.

### Control Non-Inferiority Margin (Over-Blocking Test)
- **Pre-Registered Non-Inferiority Margin:** $\delta = 2.0\text{ percentage points}$.
- On nominal `CONTROL` runs (zero fault injection):
  $$\text{PassRate}(\text{Veyra}) \ge \text{PassRate}(\text{Raw}) - 2.0\%$$
- If Veyra causes $> 2.0\%$ reduction in control pass rate or false block rate, the over-blocking mechanism must be flagged as failing non-inferiority.

### Partial Mutation Rule
- On `PARTIAL_MUTATION` faults, if `veyra_contract` lacks a safe compensation or reconciliation hook, it MUST issue `DEFER` or `DENY` rather than attempting uncompensated retry.

---

## 3. Data Split & Frozen Test Protocol

1. **DEV & VALIDATION Splits:** Used for initial parameter verification and adapter validation.
2. **Frozen TEST Split:** Executed exactly **ONCE** after DEV analysis is finalized. Zero hyperparameter tuning or code adjustments allowed after observing TEST results.
