# Soro MCP Server Audit Action

Automated CI linter and behavioral verification action for Model Context Protocol (MCP) servers.

Catches missing annotations, spec default risks, and behavioral discrepancies on pull requests before they reach host agent clients (Claude Desktop, Cursor, LibreChat).

---

## 5-Minute Quickstart

Add this workflow to your repository under `.github/workflows/mcp_audit.yml`:

```yaml
name: "MCP Server Audit"

on:
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Audit MCP Server
        uses: soro-boro/mcp-audit-action@v0.1
        with:
          command: "node dist/index.js"
          strict: "false"
```

The action runs the audit and outputs a structured Markdown report directly into your GitHub Actions **Run Summary (`$GITHUB_STEP_SUMMARY`)**.

---

## What `--dry-run` Does and What It Skips

The audit operates in two modes:

| Mode | What It Tests | What It Skips | Use Case |
| :--- | :--- | :--- | :--- |
| **`--dry-run` (Schema & Spec Mode)** | Spawns server, completes JSON-RPC handshake, fetches `tools/list`. Audits declared annotations (`readOnlyHint`, `idempotentHint`, `destructiveHint`, `openWorldHint`) against MCP spec defaults (schema `2024-11-05`). Identifies unannotated query tools that trigger user confirmation prompts. | **Skips all tool executions (`tools/call`).** Does not synthesize parameters or inspect runtime state/disk mutations. | Safe for all CI environments without credentials or sandbox isolation. |
| **Full Behavioral Mode (Dynamic)** | In addition to schema audit, synthesizes schema-conforming test arguments, executes consecutive calls in an isolated scratch sandbox, and runs a state-diff oracle. | Skips tools whose schemas require unsupported external types or ambient API keys. | Full end-to-end verification of tool idempotency and read-only invariants. |

> **Audit Rule:** *A skipped tool is not a verified tool.* Dry-run reports explicitly mark tools as `Skipped (dry_run_requested)` with `0 / N exercised`.

---

## Action Inputs

| Input | Description | Required | Default |
| :--- | :--- | :---: | :---: |
| `command` | Command to start the MCP server over stdio (e.g. `node dist/index.js` or `python -m my_server`) | Yes | — |
| `strict` | Fail the workflow (exit code 1) if any missing hints or discrepancies are found | No | `false` |
| `dry-run` | Run schema and spec analysis without invoking dynamic tools | No | `true` |
| `profile` | Path to custom YAML audit profile | No | `""` |

---

## Action Outputs

| Output | Description |
| :--- | :--- |
| `audit-summary` | Full markdown audit summary table |
| `exit-code` | Exit code: `0` (clean), `1` (discrepancies found under strict mode), `2` (server execution failure) |

---

## Security & Fork Permissions

This action runs with **read-only permissions (`contents: read`)** and requires **zero secrets or tokens**. It writes results directly to `$GITHUB_STEP_SUMMARY` and uploads artifact files, ensuring safe execution on fork pull requests without exposing repository permissions.
