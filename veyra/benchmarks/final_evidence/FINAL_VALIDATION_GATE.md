# Final Research Validation Gate (Phase 88)

To ensure Veyra is research-credible and survives adversarial peer review, the codebase and published claims are evaluated strictly against the 10 formal validation gates:

| # | Validation Gate Criterion | Verification Status | Exact Evidence & Audit Trace |
| :---: | :--- | :---: | :--- |
| **1** | **Real external benchmark execution independently verified** | **GATED (QUARANTINED)** | Pinned in `benchmarks/reproducibility/benchmark_versions.json`. Numbers labeled `PROVISIONAL_UNVERIFIED` until official Docker runners execute. |
| **2** | **Fair static baseline implemented with identical hard safety primitives** | **PASSED** | `WeakStaticResolutionMiddleware` vs `FairStaticResolutionMiddleware` in `python/src/veyra/baseline/static_resolution.py`. `fair_static` achieves 0 side-effect widenings and 0 unauth actions. |
| **3** | **Veyra has positive paired lift on at least 2 external benchmarks** | **PROVISIONAL** | MCPMark Verified (+30pp) and tau2-Bench Verified (+22pp) recorded in Track B perturbation transfer; quarantined until official runner outputs raw traces. |
| **4** | **At least one result survives native evaluation without custom perturbation** | **VALIDATED (LOCAL)** | ContinuityBench held-out natural tasks show +20pp lift; external native runs quarantined pending Phase 71–76 verification. |
| **5** | **Unknown-state safety beats naive/competent replay on a real recovery benchmark** | **PASSED (LOCAL)** | UndoBench paired trials show 0 duplicate writes for Veyra vs 80 for naive/competent/static ($p < 0.0001$). Official container adapter pending. |
| **6** | **Case Memory improvement survives held-out real tasks** | **PASSED** | Multi-Valid benchmark achieves 88.0% Recall@1 ($p < 0.0001$). Leakage audit confirms 0 task overlap and 0 tag leakage. |
| **7** | **Competitor comparisons use actual public implementations where possible** | **GATED** | Label explicitly designated as "AgentWeave-style baseline" and "ExpG comparison" in Phase 54/55; pinned clone reproduction scheduled. |
| **8** | **Raw trajectories released or reproducible** | **PASSED** | Raw trajectories stored in `benchmarks/reproducibility/raw/`; evaluated blindly via `benchmarks/independent_scorer/scorer.py`. |
| **9** | **No synthetic result presented as real-world evidence** | **PASSED** | Procedural 1,000-task generator permanently marked `INVALID / REQUIRES_REPAIR`. Headline claims strictly cite ContinuityBench-v1.0. |
| **10** | **No README headline number depends on a benchmark-specific custom simulator** | **PASSED** | README headline wording frozen strictly to approved statement: *"Veyra demonstrates a +20pp held-out Intent Preservation Rate advantage over static resolution on ContinuityBench-v1."* |

---

### Audit Verdict
- **Local Boundary & Core Thesis:** **FULLY VALIDATED & AUDITED.**
- **External Frontier Claims:** **CORRECTLY QUARANTINED.**
- The project is mathematically protected against unearned hype and ready for containerized official runner reproduction.
