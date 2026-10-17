# Veyra Next-Win Empirical Evaluation Report

**Date:** October 8, 2026  
**Auditor / Engine:** Veyra Anti-Drift Audit Task Force  
**Repository:** [github.com/nisaral/Veyra](https://github.com/nisaral/Veyra)  
**Veyra Commit:** `3423e7b` (`main`)  
**Package Version:** `0.2.0`  
**Test Suite Health:** **261 passed, 1 skipped** in 6.47s (`pytest python/tests -q`)  

---

## Executive Summary & Anti-Drift Verdict

Veyra's canonical identity is frozen:
> **Framework-agnostic post-proposal execution control middleware for tool-using AI agents.**  
> `Agent proposes → Veyra validates/resolves → Tool executes → Veyra verifies/recovers/records`

This report executes the **Directive §17 Requirements**, synthesizing actual empirical evaluations, eliminating synthetic inflations, and documenting exactly what Veyra has proven, where it hit parity or null results, and which real-world capability it can defend.

---

## 1. Strongest Result: Safe Execution Control Under Ambiguous State & UNKNOWN_ACK

### Proven Mechanism (Empirical Trajectory Backed):
- **Live LLM Evaluation (`openai/gpt-4o` via Odyssey API, $N=8$ trials per arm):**
  - **Naive Agent:** $0.0\%$ pass rate, $100\%$ Duplicate Effect Rate (DER $= 1.0$), average $511$ tokens per turn trying to replan. When the LLM was told `"The charge tool timed out with no ACK"`, despite explicit system prompts instructing it not to duplicate payments, the model blindly called `charge` again in 8 out of 8 cases, creating duplicate charges in the ledger.
  - **Veyra-Wrapped Tool:** $100.0\%$ pass rate, $0\%$ Duplicate Effect Rate (DER $= 0.0$), $0$ LLM replan tokens, latency overhead $< 0.3\,\text{ms}$. Veyra caught the timeout, intercepted the lost ACK, ran the verification probe `verify_charge`, confirmed the mutation had committed, and returned `VERIFIED_COMMITTED` directly to the agent.
- **UndoBench Protocol Evaluation ($N=120$ trials, 95% Wilson Score CIs):**
  - Naive Retry (A1): 80 duplicate effects ($100\%$ DER on mutating faults), $33.3\%$ end-to-end success.
  - Veyra-Contract (A8): 0 duplicate effects ($0.0\%$ DER), $100.0\%$ recovery success, $100.0\%$ end-to-end success.

---

## 2. Strongest Null Result: Case Memory on Held-Out Trace Transfer

- **Empirical Measurement:**
  - Evaluated on ranking lab and held-out trajectory sets.
  - While Case Memory achieved $100\%$ Recall@1 on memorized in-distribution cases, on held-out unseen tasks and cross-domain tool variants, Case Memory demonstrated **0% net transfer lift** over deterministic schema contracts and TAgE branch-prediction ($p > 0.05$).
- **Architectural Action:**
  - Case Memory is officially classified as **OPTIONAL / EXPERIMENTAL**.
  - It is completely quarantined behind the plugin registry (`use_case_memory=False` by default) and excluded from the production execution path.

---

## 3. Strongest Loss: Agent Task Success on Complex External MCP Tasks

- **Empirical Measurement (MCPMark Filesystem Tasks):**
  - Evaluated on `easy/file_property` tasks using `openai/gpt-4o` with the real stdio MCP filesystem server.
  - **Outcome:** Pass rate was **0/2**.
  - **Diagnostic:** The frontier model listed files, inspected sizes, but stopped or renamed `bridge.jpg` instead of the largest file (`sg.jpg`), failing the benchmark assertions.
  - **Veyra Impact:** When wrapped with `VeyraMiddleware`, Veyra added negligible overhead ($< 1\,\text{ms}$) and caused zero false blocks, but **middleware cannot fix agent reasoning flaws**. If the agent's proposed plan is incorrect, post-proposal middleware preserves safety but cannot manufacture task competence.
- **Positioning Takeaway:**
  - Veyra must **never** claim to improve agent intelligence or raw task planning competence.
  - Claiming a "+25pp success lift" on general agent tasks was unearned and has been removed from all documentation and public web pages.

---

## 4. Strongest Competitor: B6 (Verify-Before-Retry) & B2 (Idempotency Keys)

- **Honest Head-to-Head Comparison:**
  - When an external API already provides a functioning idempotency key header (B2) or an agent developer hand-crafts a dedicated verification probe loop (B6) for that specific tool, **B6 and B2 also achieve 0% DER**.
  - On isolated `UNKNOWN_ACK` faults with existing probes:
    $$\text{Veyra DER} = \text{B6 DER} = 0\% \implies \mathbf{PARITY}$$
  - **We explicitly do NOT claim algorithmic superiority over verify-before-retry on this single fault.**

---

## 5. Failure Class Where Veyra Adds Unique Value

Veyra’s defensible value lies in **Unified Execution Policy Across Asymmetric Fault Boundaries**:

```text
                                 [Tool Invocation Fault]
                                            │
        ┌───────────────────────────────────┼──────────────────────────────────┐
        ▼                                   ▼                                  ▼
   [Transient Network Drop]         [UNKNOWN_ACK Mutation]             [Ambiguous State]
   (Idempotent Read)                (Verify Probe Available)           (No Key, No Probe)
        │                                   │                                  │
  Naive Retry: PASS                 Naive Retry: 100% DER             Naive Retry: 100% DER
  Veyra: SAFE RETRY                 B6: 0% DER                        B6: CRASH / BLIND REPLAY
                                    Veyra: VERIFY & ACCEPT            Veyra: SAFE DEFER / DENY (0% DER)
```

### The Value Matrix:
1. **Ambiguous External State (No Key, No Probe):**
   - Individual mechanisms fail: Naive retry causes duplicate mutations (100% DER); verify-before-retry crashes or falls back to blind retry.
   - **Veyra's Contract Policy:** Safely abstains (`DEFER`/`DENY`), preserving **0% DER**.
2. **Coercion Without Agent Replanning:**
   - Parameter type mismatches (e.g. string `"123"` vs int `123`) fail raw agents, burning a turn and tokens on replanning.
   - **Veyra's Contract Layer:** Deterministically coerces types according to the tool schema, executing safely in $24\,\mu\text{s}$ without an LLM round-trip.
3. **Execution Insurance:**
   - Instead of requiring engineers to hand-craft retry loops, idempotency stores, and verification handlers for every tool in every prompt, `safe_tool = veyra.wrap(tool)` provides declarative, uniform protection.

---

## 6. Real Product Implication

Veyra must be positioned strictly as:

> **Execution Insurance & Boundary Control for Tool-Using AI Agents.**  
> *Your agent decides what to do. Veyra decides whether and how that action can safely execute.*

### What Veyra is NOT:
- Not an LLM or RL tool router.
- Not an API Gateway or network proxy product.
- Not a replacement for pre-inference retrieval layers (e.g., AgentWeave).
- Not an agent reasoning framework.

---

## 7. Next Feature Justified by Evidence

1. **Pre-Inference + Post-Proposal Composition Harness (Win C):**
   - Combine candidate reduction (top-k tool filtering) with Veyra's post-proposal contract enforcement:
     $$\text{AgentWeave / Top-K Router} \xrightarrow{\text{Tokens Reduced}} \text{Agent} \xrightarrow{\text{Proposal}} \text{Veyra} \xrightarrow{\text{Safety & Recovery}} \text{Tool}$$
   - Measure whether the composition retains token efficiency while guaranteeing 0% DER and execution invariant enforcement.
2. **Real-World Resilience Track for MCP Servers:**
   - Standardized fault injection testbed for SQLite, Filesystem, and REST MCP servers, measuring recovery, duplicate effect rate, and latency overhead under realistic network failures.

---

## 8. Features Explicitly NOT Justified (Hard Frozen)

The following will **NOT** be built or merged:
- ❌ **No Reinforcement Learning (RL) or Contextual Bandits in production:** Bandits add exploration variance to mutating actions where safety demands determinism.
- ❌ **No LLM-as-a-Router:** Adds $500\text{--}2000\,\text{ms}$ latency and non-deterministic policy failures when microsecond deterministic evaluation is sufficient.
- ❌ **No Vector Database / Large Retrieval Engine in core:** Bloats package dependencies without demonstrable recovery benefits.
- ❌ **No Standalone API Gateway / Distributed Network Control Plane:** Veyra is in-process middleware.
- ❌ **No Complex Case Memory Tuning:** Case memory remains experimental until external traces show verified out-of-distribution transfer.
