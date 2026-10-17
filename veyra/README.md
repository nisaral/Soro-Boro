# Soro

> **The Type-Safe MCP & Agent Tool Harness.**
> Stop runaway LLM duplicate tool loops, auto-repair broken JSON arguments, and audit MCP servers for reliability.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/nisaral/Soro-Boro/actions/workflows/ci.yml/badge.svg)](https://github.com/nisaral/Soro-Boro/actions)

---

## Why Soro?

When AI agents use tools in production, three things routinely break:
1. **Runaway LLM Duplicate Loops**: An LLM gets confused or loops across conversational turns, repeatedly calling `charge_card()` or `create_ticket()` with the same parameters.
2. **Brittle Argument Formatting**: The LLM passes `"49.99"` instead of `49.99`, `'{"items": [1, 2]}'` as a raw string instead of a dictionary, or `orderId` instead of `order_id`, causing runtime `TypeError` crashes.
3. **Unchecked MCP Tool Servers**: Third-party Model Context Protocol (MCP) servers omit safety hints (`readOnlyHint`, `idempotentHint`), causing constant approval popup fatigue in Cursor / Claude Desktop or blind retries during network hiccups.

**Soro solves all three in a unified, lightweight package.**

---

## 3 Core Features

### 1. `soro-audit` — Test Any MCP Server in 10 Seconds
A standalone CLI chaos and schema linter for Model Context Protocol servers. It connects over `stdio`, tests schemas, verifies behavior in an isolated sandbox, and outputs instant patches.

```bash
# Run schema and annotation audit on any server
soro-audit --stdio "npx -y @modelcontextprotocol/server-filesystem /tmp" --dry-run

# Run dynamic behavioral verification
soro-audit --stdio "node dist/index.js" --markdown audit_summary.md
```

> **Real-World Census**: We audited **359 public MCP servers** ([see census report](reports/mcp_live_census_report.json)) and found that **over 40% omit `readOnlyHint`**, causing AI desktop clients to prompt for user approval on harmless search queries. We generated instant fix patches for servers like [Datadog](reports/patch_datadog_mcp_server.diff) and [DuckDuckGo](reports/patch_duckduckgo_mcp_server.diff).

---

### 2. `@soro_wrap` — Stop LLM Double-Calls & Retry Double-Writes
Add a 1-line decorator to any tool. Soro automatically caches successful writes in a 120-second sliding loop guard and guards against network timeout double-writes:

```python
from soro import soro_wrap

@soro_wrap(side_effect="mutation")
def refund_customer(order_id: str, amount: float):
    return stripe.Refund.create(charge=order_id, amount=int(amount * 100))

# Turn 1: Normal execution
res1 = refund_customer("ord_101", 50.0)

# Turn 2: LLM gets stuck in a loop and calls it again with identical arguments
res2 = refund_customer("ord_101", 50.0)
# -> Stopped automatically! Returns PREVENTED_DUPLICATE with cached result.
```

---

### 3. `SoroHarness` — Route -> Repair -> Guard in 5 Lines
A complete, type-safe pipeline that routes natural language queries, auto-repairs LLM argument types, and executes with loop guard protection:

```python
from soro import SoroHarness

harness = SoroHarness()

@harness.tool(description="Process customer refund", side_effect="mutation")
def refund(order_id: str, amount: float, reason: str = "customer_request"):
    return {"status": "ok", "order_id": order_id, "amount": amount}

# 1. Automatic Argument Repair: Coerces strings to floats & camelCase to snake_case!
res = harness.execute("refund", {"orderId": "ord_882", "amount": "99.50"})
print(res.data)
# {'status': 'ok', 'order_id': 'ord_882', 'amount': 99.5}

# 2. Natural Language Routing + Auto-Repair + Loop-Guard:
res = harness.run("Please refund order ord_99 for 25 dollars", {"orderId": "ord_99", "amount": "25"})
```

---

## Installation

```bash
# Install Soro tool harness & boundary SDK
pip install -e "./python[dev]"

# Or run the standalone zero-dependency MCP auditor directly
pip install soro-audit
```

---

## Pipeline Architecture

```text
User / Agent Query
        │
        ▼
┌────────────────────────────────────────────────────────┐
│  1. ROUTE: Local Conformal Router (Fast Shortlisting)  │
│  2. REPAIR: Auto-Coerce Types & JSON Schema (Kev)      │
│  3. GUARD: Soro-Boro Boundary & 120s Loop Guard        │
└────────────────────────────────────────────────────────┘
        │
   Protected External Execution (API / SQL / MCP / HTTP)
```

---

## Repository Structure

- `python/src/soro/harness/`: Unified `SoroHarness` pipeline (`Route -> Repair -> Guard`).
- `python/src/soro_boro/`: Execution boundary engine (`@soro_wrap`, atomic claim store, intent minting).
- `python/src/soro/cli_audit.py`: `soro-audit` MCP server linter and behavioral sandbox verifier.
- `reports/`: Real findings across 359 MCP servers (`mcp_live_census_report.json` and generated patches).
- `web/`: Next.js interactive architecture visualization and simulator demo.

---

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
