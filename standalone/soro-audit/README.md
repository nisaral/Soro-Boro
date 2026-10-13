# soro-audit: MCP Annotation Linter & Behavioral Verifier

[![CI](https://github.com/nisaral/soro-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/nisaral/soro-audit/actions)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Fast, zero-dependency linter and behavioral verifier for [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers.

---

## Why Audit MCP Server Annotations?

Under the MCP specification (schema `2024-11-05`), tool definitions can declare behavioral hints (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). 

When annotations are omitted, host AI clients (Claude Desktop, Cursor, LibreChat) apply **conservative specification defaults**:
- `readOnlyHint` defaults to `false`.
- `destructiveHint` defaults to `true`.

### The Problem: Confirmation Fatigue & Missed Retries
1. **Confirmation Fatigue:** Because unannotated tools default to non-read-only / destructive, developer desktop clients prompt for interactive confirmation on every single retrieval (e.g., `git status`, `duckduckgo_web_search`, `query_metrics`). Developers end up clicking "Allow" constantly, degrading safety UX.
2. **Unsafe Automated Retries:** If a transient network disconnect occurs during a query or idempotent upsert, AI host clients cannot safely retry the call unless `idempotentHint: true` is explicitly declared.
3. **Contradictory Tool Claims:** Tools that claim `readOnlyHint: true` but silently mutate disk or state represent critical safety risks for autonomous agents.

`soro-audit` solves this by connecting to any MCP server over stdio, inspecting annotations against spec defaults, verifying behavior in ephemeral sandboxes, and generating ready-to-apply patches.

---

## Example Audit Terminal Output

```text
========================================================================
           SORO AUDIT — MCP SERVER LINTER & BEHAVIORAL VERIFIER
========================================================================
Server Command:         node build/index.js
Total Tools:            21
Exercised Tools:        21 / 21 (100.0%)
Missing Annotations:    0 tools without explicit hints
Unsafe Contradictions:  0 (declared safe, observed mutating)
Confirmation Fatigue:   0 (verified read-only, missing readOnlyHint)
Total Discrepancies:    0
Elapsed Time:           0.412s
------------------------------------------------------------------------
STATUS: PASS (Clean annotations and behavioral alignment)
========================================================================
```

When run against an unannotated or misconfigured server:

```text
------------------------------------------------------------------------
TOOL                       DECLARED       OBSERVED           STATUS      
------------------------------------------------------------------------
web_search                 default        read_only          FLAGGED     
  [!] CONFIRMATION FATIGUE: Verified read-only in sandbox, but readOnlyHint is false/omitted (causes unnecessary user approval prompts)
  [+] SUGGESTED PATCH: readOnlyHint=True
delete_item                default        destructive_write  OK          
  [*] SPEC CONSERVATIVE DEFAULT: destructiveHint omitted; defaults to True per spec
append_log                 idempotent     non_idempotent     FLAGGED     
  [!] CRITICAL UNSAFE CONTRADICTION: Declared idempotentHint: true, but observed non_idempotent_mutation
------------------------------------------------------------------------
```

---

## Quickstart

### 1. Installation

Install via pip (zero external dependencies, standard library only):

```bash
pip install soro-audit
```

### 2. Local CLI Usage

Audit any MCP server over stdio:

```bash
# Schema & Spec Default Audit (dry-run, no tool calls)
soro-audit --stdio "npx my-mcp-server" --dry-run

# Full Dynamic Behavioral Verification (runs in ephemeral sandbox)
soro-audit --stdio "npx my-mcp-server"

# Generate GitHub Step Summary and JSON output
soro-audit --stdio "node dist/index.js" --markdown audit_summary.md --json audit_report.json
```

### 3. GitHub Action in CI

Add `soro-audit` to your server's CI pipeline with zero elevated permissions (`contents: read`):

```yaml
name: MCP Annotation Audit

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build MCP Server
        run: npm ci && npm run build

      - name: Audit MCP Tool Annotations
        uses: nisaral/soro-audit@v0.1.0
        with:
          command: "node build/index.js"
          dry-run: "true"
          strict: "true"
```

The action automatically writes rich markdown tables directly to `$GITHUB_STEP_SUMMARY`.

---

## Command-Line Reference

| Flag | Default | Description |
| :--- | :---: | :--- |
| `--stdio <CMD>` | *required* | Subprocess command to launch the MCP server over stdio |
| `--dry-run` | `false` | Run static schema and spec default check without calling tools |
| `--strict` | `false` | Return exit code `1` if any unannotated hints or contradictions are found |
| `--markdown <PATH>` | `None` | Export GitHub Flavored Markdown audit summary table |
| `--json <PATH>` | `None` | Export full structured machine-readable JSON report |
| `--timeout <SEC>` | `15.0` | Maximum timeout in seconds per RPC handshake |
| `--allow-dirty-env` | `false` | Allow execution when ambient cloud/production credentials exist |

---

## Safety & Credential Isolation Invariants

1. **Ambient Secret Rejection:** `soro-audit` strictly checks for production secrets (`AWS_ACCESS_KEY_ID`, `STRIPE_SECRET_KEY`, `GITHUB_TOKEN`, etc.). If present, the audit halts with a safety refusal unless `--allow-dirty-env` is provided.
2. **Ephemeral CWD Sandboxing:** Dynamic invocations execute inside temporary directories (`tempfile.mkdtemp`) with scrubbed environment variables.
3. **Accounting Integrity:** A tool that returns `isError: true` during argument testing is explicitly classified as **Unexercised/Skipped**, never falsely reported as verified.

---

## License

Apache-2.0. See [LICENSE](LICENSE) for details.
