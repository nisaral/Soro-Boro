# Recovery Controller Comparison & Analysis

**Date:** October 8, 2026  
**Evaluation Suite:** Heterogeneous Fault Suite ($N=6$ scenarios across heterogeneous domains)  
**Artifacts:** [`benchmarks/recovery_controller/results.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/benchmarks/recovery_controller/results.json)  
**Directive Reference:** Veyra Algorithmic Upgrade (§9, §12, §14)  

---

## 1. Head-to-Head Comparison Matrix

| Arm / System | Safe Recovery Rate | Duplicate Effect Rate (DER) | Unnecessary Abstention Rate | Recovery Strategy Profile |
| :--- | :---: | :---: | :---: | :--- |
| **A0: Raw Agent (LLM)** | 33.3% | **66.7%** (4 duplicates) | 0.0% | Unstructured replan blindly replays mutations |
| **A1: Naive Retry** | 33.3% | **66.7%** (4 duplicates) | 0.0% | Blind retry loop creates duplicates on all mutations |
| **A2: Verify-Before-Retry (B6)** | 50.0% | **50.0%** (3 duplicates) | 0.0% | Recovers when probe exists; replays blind when probe missing |
| **A3: Idempotency Keys (B2)** | 50.0% | **50.0%** (3 duplicates) | 0.0% | Recovers when key supported; replays blind when unsupported |
| **A4: Current Veyra (Deterministic)** | 33.3% | **0.0%** (0 duplicates) | **50.0%** (3 unnecessary) | Safe but timid: abstains (`DEFER`) whenever probe is missing |
| **A5: Belief-State Veyra (New)** | **83.3%** | **0.0%** (0 duplicates) | **0.0%** (0 unnecessary) | **Evidence acquisition + utility optimization under safety constraint** |

---

## 2. Testing the Big-Win Hypothesis (Directive §12)

> **Pre-Registered Hypothesis:**  
> *The constrained belief-state controller increases safe recovery on heterogeneous fault boundaries relative to any single fixed recovery strategy, while maintaining near-zero unsafe/duplicate external effects.*

### Empirical Verification:
1. **Beating Single Fixed Recovery Baselines:**
   - On this heterogeneous benchmark, B6 (Verify-Before-Retry) achieved $50.0\%$ safe recovery because it fails on non-verifiable endpoints.
   - B2 (Idempotency Keys) achieved $50.0\%$ safe recovery because it fails on legacy endpoints lacking idempotency support.
   - **Belief-State Veyra achieved $83.3\%$ safe recovery**, substantially outperforming B6 (+33.3pp) and B2 (+33.3pp) by dynamically selecting the correct mechanism (Verify $\rightarrow$ Idempotency $\rightarrow$ Reconcile) based on observed evidence.
2. **Eliminating the Abstention Trap vs Current Veyra:**
   - Current Veyra achieved $33.3\%$ safe recovery with a $50.0\%$ unnecessary abstention rate. It protected against duplicates (0% DER), but failed to complete recoverable tasks when evidence or idempotency could resolve the uncertainty.
   - Belief-State Veyra eliminated all unnecessary abstentions ($0.0\%$), lifting safe recovery from $33.3\% \to 83.3\%$ without introducing a single duplicate write ($0.0\%$ DER).
3. **True Safety Preservation in Ambiguous States (Scenario S3):**
   - In Scenario S3 (legacy write with no probe and no idempotency key), Belief-State Veyra correctly calculated that $P(\text{unsafe}) > \epsilon$ for all mutating actions, and safely emitted **`DEFER`**.
   - In contrast, A0, A1, A2, and A3 all triggered blind retries and generated duplicate writes.

---

## 3. Comparison with Related Work: Cordon vs Veyra (Directive §14)

### Cordon (Related System):
- **Mechanism:** Task-scoped semantic transaction containment. Cordon instruments the entire agent task inside a sandboxed virtual transaction, deferring or bundling external effects until final task commit.
- **Trade-off:** High architectural coupling; requires agent framework-specific hooks and rollback orchestration across all external APIs.

### Veyra (Execution Control Layer):
- **Mechanism:** In-process, post-proposal execution control at the discrete tool boundary.
- **Differentiation:** Agent-independent; treats each tool call atomically; dynamically queries read-only evidence probes at the point of failure to resolve hidden execution state; enforces policy constraints without rewriting the agent.
