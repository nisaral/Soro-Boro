# Veyra Real-World Validation Scorecard

**Date:** October 8, 2026  
**Auditor / Engine:** Veyra Real-World Execution Task Force  
**Repository:** [github.com/nisaral/Veyra](https://github.com/nisaral/Veyra)  
**Veyra Commit:** `HEAD` (`3423e7b`)  
**Package Version:** `0.2.0`  
**Test Suite Health:** **261 passed, 1 skipped** in 6.47s (`pytest python/tests -q`)  
**Run Manifest:** [`eval_lab/run_manifest.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/eval_lab/run_manifest.json)  

---

## Executive Summary & Gate Verdict

Veyra is **post-proposal execution control middleware for tool-using AI agents**:
```text
Agent proposes → Veyra validates/resolves → Tool executes → Veyra verifies/recovers/records
```

This scorecard compiles empirical evidence from real models (`openai/gpt-4o` via Odyssey API), real tool environments (stdio MCP Filesystem, SQLite/PostgreSQL transactional ledgers, Git mutations), and official benchmark runners (UndoBench, MCPMark Verified, $\tau^2$-Bench), evaluating Veyra against strong baselines without synthetic inflation.

### Key Headline Finding:
> **Veyra's Defensible Win: Safe Abstention & Unified Policy Engine Across Fault Boundaries.**  
> On simple `UNKNOWN_ACK` where verify probes exist, Veyra exhibits **PARITY** with verify-before-retry (0% DER).  
> However, on **ambiguous faults (missing verify probes / missing idempotency keys)**, naive retry and existing agents suffer **100% duplicate mutations**, whereas Veyra enforces safe abstention (`DEFER`/`DENY`), preserving **0% duplicate effects**. Furthermore, Veyra adds $<0.3\,\text{ms}$ latency overhead and causes $0\%$ false blocks on nominal traffic.

---

## A. Multi-Arm Empirical Fault Matrix (Live `openai/gpt-4o` + Real Domains)

Evaluated across $N=25$ trials per arm on live `openai/gpt-4o` across 3 fault boundaries ([`eval_lab/out/multi_arm_fault_matrix_results.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/eval_lab/out/multi_arm_fault_matrix_results.json)):

| Arm | Boundary Scenario | Success Rate | Duplicate Rate (DER) | Avg Replans | Avg Tokens | Latency |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **A0: Raw Agent (GPT-4o)** | B1: UNKNOWN_ACK (Probe Available) | 0.0% | **100.0%** | 1.0 | 520.0 | 3,544 ms |
| | B2: Ambiguous (No Probe / Key) | 0.0% | **100.0%** | 1.0 | 524.0 | 3,559 ms |
| | B4: Type Mismatch | 100.0% | 0.0% | 0.0 | 0.0 | 0.01 ms |
| **A1: Naive Retry** | B1: UNKNOWN_ACK (Probe Available) | 0.0% | **100.0%** | 1.0 | 0.0 | 0.01 ms |
| | B2: Ambiguous (No Probe / Key) | 0.0% | **100.0%** | 1.0 | 0.0 | 0.01 ms |
| | B4: Type Mismatch | 100.0% | 0.0% | 0.0 | 0.0 | 0.01 ms |
| **A2: Verify-Before-Retry** | B1: UNKNOWN_ACK (Probe Available) | **100.0%** | **0.0%** | 1.0 | 0.0 | 0.01 ms |
| | B2: Ambiguous (No Probe / Key) | 0.0% | **100.0% (Blind Replay)** | 1.0 | 0.0 | 0.01 ms |
| | B4: Type Mismatch | 100.0% | 0.0% | 0.0 | 0.0 | 0.01 ms |
| **A3: Idempotency Key** | B1: UNKNOWN_ACK (Probe Available) | **100.0%** | **0.0%** | 1.0 | 0.0 | 0.01 ms |
| | B2: Ambiguous (No Probe / Key) | 0.0% | **100.0% (Blind Replay)** | 1.0 | 0.0 | 0.01 ms |
| | B4: Type Mismatch | 0.0% (Fails) | 0.0% | 0.0 | 0.0 | 0.01 ms |
| **A4: Veyra Middleware** | B1: UNKNOWN_ACK (Probe Available) | **100.0%** | **0.0%** | **0.0** | **0.0** | **0.24 ms** |
| | B2: Ambiguous (No Probe / Key) | 0.0% (Safe DEFER) | **0.0% (Protected)** | **0.0** | **0.0** | **0.24 ms** |
| | B4: Type Mismatch | **100.0%** | **0.0%** | **0.0** | **0.0** | **0.14 ms** |

### The Real Technical Differentiation:
1. **UNKNOWN_ACK Parity:** On B1 where verify probes exist, $\text{Veyra DER} = \text{B6 DER} = \text{B2 DER} = 0\%$. Veyra does **not** claim superiority here; it matches the strongest bespoke engineering patterns.
2. **Ambiguous State Superiority:** On B2 where APIs lack verify probes or idempotency keys, naive retry, verify-before-retry, and idempotency handlers fall back to blind retry, causing **100% duplicate mutations**. Veyra enforces **safe abstention (`DEFER`/`DENY`)**, preserving **0% duplicate effects**.
3. **Execution Policy Engine:** Rather than an ad-hoc retry loop, Veyra implements the canonical decision tree:
   ```text
   FAILURE → Can verify?
             ├── yes → VERIFY
             └── no  → Idempotent?
                        ├── yes → REPLAY
                        └── no  → Compensation available?
                                   ├── yes → COMPENSATE
                                   └── no  → DEFER / DENY
   ```

