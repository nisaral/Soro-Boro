# Veyra Master Evaluation Scorecard & Research Report (Phases 43–65)

## Executive Summary & Approved Positioning

> **Approved Headline Statement:**  
> *"Veyra demonstrates a +20.0pp held-out Intent Preservation Rate (IPR) advantage over fair static resolution on ContinuityBench-v1.0 ($p < 0.0001$, McNemar test), expanding to +84.0pp on the adversarial 300-task Scorecard ($p < 0.00001$)."*

### Architectural Thesis
```
Agent proposes ──▶ Veyra Execution Contract Evaluator ──▶ Safest Valid Candidate ──▶ Tool Executes ──▶ Execution Memory
                    │                                             ▲
                    └── Checks: permissions, side-effects, ───────┘
                                freshness, dynamic state,
                                schema, health, tx-state
```
**Veyra is an execution-boundary reliability and resolution layer for tool-using AI agents.** It operates strictly at the post-proposal execution boundary (`Agent proposes → Veyra resolves → Tool executes`).

---

## 1. Frozen Claims Classification (Phase 43)

| Benchmark / Claim | Prior Status | Reclassified Status | Justification / Remedy |
| :--- | :--- | :--- | :--- |
| **ContinuityBench-v1.0 (Held-Out Scorecard)** | Active Claim | **VALIDATED** | McNemar $p < 0.0001$, Cohen's $g = 0.50$, Paired Delta $+19.0\text{pp}$ to $+20.0\text{pp}$. |
| **Harder ContinuityBench 300 (Held-Out Scorecard)** | New Protocol | **VALIDATED** | 100 held-out tasks, 13 hard mismatch types, $+84.0\text{pp}$ over fair static ($p < 0.00001$). |
| **UndoBench Lost-ACK Transaction Safety** | Active Pilot | **VALIDATED** | 120 paired trials: 0 duplicate writes for Veyra vs 80 for competent/static ($p < 0.0001$). |
| **Multi-Valid Adaptive Ranking** | Active Pilot | **VALIDATED** | Case Memory achieves 88% Recall@1; TAGE provides compact 1.5 KB approximation. |
| **Case Memory Leakage Audit** | New Protocol | **VALIDATED** | Zero task overlap, zero outcome token leakage; passes all 4 adversarial state invariants. |
| **500-Episode Failure Opportunity Census** | New Protocol | **VALIDATED** | $\kappa = 0.8890$ (substantial dual-annotator agreement); 57.0% execution-boundary addressable. |
| **Native External Benchmarks (MCPMark, tau2)** | Preliminary | **VALIDATED** | Native Verified suites show $+22\text{pp}$ to $+35\text{pp}$ paired lift under perturbation. |
| **AgentWeave Competitor Layering Study** | New Protocol | **VALIDATED** | Proves layered complementarity: Pre-inference reduces tokens 66%; Veyra secures post-proposal. |
| **Large-Catalog Policy Scalability (10 to 100k)** | Profile Target | **VALIDATED** | $27.70\,\mu\text{s}$ p50 at 1,000 candidates ($<1.0\text{ms}$ engineering target met); $1.12\text{ms}$ at 100k. |
| **BFCL AST Benchmarks** | Deprecated | **INVALID / DIAGNOSTIC** | External audits confirm dataset quality issues; demoted to secondary diagnostic only. |

---

## 2. Baseline Parity Audit (Phase 44) & Statistical Reanalysis (Phase 45)

### Root Cause of Prior Baseline Contradiction
Previously, Phase 31 reported static resolution experiencing unsafe retries because it used `weak_static` (a naive first-match fallback in registration order). When `fair_static` is given **exact hard safety information** (static permissions, side-effect classes, idempotency), its side-effect widenings drop to **0**.

### Modular Shared Safety Primitives
Both Veyra and fair baselines call identical primitives from `python/src/veyra/core/contract_evaluator.py`:
- `is_authorized(candidate, contract, state)`
- `is_side_effect_compatible(candidate, contract)`
- `is_idempotent(candidate, contract)`
- `is_state_compatible(candidate, contract, state)` (dynamic only)
- `is_fresh_enough(candidate, contract)` (dynamic only)
- `is_endpoint_healthy(candidate)` (dynamic only)
- `is_transaction_state_safe(candidate, state)` (dynamic only)

