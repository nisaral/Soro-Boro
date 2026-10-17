# UndoBench v1.0.1 Evaluation Report

**Benchmark / Version:** UndoBench v1.0.1  
**Exact Veyra Commit:** `f8e91d34c01287e5b61a9d31e9c40210e39542a1`  
**Model:** Simulated ReAct Driver & Live OpenAI Client  
**Agent:** `VeyraUndoBenchAdapter`  
**Seeds:** `42`, `100`, `2026`  
**N:** 150 Trials (50 tasks × 3 seeds)  
**Date:** October 7, 2026  

---

## 1. Arm Definitions

- **`none`**: Raw agent proposed tool calls executed directly with 0 middleware.
- **`B0_naive_retry`**: Blindly retries tool execution on network timeouts.
- **`B1_checkpoint_rollback`**: State checkpointing and rollback on error.
- **`B2_idempotency_keys`**: Idempotency key pass-through.
- **`B3_sagas`**: Saga pattern orchestrator.
- **`B4_langgraph_native`**: Native LangGraph exception handler.
- **`B5_evoundo_journaling`**: Journaling state recovery.
- **`B6_verify_before_retry`**: Read-only probe verification before retry.
- **`veyra_zp`**: Veyra Zero-Privilege mode (standard tool surface only, error observation, non-mutating verification probes, abstains on UNKNOWN_ACK).
- **`veyra_contract`**: Veyra Contract-Enabled mode (explicit YAML/JSON contracts, idempotency keys, verification hooks, compensation hooks).

---

## 2. Experimental Metrics & 95% Confidence Intervals

| Arm | Duplicate Effect Rate (DER) | Recovery Success Rate | Control Pass Rate | 95% Confidence Interval (DER) | 95% Confidence Interval (Recovery) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `none` | 0.0% | 0.0% | 100.0% | [0.0%, 0.0%] | [0.0%, 0.0%] |
| `B0_naive_retry` | **100.0%** | 0.0% | 100.0% | [97.5%, 100.0%] | [0.0%, 0.0%] |
| `B1_checkpoint_rollback` | **100.0%** | 0.0% | 100.0% | [97.5%, 100.0%] | [0.0%, 0.0%] |
| `B2_idempotency_keys` | **0.0%** | 100.0% | 100.0% | [0.0%, 2.5%] | [97.5%, 100.0%] |
| `B3_sagas` | 0.0% | 100.0% | 100.0% | [0.0%, 2.5%] | [97.5%, 100.0%] |
| `B4_langgraph_native` | 0.0% | 100.0% | 100.0% | [0.0%, 2.5%] | [97.5%, 100.0%] |
| `B5_evoundo_journaling` | 0.0% | 100.0% | 100.0% | [0.0%, 2.5%] | [97.5%, 100.0%] |
| `B6_verify_before_retry` | **0.0%** | 100.0% | 100.0% | [0.0%, 2.5%] | [97.5%, 100.0%] |
| **`veyra_zp`** | **0.0%** | 0.0% *(Abstains)* | 100.0% | [0.0%, 2.5%] | [0.0%, 0.0%] |
| **`veyra_contract`** | **0.0%** | **100.0%** | **100.0%** | [0.0%, 2.5%] | [97.5%, 100.0%] |

---

## 3. Raw Trajectory Artifact Location

All raw JSON trajectory records conforming to Section 24 are saved under:
[`benchmarks/results/undobench_trajectories/`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/benchmarks/results/)

---

## 4. Negative & Null Results

- In **Veyra-ZP (Zero-Privilege Mode)**, when a network drop occurs during a non-idempotent mutation (`UNKNOWN_ACK`) and no read-only verification probe is declared in the standard tool schema, Veyra-ZP **abstains** (`DEFER`). It achieves 0% Duplicate Effect Rate (0 duplicate credit card charges), but cannot autonomously complete the recovery without contract hooks.
- **Control Non-Inferiority:** On nominal `CONTROL` runs (0 fault injection), `veyra_zp` and `veyra_contract` achieved a **100.0% pass rate** (0.0% over-blocking, satisfying the pre-registered 2.0pp margin).

---

## 5. Failure Taxonomy Breakdown

Across 150 evaluation trials:
- `UNKNOWN_ACK`: 50 trials (33.3%)
- `PARTIAL_MUTATION`: 50 trials (33.3%)
- `PRECONDITION_FAILURE`: 50 trials (33.3%)

---

## 6. Limitations & Reproducibility Command

### Limitations
- Requires mock backend state tracking or verification probes to confirm execution status under lost network response packets.

### Reproducibility Command
```bash
$env:PYTHONPATH="python/src;."; & "C:\Users\nisar\AppData\Local\Microsoft\WindowsApps\python3.11.exe" benchmarks/adapters/undobench/adapter.py
```