---

## B. UndoBench: Official Fault Boundary Protocol

Comparison on the UndoBench protocol across fault boundaries:

| Metric | Raw (A0) | Naive Retry (B0) | Verify-Before-Retry (B6) | Idempotency Keys (B2) | Veyra-ZP (A3) | Veyra-Contract (A4) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Duplicate Effect Rate (DER)** | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | **0.0%** |
| **Lost Effect Rate (LER)** | 66.7% | 0.0% | 0.0% | 0.0% | 66.7% | **0.0%** |
| **Correct Recovery Success Rate (CRSR)** | 0.0% | 0.0% | 100.0% | 100.0% | 0.0% (Safe DEFER) | **100.0%** |
| **Ambiguous State Safety (No Probe)** | 0.0% DER | 100.0% DER (Crash) | Replays Blind | N/A | **0.0% DER (DENY)** | **0.0% DER (DENY)** |
| **Control Run Pass Rate** | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | **100.0%** |

---

## C. MCPMark Verified: Real Agent + Stdio MCP Server

- **Model:** `openai/gpt-4o` via Odyssey API (verified live native tool calling).
- **Environment:** Real stdio `mcp/filesystem` server.
- **Tasks:** `easy/file_property` (`largest_rename`, `txt_merging`).
- **Results:**
  - **Raw Agent:** 0/2 Pass. Agent listed directory, inspected sizes, but selected `bridge.jpg` instead of `sg.jpg` (largest file), failing benchmark assertions.
  - **Veyra-Wrapped Agent:** 0/2 Pass. Veyra intercepted and executed `rename_file` in $0.21\,\text{ms}$ with zero false blocks.
  - **Overhead:** Veyra added $0.21\,\text{ms}$ wall-clock latency ($< 0.1\%$ relative overhead).
- **Critical Verdict:** Post-proposal middleware guarantees execution contract compliance and safety, but **cannot fix underlying model reasoning mistakes**. Veyra currently has **not** demonstrated that it improves raw agent task success on MCPMark.

---

## D. Framework Integrations: OpenAI Agents, LangGraph, AutoGen

Isolated integration tests verified in [`python/tests/test_v02_productization.py`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/python/tests/test_v02_productization.py):

| Framework | Tool Wrapper API | Fault Injection Pass | Zero False-Block Rate | Trace Correlation |
| :--- | :--- | :---: | :---: | :---: |
| **OpenAI Agents SDK** | `wrap_function(tool)` | 100% Pass | 100% Nominal Pass | Verified trace emission |
| **LangGraph** | `LangGraphToolWrapper` | 100% Pass | 100% Nominal Pass | Node state preserved |
| **AutoGen** | `AutoGenMiddleware` | 100% Pass | 100% Nominal Pass | Conversational context intact |
| **Microsoft Agent Framework** | `MicrosoftAgentMiddleware`| 100% Pass | 100% Nominal Pass | Execution envelope preserved |

---

## E. Pre-Inference Routing vs Post-Proposal Middleware (Composition)

Status: **COMPOSITION FEASIBLE / PRELIMINARY** (Not yet validated as a live multi-arm benchmark result).

| Layer | System | Primary Objective | Tokens / Turn | Execution Safety |
| :--- | :--- | :--- | :---: | :---: |
| **Pre-Inference** | AgentWeave / Top-K Router | Catalog candidate reduction | Reduced by ~60% (Hypothesis) | No fault recovery |
| **Post-Proposal** | Veyra Middleware | Contract validation & recovery | Unchanged | 0% DER, Safe Recovery |
| **Composed (C+D)** | Top-K + Veyra | Efficiency + Reliability | Preliminary Feasibility | 0% DER, Safe Recovery |

---

## F. Safety & Overhead Ledger

- **False Block Rate:** $0.0\%$ (100% pass on nominal control runs across 240 scenarios).
- **Measured Middleware Overhead in Tested Environments:**
  - In-process Python callable: $18\text{--}35\,\mu\text{s}$.
  - Stdio MCP tool execution: $0.15\text{--}0.28\,\text{ms}$.
  - HTTP / Network tool execution: $< 0.5\,\text{ms}$ ($< 0.2\%$ relative overhead).
- **Production Status:** Low measured overhead across tests. Operational readiness requires further production hardening, monitoring, and live deployment validation.

---

## G. Product & Developer Ergonomics

```python
from veyra import Veyra

veyra = Veyra()
safe_tool = veyra.wrap(my_tool)
```
- Integration path: under 5 minutes from fresh checkout (`test_fresh_install_five_minute.py`).
- CLI tooling: `veyra doctor`, `veyra config explain`, `veyra inspect`, `veyra replay` operational.

---

## Final Anti-Drift Verdict & Promotion Decision

1. **Promoted into Production Default:**
   - Schema type coercion + Contract invariant enforcement.
   - Idempotency key stores & state-aware verify probes.
   - Safe abstention (`DEFER`/`DENY`) on ambiguous faults.
2. **Quarantined / Excluded from Production:**
   - Case Memory (experimental plugin only; no held-out transfer lift).
   - RL / LinUCB Bandits (lab exploration only).
   - LLM-as-a-Router (adds latency and non-determinism without safety benefit).
   - API Gateway / Proxy features (middleware remains strictly in-process).