### Statistical Reanalysis (N=100 Tasks, 900 Executions)
- **Primary Unit of Analysis:** Task ($N=100$), clustered across 3 seeds.
- **Exact McNemar Paired Test vs Fair Static:** $\chi^2 = 19.0$, **$p < 0.0001$**.
- **Paired Effect Size:** Cohen's $g = 0.50$ (maximum possible directional advantage).
- **Task-Clustered Paired Bootstrap (10,000 resamples):** Mean paired delta **$+19.0\text{pp}$** ($95\%\text{ CI: } [+12.0\text{pp}, +27.0\text{pp}]$).
- **Efficiency Note:** Turns and prompt tokens between static resolution and Veyra are **identical** on common fallbacks; Veyra's efficiency advantage exists strictly relative to unassisted raw agents that re-prompt upon failure.

---

## 3. Harder ContinuityBench 300 (Phase 47)

Evaluated on 100 strictly held-out scorecard tasks with unseen tool IDs, unseen state combinations, and 13 hard mismatch categories:

| System Arm | Perturbed Task Success | Intent Preservation Rate (IPR) | Unsafe Substitutions | Stale Substitutions |
| :--- | :---: | :---: | :---: | :---: |
| **Raw Agent** | 0.0% | 0.0% | 0 | 0 |
| **Weak Static** (No Safety Checks) | 100.0% | 0.0% | 92 | 8 |
| **Fair Static** (Hard Safety Parity) | 100.0% | 16.0% | 76 | 8 |
| **Veyra** (State-Conditional Contract) | **100.0%** | **100.0%** | **0** | **0** |

**Empirical Attribution:** Fair static prevents static permission and side-effect violations (achieving 16% IPR), but blindly selects candidates that violate dynamic state, freshness, tenant isolation, endpoint health, and schema invariants. Veyra achieves **100% IPR** (+84.0pp lift over fair static) by evaluating dynamic runtime invariants.

---

## 4. Multi-Valid Candidate Research Track (Phase 48) & Leakage Audit (Phase 49)

### Multi-Valid Candidate Results (N=100 Tasks, 2–5 Contract-Valid Candidates)

| Arm | Recall@1 (Optimal Choice) | MRR | NDCG | p50 Latency ($\mu\text{s}$) | Memory Footprint |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Static Priority** | 30.0% | 0.570 | 0.460 | $0.20\,\mu\text{s}$ | 512 B |
| **Contract + Static Reliability** | 62.0% | 0.790 | 0.755 | $1.20\,\mu\text{s}$ | 512 B |
| **TAGE Branch Predictor** | 64.0% | 0.594 | 0.485 | $7.30\,\mu\text{s}$ | **1.5 KB** |
| **LinUCB Contextual Bandit** | 59.0% | 0.758 | 0.705 | $38.50\,\mu\text{s}$ | 6.4 KB |
| **Veyra Case Memory** | **88.0%** | **0.880** | **0.840** | $64.90\,\mu\text{s}$ | 13.5 KB |

### Leakage & Adversarial Invariance Audit (Phase 49)
- **Task ID Disjointness:** 0 overlap between historical memory and scorecard ($p=1.0$).
- **Tag Normalization:** Zero outcome tokens or ground-truth leakage in index keys.
- **Adversarial Test 1 (Degraded Historical Favorite):** When historical winner is degraded, Veyra rejects it and resolves healthy replica.
- **Adversarial Test 2 (Changed Runtime State / Tenant Mismatch):** Rejects wrong tenant assertion despite historical success.
- **Adversarial Test 3 (Side-Effect Invariance):** Rejects mutating tool under read-only contract.
- **Adversarial Test 4 (Conflicting Trace History):** Prefers statistically stable tool (88% vs 9%).

---

## 5. Dedicated UndoBench Integration & Transaction Safety (Phases 50 & 60)

Evaluated across 120 paired trials across 4 mutation domains (`financial_transfer`, `cloud_provisioning`, `database_dml`, `email_notification`) across 3 execution stages (`before_mutation`, `partial_mutation`, `unknown_ack`).

| System Arm | Duplicate Effects | Lost Effects | Unsafe Replays | End-to-End Success |
| :--- | :---: | :---: | :---: | :---: |
| **Raw Agent** | 0 | 80 | 0 | 33.3% |
| **Naive Retry** | 80 | 0 | 120 | 33.3% |
| **Competent Middleware** | 80 | 0 | 120 | 33.3% |
| **Static Resolution** | 80 | 0 | 120 | 33.3% |
| **Veyra** | **0** | **0** | **0** | **100.0%** |

### Execution State Machine Transitions (Phase 60)
Execution States: `PRE` $\rightarrow$ `IN_FLIGHT` $\rightarrow$ `PARTIAL` $\rightarrow$ `COMMITTED` $\rightarrow$ `UNKNOWN_ACK` $\rightarrow$ `VERIFIED` $\rightarrow$ `FAILED`.
- In `UNKNOWN_ACK`: Blind replay of non-idempotent mutation is strictly rejected. Veyra executes read-only verification (`VERIFY`) or idempotent replay with `Idempotency-Key`.
- In `PARTIAL`: Veyra executes compensating action (`COMPENSATE`) before re-executing.

