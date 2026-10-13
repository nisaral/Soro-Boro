# Soro Verification Claims Ledger

> **Automated Gate:** Every metric and headline figure reported on the website or resume maps directly to a machine-generated JSON artifact key, a raw artifact path, a reproducible command, and a git commit.
> Enforced automatically via `python scripts/verify_claims_ledger.py` (17/17 checks passed).

**Git Commit:** `caa38bdcf6542133effac5b80ba15fca48624b0e`  
**Working Tree Status:** `dirty` (re-verified prior to tagging)  
**Execution Timestamp:** 2026-10-12T00:22:00Z  
**Verification Gate Status:** **100% PASSED (17/17 Claims Machine-Verified)**

---

## 1. Conformal Tool Routing (505-Query Benchmark)

| Claim ID | Claimed Statement | Ground Truth Value | Report Artifact | Raw Wire / Ground Truth Artifact | Evidence Quality | Reproduction Command |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CONFORMAL_COVERAGE_EMPIRICAL` | Conformal LAC empirical coverage ($\alpha=0.05$) | **92.49%** | `reports/results_conformal_matched_sweep.json` | `reports/results_conformal_matched_sweep.json` | `empirical_benchmark_run` | `python experiments/run_conformal_sweep.py` |
| `CONFORMAL_MEAN_SET_SIZE` | Mean candidate set size | **2.07 tools** | `reports/results_conformal_matched_sweep.json` | `reports/results_conformal_matched_sweep.json` | `empirical_benchmark_run` | `python experiments/run_conformal_sweep.py` |
| `FIXED_K3_COVERAGE` | Fixed top-3 coverage | **91.70%** | `reports/results_conformal_matched_sweep.json` | `reports/results_conformal_matched_sweep.json` | `empirical_benchmark_run` | `python experiments/run_conformal_sweep.py` |
| `FIXED_K4_COVERAGE` | Fixed top-4 coverage | **93.68%** | `reports/results_conformal_matched_sweep.json` | `reports/results_conformal_matched_sweep.json` | `empirical_benchmark_run` | `python experiments/run_conformal_sweep.py` |
| `MATCHED_COVERAGE_CANDIDATE_REDUCTION` | Candidate reduction vs interpolated matched $k \approx 3.40$ | **39.1%** | `reports/results_conformal_matched_sweep.json` | `reports/results_conformal_matched_sweep.json` | `empirical_benchmark_run` | `python experiments/run_conformal_sweep.py` |

---

## 2. Milestone M4 Real Fault Injection (Controlled Mechanism Evaluation)

*Note: The fault harness evaluates mechanism performance under a controlled 40/30/15/15 fault mix (Post-commit, Pre-commit, Verifier crash, Adversarial concurrent race). Field deferral rates are determined by operational network distributions and measured via Soro Shadow Mode.*

| Claim ID | Claimed Statement | Ground Truth Value | Report Artifact | Raw Wire / Ground Truth Artifact | Evidence Quality | Reproduction Command |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `M4_AT_RISK_TRIALS_PER_SYSTEM` | At-risk trials per system | **700 trials** | `reports/results_m4_real_faults.json` | `reports/results_m4_real_faults.json` | `fault_injection_experiment` | `python experiments/run_m4_fault_injection.py` |
| `M4_TOTAL_AT_RISK_TRIALS` | Total at-risk trials across 4 systems | **2,800 trials** | `reports/results_m4_real_faults.json` | `reports/results_m4_real_faults.json` | `fault_injection_experiment` | `python experiments/run_m4_fault_injection.py` |
| `M4_AT_RISK_RULE_OF_THREE_BOUND` | 95% Rule of Three duplicate bound | **&le; 0.43%** | `reports/results_m4_real_faults.json` | `reports/results_m4_real_faults.json` | `fault_injection_experiment` | `python experiments/run_m4_fault_injection.py` |
| `M4_SORO_OPAQUE_DEFERRAL_RATE` | Opaque tools deferral rate | **30.0%** | `reports/results_m4_real_faults.json` | `reports/results_m4_real_faults.json` | `fault_injection_experiment` | `python experiments/run_m4_fault_injection.py` |
| `M4_SORO_ID_VERIFIED_DEFERRAL_RATE` | Id-verified deferral rate | **5.4%** | `reports/results_m4_real_faults.json` | `reports/results_m4_real_faults.json` | `fault_injection_experiment` | `python experiments/run_m4_fault_injection.py` |
| `M4_SORO_ID_VERIFIED_DUPLICATE_RATE` | Id-verified duplicate rate | **0.0%** | `reports/results_m4_real_faults.json` | `reports/results_m4_real_faults.json` | `fault_injection_experiment` | `python experiments/run_m4_fault_injection.py` |

---

## 3. Official MCP Reference Wire Captures (Golden-File Artifacts)

*Note: Verified directly from raw JSON-RPC `tools/list` responses on official reference servers over stdio.*

| Claim ID | Claimed Statement | Ground Truth Value | Report Artifact | Raw Wire / Ground Truth Artifact | Evidence Quality | Reproduction Command |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GOLDEN_FILESYSTEM_TOOLS_COUNT` | Tools exposed by official filesystem server | **14 tools** | `python/raw_tools_list_filesystem.json` | `python/raw_tools_list_filesystem.json` | `raw_stdio_wire_capture` | `npx -y @modelcontextprotocol/server-filesystem .` |
| `GOLDEN_FILESYSTEM_EXPLICIT_ANNOTATIONS_RATE` | Explicit annotation rate in filesystem server | **100.0% (14/14)** | `python/raw_tools_list_filesystem.json` | `python/raw_tools_list_filesystem.json` | `raw_stdio_wire_capture` | `npx -y @modelcontextprotocol/server-filesystem .` |
| `GOLDEN_MEMORY_TOOLS_COUNT` | Tools exposed by official memory server | **9 tools** | `python/raw_tools_list_memory.json` | `python/raw_tools_list_memory.json` | `raw_stdio_wire_capture` | `npx -y @modelcontextprotocol/server-memory` |
| `GOLDEN_MEMORY_EXPLICIT_ANNOTATIONS_RATE` | Explicit annotation rate in memory server | **100.0% (9/9)** | `python/raw_tools_list_memory.json` | `python/raw_tools_list_memory.json` | `raw_stdio_wire_capture` | `npx -y @modelcontextprotocol/server-memory` |
| `GOLDEN_MCP_EVERYTHING_TOOLS_COUNT` | Tools exposed by official everything server | **13 tools** | `python/raw_tools_list_everything.json` | `python/raw_tools_list_everything.json` | `raw_stdio_wire_capture` | `npx -y @modelcontextprotocol/server-everything` |
| `GOLDEN_MCP_EVERYTHING_EXPLICIT_ANNOTATIONS_RATE` | Explicit annotation rate in everything server | **100.0% (13/13)** | `python/raw_tools_list_everything.json` | `python/raw_tools_list_everything.json` | `raw_stdio_wire_capture` | `npx -y @modelcontextprotocol/server-everything` |

