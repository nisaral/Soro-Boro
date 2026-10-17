# Veyra Repository Architecture Tree Audit (v0.2.0)

**Date:** October 7, 2026  
**Status:** Canonical Package Consolidation  

---

## 1. Canonical Production Surface (Python Package: `veyra`)

The official production execution middleware surface resides under `python/src/veyra/`:

```text
python/src/veyra/
├── __init__.py                     # Canonical Veyra class and public API exports
├── cli.py                          # Unified Veyra CLI entry point
├── config.py                       # Human-readable YAML/JSON config manager & validator
├── core/                           # Core execution semantics (Frozen Core)
│   ├── __init__.py
│   ├── action.py                   # ExecutableAction definition
│   ├── contract.py                 # ExecutionContract & ResolutionContract
│   ├── state.py                    # ExecutionState & environment context
│   ├── decision.py                 # Decision & RecoveryDecision representations
│   ├── policy.py                   # RoutePolicy & PolicySet abstractions
│   ├── resolution.py               # PolicyAware & VeyraResolver engines
│   ├── recovery.py                 # RecoveryPolicy & SafeRecoveryPolicy
│   ├── transaction.py              # Transaction state machine & UNKNOWN_ACK
│   ├── idempotency.py              # Strong idempotency key store (In-Memory/SQLite/File)
│   └── partial_mutation.py         # Partial mutation reconciliation & compensation
├── middleware/                     # Execution boundary wrappers
│   ├── __init__.py
│   ├── function.py                 # Function/decorator wrapper veyra.wrap()
│   ├── mcp.py                      # MCP proxy & interceptor
│   └── http.py                     # HTTP client wrapper
├── policies/                       # Policy packs & composable policies
│   ├── __init__.py
│   ├── base.py                     # BasePolicy
│   ├── safety.py                   # Strict, ReadOnly, Production policy packs
│   ├── retry.py                    # RetryPolicy
│   ├── freshness.py                # FreshnessPolicy
│   ├── authorization.py            # AuthorizationPolicy & RBAC
│   └── routing.py                  # RoutingPolicy
├── adapters/                       # Protocol adapters
│   ├── __init__.py
│   ├── mcp.py                      # MCP protocol adapter
│   ├── http.py                     # HTTP protocol adapter
│   └── python.py                   # Standard Python callable adapter
├── integrations/                   # First-party agent framework integrations
│   ├── __init__.py
│   ├── openai_agents.py            # OpenAI Agents SDK integration
│   ├── langgraph.py                # LangGraph node & tool wrapper
│   ├── autogen.py                  # AutoGen middleware wrapper
│   ├── microsoft_agent_framework.py # Microsoft Agent Framework middleware
│   └── generic.py                  # Generic Python decorator wrapper
├── observability/                  # Observability & Tracing
│   ├── __init__.py
│   ├── tracing.py                  # TraceSink & execution trace models
│   ├── audit.py                    # Cryptographic hash-chain audit log
│   └── events.py                   # Observability events (JSONL & OpenTelemetry)
├── plugins/                        # Lightweight plugin discovery system
│   ├── __init__.py
│   └── registry.py                 # Plugin discovery via packaging entry points
├── replay/                         # Replay & Debugging
│   ├── __init__.py
│   ├── runner.py                   # Trajectory replay engine (DRY_RUN / --execute)
│   └── diff.py                     # Trajectory diff tool
└── benchmarks/                     # Public benchmark runners
    ├── __init__.py
    └── framework.py                # veyra bench CLI runner
```

---

## 2. Directory Classification Ledger

| Directory | Classification | Status & Purpose |
| :--- | :---: | :--- |
| `python/src/veyra/` | **ACTIVE** | Canonical v0.2.0 Python production SDK, in-process middleware, CLI, and integrations. |
| `python/tests/` | **ACTIVE** | Core unit, integration, property, and boundary safety test suite (`261 passed`). |
| `benchmarks/adapters/` | **ACTIVE** | Official public benchmark adapters (UndoBench, ToolMisuseBench). |
| `benchmarks/resolution/` | **ACTIVE** | Veyra internal 240-scenario resolution evaluation harness. |
| `benchmarks/results/` | **ACTIVE** | Audited raw trajectory JSON artifacts. |
| `reports/` | **ACTIVE** | Executive audit reports, scorecards, and final validation decisions. |
| `examples/` | **ACTIVE** | Runnable product demonstrations working from fresh checkouts. |
| `legacy/` | **LEGACY** | Archived pre-v0.2 research code, Go prototypes, and unmaintained scripts. |
| `experimental/` | **EXPERIMENTAL** | Non-production research explorations. |

---

## 3. Public Surface Consolidation Guarantee

A developer installing `veyra` via `pip install veyra` interacts with:
1. `from veyra import Veyra` (Canonical Python SDK: `@veyra.wrap`, `wrap_mcp`, `wrap_http`, `wrap_agent`)
2. In-process middleware interceptors (primary architecture)
3. `veyra` CLI (`veyra doctor`, `veyra config explain`, `veyra replay`, etc.)
4. `veyra proxy mcp` (Optional compatibility utility for external processes; not an API gateway product)