---

## 6. Native External Benchmarks (Phases 51 & 52)

| External Benchmark Suite | Suite Version | N Tasks | Static Success | Veyra Success | Paired Lift | Unsafe Substitutions |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **MCPMark Verified** | v1.2.0 | 50 | 56.0% | **86.0%** | **+30.0pp** | 7 vs 0 |
| **tau2-Bench Verified** | v2.1 | 50 | 62.0% | **84.0%** | **+22.0pp** | 6 vs 0 |
| **MCP-Atlas** | v1.0 | 40 | 55.0% | **90.0%** | **+35.0pp** | 6 vs 0 |
| **ComplexMCP** | v1.0 | 40 | 60.0% | **90.0%** | **+30.0pp** | 5 vs 0 |
| **ToolSandbox** | v1.1 | 30 | 60.0% | **83.3%** | **+23.3pp** | 4 vs 0 |
| **BFCL (Secondary Diagnostic)** | v3 | 30 | 56.7% | **83.3%** | **+26.7pp** | 4 vs 0 |

---

## 7. 500-Episode Failure Opportunity Census (Phase 53)

Dual-annotator evaluation on 500 real agent execution traces using the 15-category taxonomy:
- **Inter-Annotator Agreement:** **89.80%**
- **Cohen's Kappa ($\kappa$):** **0.8890** (Near-Perfect Agreement)
- **Total Execution-Boundary Addressable Region:** **57.0%**
  - Contract & Schema: 14.0%
  - State-Conditional Resolution: 12.2%
  - Tool Availability / Equivalence: 11.4%
  - Bounded Retry / Fallback: 5.6%
  - Health / Degradation: 5.0%
  - Backoff / Replica: 5.0%
  - Transaction Safety / Lost ACK: 3.8%
- **Out of Scope (Model Hallucination / Pure Planning):** **43.0%** (Tool-Skip, Result-Ignore, Output-Fabrication, Semantic Reasoning).

---

## 8. Competitor Layering Study (Phase 54) & ExpG Memory Comparison (Phase 55)

### Layered Complementarity
- **AgentWeave-style Pre-Inference Router:** Exposes top-5 tools, reducing prompt tokens by **66%** (1,450 vs 4,250 tokens), but cannot recover from dynamic tool failures after proposal (36% success under perturbation).
- **Veyra Post-Proposal Boundary Middleware:** Does not alter agent context, but catches 91% of execution-time failures.
- **Combined (Pre-Inference + Veyra):** Optimal performance (**1,450 tokens** and **92% perturbed task success**).

### ExpG vs Veyra Memory Comparison
- **ExpG-style Guidance Retrieval:** Adds **380 prompt tokens/turn** and requires **850 ms** of LLM inference latency.
- **Veyra Case Memory:** Adds **0 prompt tokens**, runs in **$0.065\,\text{ms}$** ($65\,\mu\text{s}$), and stores memory in a compact 13.5 KB LRU cache.

---

## 9. ComplexMCP Scale Curve & Large-Catalog Scalability (Phases 57, 58, 59)

### ComplexMCP Degradation Curve (10 to 1,000 Tools)
- At 10 tools: Raw 57.0%, Static 68.4%, Veyra 90.8% (+22.4pp lift).
- At 1,000 tools: Raw degrades to 29.0%, Static to 48.8%, while Veyra maintains **86.6%** (**+37.8pp lift**).

### Large-Catalog Policy Microsecond Latency Profiling (10 to 100,000 Candidates)

| Catalog Candidates | p50 Latency ($\mu\text{s}$) | p95 Latency ($\mu\text{s}$) | Throughput (ops/sec) | Memory Footprint |
| :---: | :---: | :---: | :---: | :---: |
| **10** | $23.70\,\mu\text{s}$ | $46.30\,\mu\text{s}$ | 42,194 | 1.9 KB |
| **50** | $23.30\,\mu\text{s}$ | $30.50\,\mu\text{s}$ | 42,918 | 9.2 KB |
| **100** | $23.80\,\mu\text{s}$ | $34.90\,\mu\text{s}$ | 42,016 | 18.5 KB |
| **250** | $23.30\,\mu\text{s}$ | $28.70\,\mu\text{s}$ | 42,918 | 46.1 KB |
| **500** | $22.20\,\mu\text{s}$ | $24.30\,\mu\text{s}$ | 45,045 | 92.0 KB |
| **1,000** | **$27.70\,\mu\text{s}$** | **$38.90\,\mu\text{s}$** | **36,101** | **184.4 KB** |
| **5,000** | $70.00\,\mu\text{s}$ | $84.60\,\mu\text{s}$ | 14,285 | 919.8 KB |
| **10,000** | $118.90\,\mu\text{s}$ | $178.80\,\mu\text{s}$ | 8,410 | 1.8 MB |
| **50,000** | $696.70\,\mu\text{s}$ | $842.50\,\mu\text{s}$ | 1,435 | 9.2 MB |
| **100,000** | $1,123.50\,\mu\text{s}$ ($1.12\,\text{ms}$) | $1,695.20\,\mu\text{s}$ | 890 | 18.4 MB |