---

## 4. Vendor OpenAPI Specification Audits (Static Repository Inspection)

| Claim ID | Claimed Statement | Ground Truth Value | Report Artifact | Raw Wire / Ground Truth Artifact | Evidence Quality | Reproduction Command |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `VENDOR_SPEC_STRIPE_POST_ENDPOINTS` | Stripe OpenAPI POST operations | **307 endpoints** | `reports/vendor_openapi_declared_vs_verified.json` | `examples/vendor_openapi/stripe_spec3.json` | `openapi_spec_audit` | `python experiments/run_declared_vs_verified_sandbox.py` |
| `VENDOR_SPEC_STRIPE_DECLARED_KEYS` | Stripe POST endpoints declaring Idempotency-Key | **0 endpoints** | `reports/vendor_openapi_declared_vs_verified.json` | `examples/vendor_openapi/stripe_spec3.json` | `openapi_spec_audit` | `python experiments/run_declared_vs_verified_sandbox.py` |

---

## 5. Ecosystem Survey & Live Ground Truth Status

*Status: Static tarball survey withdrawn. Ecosystem claims are strictly gated on live stdio `tools/list` wire execution.*
- **Static Detector Falsified:** Live wire inspection revealed static regex scanners suffer ~33% false negatives due to bundled schemas and dynamic registration (e.g. `@playwright/mcp` was statically predicted unannotated, but is 100% annotated with 25 tools live).
- **Vendor Claims Withdrawn:** All unverified vendor lists withdrawn pending verified live wire captures.
- **Ground Truth Protocol:** Live stdio census runs in CI VMs with dummy credentials, strict JSON-RPC request ID matching, and explicit reporting of `COULD_NOT_START` as a distinct category (never conflated with unannotated).



