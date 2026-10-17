# Veyra Partial Observability Benchmark Protocol (v1.0-frozen)

**Date:** October 8, 2026  
**Status:** FROZEN RESEARCH PROTOCOL  
**Primary Claim under Test:**  
> *"Under partial observability and realistic execution-evidence failures, an uncertainty-aware recovery controller achieves a better safe-recovery/risk frontier than an observation-equivalent deterministic controller with the same recovery mechanisms."*

---

## 1. Core Principles & Isolation Invariants

1. **Strict Information Boundary:**  
   The controller and all baseline agents operate under partial observability. The ground-truth state of the environment (`true_execution_state`, true commit timestamp, unobserved transport duplicates) is accessible **exclusively** to the independent Oracle and the evaluation scoring harness.
2. **Observation Equivalence:**  
   Any head-to-head comparison between controller architectures (e.g. Full-Mechanism Deterministic vs. Belief-State Veyra) MUST receive byte-for-byte identical inputs: the serialized `Observation`, the `ExecutionContract`, and the `ActionHistory`.
3. **No Uncalibrated Risk Claims:**  
   Finite-sample observations of zero duplicate effects ($\text{DER} = 0$) do not constitute mathematical impossibility. All empirical zero-risk measurements must report the finite-sample one-sided 95% upper confidence bound (Rule of Three):
   $$\text{UCB}_{95\%} = \frac{-\ln(0.05)}{N} \approx \frac{2.9957}{N}$$
4. **Equal Recovery Action Spaces:**  
   Baselines cannot be handicapped by artificially restricting allowed actions when measuring algorithmic inference. The allowed action set is strictly frozen across candidate arms:
   - `VERIFY`
   - `RETRY`
   - `IDEMPOTENCY_REPLAY`
   - `RECONCILE`
   - `COMPENSATE`
   - `FALLBACK`
   - `DEFER`
   - `DENY`

---

## 2. Observable Inputs vs. Hidden Environment Variables

### Observable Inputs (`Observation` Object):
```python
@dataclass(frozen=True)
class Observation:
    action_id: str
    tool_name: str
    arguments: dict[str, Any]
    status_code: int | None
    error_message: str | None
    is_timeout: bool
    latency_ms: float
    headers: dict[str, str]
    probe_result: dict[str, Any] | None
    probe_latency_ms: float | None
    probe_freshness_sec: float | None
    local_attempt_count: int
    operation_identity: str
```

### Hidden Variables (Evaluator Oracle ONLY):
- `true_execution_state`: `NOT_COMMITTED`, `IN_FLIGHT`, `COMMITTED`, `PARTIAL`, `DUPLICATED`, `UNKNOWN`.
- `true_commit_timestamp`: Exact wall-clock millisecond when server mutated state.
- `transport_delivery_count`: Whether transport layer delivered packet 0, 1, or 2 times.
- `server_crash_offset`: Whether process crashed before, during, or after fsync.

---

## 3. Evaluated Arms & Protocols

1. **Arm A: Full-Mechanism Deterministic Heuristic**  
   Deterministic rule chain with access to probes, idempotency keys, reconciliation, and compensation. Does not compute epistemic posterior distributions or bounded risk integrals.
2. **Arm B: Belief-State Veyra**  
   Constrained belief-state recovery controller. Computes $P(\text{state} \mid \text{Observation})$ under Bayes' rule and optimizes expected utility subject to the hard risk invariant $P(\text{duplicate}) \le \epsilon$.
3. **Arm C: Simple Probabilistic Predictor + Hard Safety Gate**  
   Statistical classifier (SGD Logistic Regression) predicting $P(\text{committed})$ from observable features, gated by $P \le \epsilon$.
4. **Arm D: Cautious Verify-Before-Retry (UndoBench B6 Cautious)**  
   Active probes when available; cautious abstention (`DEFER`) when verification probes are absent on non-idempotent operations.
5. **Arm E: Cautious Idempotency-Key Baseline (UndoBench B2 Cautious)**  
   Idempotency replay when key supported; cautious abstention (`DEFER`) when endpoint lacks idempotency support.
6. **Arm F: Environment Oracle**  
   Theoretical upper-bound policy with direct access to hidden environment state. Marked as non-deployable reference.

---

## 4. Evaluation Metrics & Scoring Definitions

- **Safe Recovery Rate (SRR):**  
  Proportion of failed executions safely recovered (completed without duplicate side-effects).
- **Duplicate Effect Rate (DER):**  
  Proportion of executions that caused duplicate mutations (e.g., duplicate financial debit, duplicate database insert).
- **One-Sided 95% DER Upper Bound ($\text{DER}_{95\%}$):**  
  Wilson upper bound or Rule of Three bound when observed DER = 0.
- **Unnecessary Abstention Rate (UAR):**  
  Proportion of executions safely recoverable by the Oracle that were abandoned by the policy.
- **Safe Recovery Under Risk Budget ($\text{SRRB}(\epsilon)$):**  
  $$\text{SRRB}(\epsilon) = \max_{\pi} \text{SRR}(\pi) \quad \text{subject to} \quad \text{DER}(\pi) \le \epsilon$$
  Evaluated across risk thresholds: $\epsilon \in \{0.0\%, 0.1\%, 0.5\%, 1.0\%, 2.0\%, 5.0\%\}$.

---

## 5. Statistical Rigor & Bootstrap Procedure

- **Cluster Unit:** Scenario template / domain structure ($K = 50$ unique clusters).
- **Executions:** $N = 500$ paired runs across 10 random seeds ($N=10$ per cluster).
- **Bootstrap Method:** Scenario-clustered paired bootstrap with 1,000 resamples over the 50 scenario clusters.
- **Reporting Standard:** Mean, 95% paired two-sided confidence intervals $[\Delta_{\text{low}}, \Delta_{\text{high}}]$, and finite-sample DER upper bounds.
