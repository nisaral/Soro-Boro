# Veyra Evidence Status Ledger (Phase 66 Quarantine)

**Audit Version:** `v1.1-quarantined`  
**Date:** October 7, 2026  
**Status Rule:** Strictly provisional. Zero unearned hype.

---

## 1. Frozen Thesis Statement & Approved Headline

> **Thesis:** State-conditional execution resolution can preserve an agent's intended action when the proposed execution path becomes unavailable or degraded.

> **Approved Headline Wording:**  
> *"Veyra demonstrates a +20pp held-out Intent Preservation Rate advantage over static resolution on ContinuityBench-v1."*

### Explicitly Prohibited Claims:
- ❌ Do NOT claim universal efficiency improvement over static resolution (turns/tokens are equal between fair static and Veyra on simple fallbacks; efficiency advantage is strictly vs. raw unassisted agent).
- ❌ Do NOT claim universal benchmark improvement across all agent tools.
- ❌ Do NOT claim TAGE is the best adaptive method (Case Memory dominates TAGE in optimal candidate recall when unconstrained by memory; TAGE is a compact 1.5 KB approximation).
- ❌ Do NOT claim Veyra is statistically superior merely because 95% CIs do not overlap (exact paired McNemar tests and task-clustered bootstraps required).
- ❌ Do NOT cite BFCL results as authoritative.
- ❌ Do NOT use external benchmark claims (MCPMark, tau2, MCP-Atlas, ComplexMCP) as official paper headlines until independently verified via Phase 67–76 runners.

---

## 2. Evidence Classification Ledger

### A. Strictly Validated Evidence
| Benchmark / Artifact | Metric | Validated Finding | Provenance |
| :--- | :--- | :--- | :--- |
| **ContinuityBench-v1.0 Scorecard** | IPR (N=40 held-out tasks) | Veyra 100.0% vs Static 80.0% (+20.0pp lift, 0 unsafe substitutions) | `benchmarks/continuitybench/scorecard_results.json` |
| **Component Attribution Ablation** | Incremental IPR Lift | Contract alone explains 0.0pp; State assertions and freshness explain entire +20.0pp lift | `benchmarks/continuitybench/component_ablation_results.json` |
| **Baseline Parity Audit (Phase 44)** | Hard Safety Invariants | `fair_static` achieves 0 side-effect widenings and 0 unauth actions; proves advantage is dynamic state | `python/src/veyra/core/contract_evaluator.py` |
| **Statistical Reanalysis (Phase 45)** | Exact McNemar & Bootstrap | Paired lift +19.0pp ($p < 0.0001$, Cohen's $g = 0.50$, bootstrap 95% CI: $[+12.0\text{pp}, +27.0\text{pp}]$) | `benchmarks/final_evidence/statistical_reanalysis_report.json` |
| **Independent Frozen Evaluator** | Read-Only SHA256 Runner | Runs from fresh checkout; validates dataset hash before evaluation; zero Veyra internal imports | `benchmarks/frozen_eval/run.py` |
| **Harder ContinuityBench 300** | Scorecard (N=100 tasks) | Raw 0%, Fair Static 16.0% (76 unsafe, 8 stale), Veyra 100.0% (+84.0pp lift, $p < 0.00001$) | `benchmarks/continuitybench/results_300_scorecard.json` |
| **Case Memory Leakage Audit** | Adversarial Invariance | 0 task overlap, 0 tag leakage, passes degraded winner, tenant mismatch, and conflicting frequency tests | `benchmarks/final_evidence/case_memory_leakage_audit.json` |
| **Large-Catalog Policy Scalability** | Latency & Scalability | 1,000 candidates: p50 $27.70\,\mu\text{s}$ (36,101 ops/sec); 100,000 candidates: $1.12\,\text{ms}$ | `benchmarks/final_evidence/scalability_and_scale_curve_report.json` |

---

### B. Quarantined Evidence (`PROVISIONAL_UNVERIFIED`)
The following external numbers are placed in **formal quarantine** until independently reproduced from real official runners, pinned environments, and raw trajectory artifacts (Phases 67–76):

1. **MCPMark Verified (+30pp lift):** Quarantined pending execution against official MCPMark Verified release and Docker containers.
2. **tau2-Bench Verified (+22pp lift):** Quarantined pending execution against official tau2-Bench Verified verifier.
3. **MCP-Atlas (+35pp lift):** Quarantined pending execution against official MCP-Atlas public server suite.
4. **ComplexMCP (+30pp lift & 1,000 tools):** Quarantined pending execution against official ComplexMCP Docker runner.
5. **ToolSandbox (+23.3pp lift):** Quarantined pending execution against official ToolSandbox benchmark.
6. **AgentWeave Competitor Study:** Quarantined pending execution against pinned public AgentWeave repository checkout.
7. **ExpG Competitor Comparison:** Quarantined pending execution against official ExpG code.
8. **ToolFailBench Diagnostic:** Quarantined pending official ToolFailBench dataset run.
9. **500-Episode Failure Census (57% addressable):** Quarantined pending raw trace-backed provenance validation.
10. **UndoBench 120 Paired Trials (0 duplicate writes):** Quarantined pending official UndoBench environment-oracle validation.
11. **Real LLM Confirmatory Study ("900 runs"):** Quarantined pending Phase 68 fresh real-model study with visible raw model trajectories in artifacts directory.

---

### C. Invalidated / Retired Artifacts
- **Pre-Phase 0 Procedural Generator (1,000 templated tasks):** Permanently discarded due to synthetic repetition across 6 templates producing false precision.
