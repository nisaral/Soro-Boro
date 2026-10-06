# Veyra — Frozen Objective & Execution Plan (v0.1)

> **"Build the boundary first. Measure what actually breaks. Automate only what can be made reliably safe. Learn only from evidence."**

---

## 1. Main Objective

Build Veyra as a **drop-in, vendor-neutral tool-boundary reliability layer** for existing AI agents.

The agent remains responsible for reasoning, conversation, and high-level planning. Veyra sits between the agent's proposed tool call and the actual tool:

```
User
  ↓
Existing Agent
  ↓
proposed tool call
  ↓
┌─────────────────────────────────┐
│              VEYRA              │
│                                 │
│  1. validate arguments          │
│  2. classify failure            │
│  3. safely resolve              │
│  4. route / recover             │
│  5. observe & audit             │
└────────────────┬────────────────┘
                 ↓
      MCP / Python / Internal
                 ↓
               result
                 ↓
               Veyra
                 ↓
         Existing Agent
```

### The Core Abstraction
$$\text{Agent proposes} \longrightarrow \text{Veyra resolves}$$

Veyra is strictly outside the agent reasoning loop. Learning is optional rather than mandatory.

---

## 2. Immediate Objective (Binary Milestone)

Do not try to solve "agent tooling" generally. Our immediate question is:

> **Can Veyra reliably resolve a meaningful class of problematic tool calls without forcing the agent to re-plan, while adding negligible runtime overhead and very low harmful-intervention risk?**

$$\text{Can this be useful?} \longrightarrow \begin{cases} \textbf{YES} \longrightarrow \text{Continue} \\ \textbf{NO} \longrightarrow \text{Kill / Reposition} \end{cases}$$

Not:
- Can we make the fanciest router?
- Can we beat every tool-retrieval benchmark?
- Can we train an RL agent?

Those come only after the basic reliability layer demonstrates value.

---

## 3. What Veyra v0.1 Actually Is

Keep it very small.

### Supported Initially
- **Python functions** (`@veyra.tool(...)`, `veyra.wrap(...)`)
- **MCP (Model Context Protocol)** middleware
- *Nothing else. No OpenAPI/REST in the first implementation.*

### V0.1 Responsibilities
1. **Intercept** proposed tool calls
2. **Validate** arguments
3. **Classify** failures into structured taxonomy
4. **Apply** only provably safe corrections (semantics-preserving normalizations)
5. **Retry** only safe failure classes (idempotent + transient/rate-limit)
6. **Return structured errors** when Veyra cannot safely resolve (enabling the agent to re-plan with precise error feedback)
7. **Record** an execution trace

### What Veyra Must NOT Do in v0.1 (Strict Exclusions)
- ❌ No semantic argument guessing
- ❌ No automatic tool equivalence discovery
- ❌ No arbitrary fallback tools
- ❌ No LLM-based repair
- ❌ No RL
- ❌ No learned routing
- ❌ No agent orchestration
- ❌ No managed credentials / identity platform
- ❌ No integration marketplace
- ❌ No huge dashboard

---

## 4. Core Failure Taxonomy

Every tool failure becomes a structured object:

```json
{
  "kind": "schema_error",
  "retryable": false,
  "repairable": true,
  "requires_agent": false,
  "safe_to_retry": false,
  "message": "...",
  "details": {}
}
```

### Taxonomy Classes:
1. **`SCHEMA_ERROR`**:
   - Wrong type, missing required argument, invalid enum, malformed date, unknown property.
   - *Provably safe normalization only*: `"42"` $\to$ `42`, `"2026-10-06"` $\to$ normalized ISO date, `"ACTIVE"` $\to$ `"active"` (unique case match).
   - No semantic guessing.
2. **`TRANSIENT_ERROR`**:
   - Timeout, connection reset, temporary 5xx, service unavailable.
   - *Retry only when*: Tool is explicitly declared retryable **AND** operation is idempotent (or idempotency key supplied).
3. **`RATE_LIMIT`**:
   - HTTP 429, quota exceeded.
   - *Resolution*: Exponential backoff + `retry-after` header obedience. Never hammer the endpoint.
4. **`PRECONDITION_ERROR`**:
   - Resource locked, order must exist, customer missing.
   - *Resolution*: Return structured diagnostic information to the agent. Do not invent the missing action.
5. **`AUTHORIZATION_ERROR`**:
   - 401 / 403, permission denied, wrong scope.
   - *Resolution*: No retry, no guessing. Immediate escalation.
