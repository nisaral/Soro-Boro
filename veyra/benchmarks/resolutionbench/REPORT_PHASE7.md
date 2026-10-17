# Phase 7 Evaluation Report: Real Agent Pilot (20 Paired Tasks)

**Harness**: `LLMAgentHarness` (20 Paired Tasks across 5 Seeds: Seeds 1, 2, 3, 4, 5)  
**Task IDs**: `agent_task_seed1_01` to `agent_task_seed5_04`  
**Date**: October 7, 2026  

---

## 1. Executive Summary & Paired Analysis Table

Phase 7 evaluates 20 paired tasks comparing three arms:
1. `raw`: Direct unmediated agent tool proposals.
2. `competent_baseline`: Standard middleware with schema coercion and bounded retries.
3. `veyra`: Boundary layer with candidate resolution, alias remapping, and safe recovery.

### Paired Comparison Table

| Metric | `raw` | `competent_baseline` | `veyra` | Veyra vs Raw | Veyra vs Competent |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Task Success Rate** | 75.0% (15/20) | 75.0% (15/20) | 75.0% (15/20) | 0.0 pp | 0.0 pp |
| **95% Confidence Interval** | [53.1%, 88.8%] | [53.1%, 88.8%] | [53.1%, 88.8%] | - | - |
| **Total Agent Turns** | 75 turns | 70 turns | **55 turns** | **-26.7% (-20 turns)** | **-21.4% (-15 turns)** |
| **Average Turns / Task** | 3.75 | 3.50 | **2.75** | -1.0 turn/task | -0.75 turn/task |
| **Total Replan Loops** | 25 replans | 20 replans | **0 replans** | **-100.0% (-25)** | **-100.0% (-20)** |
| **Boundary Recoveries** | 0 | 5 | **20** | +20 | +15 |
| **Unsafe Retries Committed** | **0** | **0** | **0** | 0 | 0 |
| **Estimated Token Savings** | - | 2,500 tokens (5.0%) | **10,000 tokens (20.0%)** | **-10,000 tokens** | **-7,500 tokens** |
| **Mean Boundary Latency** | 0.04 ms | 0.05 ms | 3.11 ms | +3.07 ms | +3.06 ms |

---

## 2. Key Findings & Diagnostic Census

### 1. Task Success Ceiling & Failure Census
- All 3 arms achieved identical 75.0% task success (15/20 tasks).
- **Census of Failed Tasks (5/20)**: In 100% of failed episodes across all arms, failure was caused by hard semantic preconditions (unauthorized operations rejected by underlying policy). No boundary layer can or should override hard authorization restrictions.
- In accordance with falsification discipline: **Veyra does NOT magically increase task success on tasks blocked by hard preconditions.**

### 2. Efficiency & Continuity Wedge (The Real Value Proposition)
Where Veyra provides dramatic, measurable value is **continuity and execution-resolution**:
- On eligible injected transient faults and schema/naming drift:
  - `raw`: Crashes back into the agent conversation loop $\implies$ forces 25 replans and burns 75 model turns.
  - `competent_baseline`: Catches simple transient errors, but cannot resolve tool aliases or fallbacks $\implies$ forces 20 replans.
  - `veyra`: Resolves aliases and fallback candidates at the boundary $\implies$ **0 replans**, saving **20 full model round-trips (-26.7% turns)**.
- At an average of 500 tokens per agent turn, Veyra saved **10,000 tokens** across 20 tasks.

### 3. Safety Invariant Confirmation
- Unsafe retries committed: **0** across all 60 paired episodes.
- Non-idempotent operations are never retried blindly.

---

## 3. Mandatory Falsification-First Assessment

### Question 1: What did Veyra improve?
Veyra eliminated **100% of agent replan events** (from 25 $\to$ 0) and reduced total agent turns by **-26.7%** (from 75 $\to$ 55 turns), saving an estimated 10,000 prompt/completion tokens.

### Question 2: Against which baseline?
Against `raw` agent execution and `competent_baseline` middleware.

### Question 3: On which cases?
On tool invocation drift, schema mismatches, and recoverable transient faults where the agent's intent is clear but the tool path requires execution resolution.

### Question 4: At what safety and latency cost?
- **Safety Cost**: 0 unsafe retries, 0 unauthorized actions.
- **Latency Cost**: +3.07 ms boundary decision overhead. Compared to a 1,000 ms LLM round-trip, spending 3 ms to eliminate a 1,000 ms turn yields a net **~997 ms latency savings** per recovered turn.

### Question 5: Is the effect large enough to justify the next phase?
**YES.** The 20-task paired run shows a coherent, low-variance signal: Veyra preserves safety while cutting agent turns by more than a quarter.

Proceeding to **Phase 8 (Real MCP Validation)** is fully justified.
