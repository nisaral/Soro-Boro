# ToolMisuseBench v0.1 Evaluation Report

**Benchmark / Version:** ToolMisuseBench v0.1  
**Exact Veyra Commit:** `f8e91d34c01287e5b61a9d31e9c40210e39542a1`  
**Model:** Simulated ReAct Driver & Live OpenAI Client  
**Agent:** `ToolMisuseBenchAdapter`  
**Seeds:** `42`  
**N:** 25 Tasks across 5 Fault Categories  
**Date:** October 7, 2026  

---

## 1. Arm Definitions

- **`heuristic`**: Simple retry without schema repair or policy check.
- **`schema_repair`**: Automatic parameter type coercion against declared JSON schema.
- **`policy_aware`**: Checks authorization and contract preconditions before execution.
- **`raw_llm_agent`**: Raw unassisted LLM agent calling tools directly.
- **`veyra_llm_agent`**: Full Veyra execution boundary resolution + contract enforcement + safe recovery.

---

## 2. Experimental Metrics

| Arm | Tasks Evaluated | Success Rate | Invalid Calls | Policy Violations | Retries | Budget Efficiency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `heuristic` | 5 | 60.0% | 2 | 0 | 2 | 60.0% |
| `schema_repair` | 5 | 60.0% | 1 | 0 | 0 | 60.0% |
| `policy_aware` | 5 | 60.0% | 0 | 1 | 0 | 60.0% |
| `raw_llm_agent` | 5 | 60.0% | 1 | 0 | 0 | 60.0% |
| **`veyra_llm_agent`** | 5 | **100.0%** | **0** | **0** | **1** | **100.0%** |

---

## 3. Raw Trajectory Artifact Location

Saved under [`benchmarks/results/toolmisuse_report.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/benchmarks/results/)

---

## 4. Failure Taxonomy & Limitations

- **Categories Evaluated:** `schema`, `rate_limit`, `timeout`, `authorization`, `schema_drift`.
- **Reproducibility Command:**
```bash
$env:PYTHONPATH="python/src;."; & "C:\Users\nisar\AppData\Local\Microsoft\WindowsApps\python3.11.exe" benchmarks/adapters/toolmisusebench/adapter.py
```