6. **`UNKNOWN_STATE`**:
   - Write request $\to$ timeout $\to$ state unknown.
   - *Resolution*: Never retry unless idempotency is strictly guaranteed.
7. **`UNKNOWN`**:
   - Unclassified failure.
   - *Resolution*: Do not intervene. Return diagnostic structured error.

---

## 5. The First Killer Behavior

```
[BEFORE VEYRA]
Agent → bad tool call → tool error → LLM sees error → reasons again → retry → maybe succeeds

[WITH VEYRA]
Agent → bad tool call → VEYRA → safe correction / safe retry → tool succeeds → Agent continues
```

---

## 6. Benchmark & Gate Strategy

### Benchmark Tiers
- **Tier 0 — Unit / Synthetic (Engineering Validation):**
  - 100–500 hand-built cases covering schema, enum, type coercion, dates, timeouts, rate limits, 403s, unknown state, safe vs unsafe retries.
  - Target: `false_intervention = 0`, `unsafe_retry = 0`, `classification_accuracy ≈ 100%`.
- **Tier 1 — ToolMisuseBench (Primary v0.1 Benchmark):**
  - Deterministic and replayable CRUD/retrieval faults across 8,100 tasks.
  - Compare 4 systems: (A) Raw agent, (B) Raw agent + naive retry, (C) Raw agent + structured error feedback, (D) Raw agent + Veyra.
  - Metric: Task success, safety (invalid calls, policy violations, harmful interventions), efficiency, and Boundary Recovery:
    $$\text{BoundaryRecovery} = \frac{\text{failures resolved without agent planning}}{\text{failures eligible for boundary resolution (from fault metadata)}}$$
- **Tier 2 — Real MCP Environment:** MCP-Universe.
- **Tier 3 — MCPMark:** Real heterogeneous applications (filesystem, GitHub, Notion, Playwright, Postgres).
- **Tier 4 — ComplexMCP:** 300 stateful interdependent tools (stress test).
- **Tier 5 — ToolSandbox:** State-dependent workflows.

### Exact Decision Gates
- **Gate 0 (Correctness):** 0 unauthorized executions, 0 unsafe retries, 0 silent semantic repairs.
- **Gate 1 (Product Value):** Demonstrates improved task success or avoided agent re-plans without unacceptable overhead on ToolMisuseBench.
- **Gate 2 (Real-World Relevance):** Evaluated against 3 real MCP catalogs.
- **Gate 3 (Routing):** Routing between valid alternatives only after recovery has proven value.
- **Gate 4 (Learning):** Offline learning (outcome refinement, process graphs, contrastive bandits) only after sufficient trace volume.

---

## 7. Product Interfaces

### Python Function Decorator & Wrapper
```python
from veyra import Veyra

veyra = Veyra()

@veyra.tool(retryable=True, idempotent=True)
def get_customer(customer_id: str):
    ...
```

### Model Context Protocol (MCP) Middleware
```
Existing MCP Client ──▶ Veyra Middleware ──▶ Existing MCP Server
```

### Standard Execution Trace Format
```json
{
  "trace_id": "trc_849201",
  "agent": "agent_alpha",
  "tool_proposed": "get_customer",
  "arguments_proposed": {"customer_id": "42"},
  "tool_resolved": "get_customer",
  "arguments_resolved": {"customer_id": 42},
  "decision": "corrected_and_executed",
  "failure": null,
  "state_before": null,
  "state_after": null,
  "latency_ms": 12,
  "attempt": 1,
  "safe": true,
  "outcome": "success"
}
```

### CLI Diagnostic Surface: `veyra audit`
```bash
veyra audit --traces runs/events.jsonl
```
Summarizes tool calls, failure distributions, automatic recoveries, agent re-plans avoided, and verifies 0 unsafe retries.

---

## 8. Final Frozen Roadmap

- **Week 1 — Core:** Veyra interceptor, Python wrapper, MCP middleware, trace format, failure taxonomy, schema validator, safe retry engine, Tier 0 synthetic benchmark suite.
- **Week 2 — Evidence:** ToolMisuseBench adapter, baseline agents, metrics, fault-by-fault evaluation.
- **Week 3 — Real Environment:** 3 MCP catalogs, real traces, production-like fault scenarios, benchmark report.
- **Week 4 — Release:** Docs, examples, CLI audit, README, PyPI, GitHub release.
