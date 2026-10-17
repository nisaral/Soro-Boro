# Soro-Boro: System Objective & Execution Boundary Specification

> **Find which agent tools are unsafe to retry, then make them safe.**

Soro-Boro sits between the agent framework and external tools/services, resolving ambiguous execution states and eliminating duplicate side-effects.

```text
Agent / Host (LangGraph, CrewAI, AutoGen, MCP client)
        │ proposed tool action
        ▼
┌────────────────────────────────────────────────────────┐
│  SORO-BORO EXECUTION BOUNDARY                           │
│  1. Mint durable OperationIdentity per workflow intent │
│  2. Acquire atomic cross-process claim lease           │
│  3. Synchronously flush intent to WAL (fsync)          │
│  4. Dispatch external mutation                         │
│  5. UNKNOWN_ACK → reconcile or AMBIGUOUS_DEFERRED     │
│  6. Release claim & persist verifiable outcome         │
└────────────────────────────────────────────────────────┘
        │
   Tools / MCP / HTTP / SQL
```

---

## What Soro-Boro Is

1. **An Audit Tool (`soro-audit`)**: Scans MCP servers and agent tool definitions to uncover missing idempotency declarations, hidden mutations, and unhandled retry loops.
2. **An Execution Boundary SDK (`soro_boro`)**: Wraps consequential mutations across non-keyed services (SQL, GitHub, Slack, webhooks) with atomic claims and durable Write-Ahead Logging.
3. **Fail-Closed on Uncertainty**: Unlike naive retries or receipt-only wrappers, Soro-Boro returns an explicit `AMBIGUOUS_DEFERRED` outcome whenever read replica lag or probe errors make upstream state uncertain.

---

## What Soro-Boro Is Not

- **Not an LLM router or prompt gateway**: Execution safety and deduplication are deterministic systems problems, not prompt-engineering problems.
- **Not a workflow graph engine**: Soro-Boro does not schedule agent DAGs (like Temporal or LangGraph); it protects the execution boundary of individual tools.
- **Not a synthetic claim**: All claims are validated against real distributed failure modes (dropped ACKs, replica lag, probe 500s, concurrency races) on services lacking native idempotency keys.

---

## Key Invariants

1. **Operation Identity**: Derived once from workflow position, not token arguments. Mismatched arguments on replay trigger `MismatchedParametersError`.
2. **Key Expiration**: Keys older than provider retention windows (e.g. 24h) cannot be re-dispatched automatically.
3. **Authoritative Reconciliation**: Reconcilers query specific entities with op markers. `NOT_FOUND` is non-authoritative by default under eventual consistency.
4. **Mutual Exclusion**: Cross-process atomic claim leases prevent racing parallel executions.