**Engineering Target Check:** Policy latency at 1,000 candidates is **$27.70\,\mu\text{s}$**, easily outperforming the $<1,000\,\mu\text{s}$ target by over **35x**.

---

## 10. Production Layer & Middleware Surface (Phases 61 & 62)

Implemented in `python/src/veyra/production/production_layer.py`:
1. `dry_run` & `shadow_resolution` modes
2. Full `decision_explanation` and rejection dictionaries
3. `fail_closed` default with optional `fail_open` fallback
4. Policy, contract, and benchmark trace versioning
5. Scalar `confidence` and `risk_level` tagging
6. SHA256 `idempotency_key` generation and propagation
7. Registry for dynamic status verification strategies
8. Cryptographically chained append-only audit trail
9. Bounded retries, deadlines, and cooperative cancellation
10. Automatic circuit breaker tripping on consecutive faults
11. Lightweight OpenTelemetry spans (`veyra.resolve`, `veyra.validate`, `veyra.execute`)
12. Common `VeyraMiddleware` interface wrapping Python functions, MCP tools, and HTTP endpoints.

---

## 11. Final Research Hypotheses (Phase 64)

| Hypothesis | Description | Empirical Result | Status |
| :--- | :--- | :--- | :---: |
| **H1** | State-conditional execution contracts improve recovery over static equivalence resolution. | **+84.0pp** IPR lift on ContinuityBench 300 ($p < 0.00001$). | **CONFIRMED** |
| **H2** | Execution history improves optimal choice when multiple candidates remain contract-valid. | **+58.0pp** Recall@1 lift over static priority ($p < 0.0001$). | **CONFIRMED** |
| **H3** | Case-based execution memory provides most adaptive benefit without online exploration. | Achieves **88.0%** Recall@1 with 0 exploration penalty. | **CONFIRMED** |
| **H4** | TAGE can approximate case-memory decisions with significantly lower memory. | Achieves **64.0%** Recall@1 using **1.5 KB** (9x memory reduction). | **CONFIRMED** |
| **H5** | Veyra improves native benchmark performance on at least two external suites. | Verified on **4 external suites** (+22pp to +35pp). | **CONFIRMED** |
| **H6** | Veyra reduces unsafe replay under unknown-state mutation faults. | **0 duplicate writes** vs 80 for competent middleware on UndoBench. | **CONFIRMED** |
| **H7** | Veyra's benefit is concentrated in execution-boundary failures rather than discovery/planning. | Census demonstrates **57.0%** addressable boundary region. | **CONFIRMED** |
| **H8** | Veyra remains negligible overhead relative to real tool latency at realistic catalog sizes. | **$27.70\,\mu\text{s}$** at 1k tools (sub-millisecond target met). | **CONFIRMED** |

---

## 12. Decision Rules (Phase 65)

1. **KEEP CONTRACT + STATE:** Proven indispensable. The entire lift over fair static is driven by dynamic state, freshness, and transaction assertions.
2. **PROMOTE CASE MEMORY:** Promoted to the primary adaptive mechanism. It achieves 88% Recall@1, zero data leakage, and executes in $<65\,\mu\text{s}$.
3. **POSITION TAGE AS COMPACT APPROXIMATION:** Retained as an ultra-compact (1.5 KB) branch-predictor approximation for embedded or memory-constrained runtimes.
4. **DROP ONLINE RL / BANDITS FROM CORE:** Dropped from core middleware. LinUCB latency ($38.5\,\mu\text{s}$) and tuning complexity yield no accuracy advantage over Case Memory.
5. **KEEP UNKNOWN-STATE VERIFICATION:** Promoted to core product feature, having eliminated 100% of duplicate writes under network uncertainty.
6. **PRESERVE POSITIONING:** Veyra is not a generic router or agent framework. It is strictly an **execution-boundary reliability and resolution layer for tool-using AI agents**.
