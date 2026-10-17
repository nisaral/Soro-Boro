# Final Competitor Architecture & Evidence Matrix (Phase 87 & Section 11)

**Principle (Section 11):** Evidence-based only. No competitor is credited or penalized for untested speculative features.
Where reproducible implementations exist, evaluate directly.
If reproduction is impossible, the comparison is strictly labeled:
`RELATED SYSTEM`
not:
`BENCHMARKED COMPETITOR`

| System | Primary Architectural Layer | Execution Boundary Phase | Requires LLM Inference at Boundary? | Execution Memory Type | Dynamic Boundary Recovery? | Dynamic State & Freshness Aware? | Unknown-State Mutation Safety? | Pre-Inference Tool Discovery? | Decision Latency (Typical) | Benchmark Evidence Status | Open Source? | Integration Mechanism |
| :--- | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: |
| **Veyra** | Execution Boundary Middleware | **Post-Proposal** (`Agent → Veyra → Tool`) | **NO** (Deterministic / ML Policy) | Case Memory (13.5 KB) & TAGE (1.5 KB) | **YES** (Contract-guided fallback) | **YES** (Freshness, tenant, consistency, health) | **YES** (Rejects blind retry; issues `VERIFY` / `COMPENSATE`) | NO (Complementary to routers) | **$8.3\,\mu\text{s} - 27.7\,\mu\text{s}$** (Microsecond-scale) | Validated on ContinuityBench-v1.0 & 300 Scorecard; Quarantined for external | **YES** | Standalone Middleware / MCP Interceptor / Python SDK |
| **AgentWeave** | Routing Layer | **Pre-Inference** (`Context → AgentWeave → Prompt`) | YES / Semantic Embedding | None (Static Graph / Router) | NO (Cannot resolve tool failure after action proposed) | NO (Optimizes tool candidate exposure) | NO (Pass-through to agent) | **YES** (Filters tool catalog, cuts tokens 66%) | ~12.5 ms (Embedding / graph lookup) | **RELATED SYSTEM** (Quarantined pending pinned clone reproduction) | YES | Agent Framework / Prompt Pre-processor |
| **ToolRoute** | Pre-Inference Router | **Pre-Inference** (`Context → Router → Subsets`) | YES / LM Router | None | NO | NO | NO | **YES** | ~45–120 ms | **RELATED SYSTEM** (Unverified paper baseline; no reproducible code) | NO | Pre-inference tool filtering |
| **Toolport / Lazy Discovery** | Lazy Tool Retrieval | **Pre-Inference** (`Query → Tool Index → Prompt`) | YES / Vector DB | None | NO | NO | NO | **YES** (Lazy tool loading) | ~20–80 ms | **RELATED SYSTEM** (Unverified external implementation) | YES | Tool retrieval gateway |
| **ExpG** | Context Augmentation | **Pre-Inference** (`Memory → Prompt Injection`) | **YES** (Requires LLM to interpret guidance) | Textual Guidance Buffer (240 KB) | NO (Relies on LLM reasoning to self-correct) | Partial (Only if captured in prompt text) | NO (Does not intercept dropped ACKs) | Partial (Prompt guidance) | ~850 ms (LLM prompt token overhead) | **RELATED SYSTEM** (Quarantined pending official codebase run) | YES | Prompt Memory Extension |
| **AgentDebugX** | Postmortem / Observability | **Post-Failure** (`Failure → Log → Debugger`) | YES (LLM Diagnostic Agent) | Postmortem Trace Store | NO (Inline recovery not supported; requires re-plan) | Retrospective only | NO (Offline diagnosis) | NO | Multi-second (Re-runs diagnosis workflow) | **RELATED SYSTEM** (Quarantined pending workflow reproduction) | YES | Observability / Debugging Agent |
| **OpenAI Tool Search** | Model Platform Primitive | **Pre-Inference** (`Prompt → API Router`) | YES (Model-internal) | Server-side semantic index | NO (Fails if chosen tool returns 500) | NO (Static JSON Schema match) | NO | **YES** (Filters tools inside API) | ~100–300 ms (Model API latency) | **RELATED SYSTEM** (Proprietary platform feature) | NO (Proprietary API) | OpenAI API parameter |
| **AWS AgentCore Tool Search** | Enterprise Gateway | **Pre-Inference** (`Gateway → Bedrock`) | Hybrid (OpenSearch / Bedrock) | Vector store index | NO (Passes error back to agent) | Partial (IAM permissions only) | NO | **YES** (Semantic tool catalog lookup) | ~50–150 ms | **RELATED SYSTEM** (Proprietary cloud service) | NO (AWS Managed) | AWS Bedrock Agent Gateway |

---

### Layered Complementarity Finding
Veyra does **not** compete with pre-inference routers like AgentWeave or OpenAI Tool Search.
As demonstrated in Phase 54 and Section 12:
- Pre-inference routers reduce token context costs by narrowing candidate exposure.
- Veyra enforces post-proposal execution-path invariants and guarantees continuity when the selected tool path degrades or disconnects.
- **Combined (AgentWeave + Veyra):** Delivers both token reduction and boundary execution safety.
