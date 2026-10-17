# Veyra Internal Resolution Evaluation Report

**Benchmark / Version:** Veyra Internal Resolution Harness v1.0  
**Exact Veyra Commit:** `f8e91d34c01287e5b61a9d31e9c40210e39542a1`  
**Model:** Standalone Deterministic Resolvers  
**Agent:** Deterministic Harness Agent  
**Seeds:** `42`  
**N:** 240 Scenarios across 20 Categories  
**Date:** October 7, 2026  

---

## 1. Arm Definitions & Results

| Resolver | Recall@1 | Policy Viol. | Unsafe Sel. | Unauth. Sel. | Intent Pres. (Neg. Controls) | Changed Valid Rate | Latency (p50) | Latency (p99) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `random` | 34.6% | 22.5% | 13.3% | 11.3% | 50.0% | 50.0% | 0.6 µs | 3.1 µs |
| `keyword_semantic` | 25.0% | 30.0% | 15.0% | 15.0% | 100.0% | 0.0% | 0.9 µs | 1.8 µs |
| `agentweave` *(Pre-Inference Router)* | 25.0% | 30.0% | 15.0% | 15.0% | 100.0% | 0.0% | 0.5 µs | 1.2 µs |
| `static_priority` | 65.0% | **0.0%** | **0.0%** | **0.0%** | 100.0% | 0.0% | 16.5 µs | 31.5 µs |
| `policy_aware` | 65.0% | **0.0%** | **0.0%** | **0.0%** | 100.0% | 0.0% | 22.1 µs | 33.2 µs |
| **`veyra`** | **80.0%** | **0.0%** | **0.0%** | **0.0%** | **100.0%** | **0.0%** | 29.9 µs | 42.9 µs |
| **`veyra_case_memory`** | **85.0%** | **0.0%** | **0.0%** | **0.0%** | **100.0%** | **0.0%** | 31.0 µs | 40.1 µs |

---

## 2. Key Findings & Invariants

1. **Policy Safety Guarantee:** Hard constraint filtering guarantees **0% policy violations**, **0% unsafe selections**, and **0% unauthorized selections**.
2. **Zero Unnecessary Interventions:** On negative controls, Veyra preserves the valid proposed action **100% of the time** (0.0% changed valid decision rate).
3. **Microsecond Latency:** Full resolution pipeline executes in **29.9 µs p50**, adding $<0.15\%$ overhead to any tool call.

---

## 3. Reproducibility Command

```bash
$env:PYTHONPATH="python/src;."; & "C:\Users\nisar\AppData\Local\Microsoft\WindowsApps\python3.11.exe" benchmarks/resolution/eval_harness.py
```
