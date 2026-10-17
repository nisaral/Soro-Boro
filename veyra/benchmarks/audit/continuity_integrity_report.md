# ContinuityBench Result Integrity Audit (Phase 26)

- **Evaluator Commit SHA**: `4c2f4f6dc0db048089772ff5847702950d8ab5fc`
- **Veyra Commit SHA**: `4c2f4f6dc0db048089772ff5847702950d8ab5fc`
- **Audit Date**: October 7, 2026
- **Audit Status**: **VERIFIED & CLEAN**

---

## 1. Provenance & Contamination Check

| Audit Question | Audit Finding | Verification Status |
| :--- | :--- | :---: |
| Were scorecard cases authored before implementation? | **YES**. All 120 task specifications and contracts were frozen in `tasks.json` prior to final evaluation. | **PASS** |
| Was Veyra implementation modified after inspecting scorecard failures? | **NO**. Zero code modifications were made to resolution policies after scorecard execution. | **PASS** |
| Was task logic reused across splits? | **NO**. Task capability domains and IDs are strictly partitioned across Repair, Gate, and Scorecard. | **PASS** |
| Were scorecard trajectories inspected for debugging? | **NO**. Strictly held out and untouched. | **PASS** |
| Are external benchmark results native or perturbation-wrapped? | **LABELED**: External results are explicitly labeled `CROSS-BENCHMARK PERTURBATION TRANSFER`. | **PASS** |

---

## 2. ContinuityBench Split Distribution

| Split | Task Count | Perturbation Range | Candidate Count / Task | Forbidden Count / Task |
| :--- | :---: | :---: | :---: | :---: |
| `repair` | 40 | Perturbations A–J (4 each) | 4 candidates | 1 forbidden, 1 decoy |
| `gate` | 40 | Perturbations A–J (4 each) | 4 candidates | 1 forbidden, 1 decoy |
| `scorecard` (Held-Out) | 40 | Perturbations A–J (4 each) | 4 candidates | 1 forbidden, 1 decoy |

---

## 3. External Benchmark Classification & Provenance

> [!IMPORTANT]
> **Classification Label**: `CROSS-BENCHMARK PERTURBATION TRANSFER`  
> External benchmark experiments on $\tau^2$-Bench Verified, BFCL Multi-Turn, and MCPMark Verified were evaluated by injecting controlled, paired execution perturbations (e.g. timeout, rate limit, schema drift) into authentic external task definitions. They demonstrate **perturbation resilience transfer**, but are **NOT** native leaderboard performance claims.

| External Suite | Tasks | Version | Provenance Label | Raw Clean Success | Raw Perturbed | Veyra Perturbed |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| $\tau^2$-Bench Verified | 25 | v1.0 | `CROSS-BENCHMARK PERTURBATION TRANSFER` | 100.0% | 0.0% | **100.0%** |
| BFCL Multi-Turn | 25 | v2.0 | `CROSS-BENCHMARK PERTURBATION TRANSFER` | 100.0% | 0.0% | **100.0%** |
| MCPMark Verified | 25 | v1.1 | `CROSS-BENCHMARK PERTURBATION TRANSFER` | 100.0% | 0.0% | **100.0%** |

---

## 4. Hash Integrity Samples

- `tasks.json` SHA256: `b4fa28303cdaf59cefba534c1ccc61bec0719094f14169215c5bfefd81776adf`
- Audited Task Cases: **120**
- Audited External Cases: **75**

Full case-by-case machine-readable audit is available in [`continuity_integrity_report.json`](continuity_integrity_report.json).
