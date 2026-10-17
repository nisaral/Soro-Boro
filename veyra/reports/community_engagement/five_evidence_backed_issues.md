# MCP Community Maintenance Triage: Verified Targets & Dropped Candidates

This report records the rigorous ground-truth verification of candidate MCP repositories for community pull requests. Candidates were evaluated against live stdio JSON-RPC wire inspection, active repository maintenance, and reproducible test suites.

---

## 1. Surviving Verified PR Candidates

### Candidate 1: `ericthered926/duckduckgo-mcp-server`
- **Ecosystem Footprint:** ~30,000 downloads/week.
- **Repository Status:** Active, open issues: 2, last commit: recent.
- **Tools Evaluated:** `duckduckgo_web_search`, `duckduckgo_news_search` (2 tools total).
- **Unpatched Wire Capture:** [`raw_wire_duckduckgo_tools_list.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/raw_wire_duckduckgo_tools_list.json).
  - Both tools completely omit the `annotations` property over the wire (defaulting to unannotated `readOnlyHint: false, destructiveHint: true`).
- **Complete Scope:** Both tools classified and annotated in a single PR:
  ```json
  "annotations": {
    "readOnlyHint": true,
    "destructiveHint": false,
    "idempotentHint": true,
    "openWorldHint": true
  }
  ```
- **Test Suite Results:** Native test suite in `test/server.test.js` updated with assertions.
  - Command: `node --test test/server.test.js`
  - Result: **5 passed, 0 failed** in 4.8s.
- **Clean Diff:** [`patch_duckduckgo_mcp_server.diff`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/patch_duckduckgo_mcp_server.diff) (generated via `git diff`).
- **Patched Wire Capture:** [`raw_wire_duckduckgo_patched.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/raw_wire_duckduckgo_patched.json).

---

### Candidate 2: `winor30/mcp-server-datadog`
- **Ecosystem Footprint:** ~31,000 downloads/week.
- **Repository Status:** Active, open issues: 3, last commit: recent.
- **Tools Evaluated:** All 21 tools across 9 domain modules:
  - 17 Read-Only Query Tools: `list_incidents`, `get_incident`, `query_metrics`, `get_logs`, `get_all_services`, `get_monitors`, `list_dashboards`, `get_dashboard`, `list_traces`, `list_hosts`, `get_active_hosts_count`, `list_downtimes`, `get_rum_applications`, `get_rum_events`, `get_rum_grouped_event_count`, `get_rum_page_performance`, `get_rum_page_waterfall`.
  - 4 Mutating Action Tools: `schedule_downtime`, `cancel_downtime` (destructive), `mute_host`, `unmute_host`.
- **Infrastructure Change:** Updated `src/utils/tool.ts` `createToolSchema` to accept optional `annotations?: ToolAnnotations` and spread `...(annotations ? { annotations } : {})`.
- **Complete Scope:** All 21 tools classified and annotated across all 9 domain modules in one complete PR.
- **Test Suite Results:**
  - Unit test in `tests/utils/tool.test.ts` verifying annotations preservation: **2 passed, 0 failed** in `vitest`.
  - Full TypeScript build via `tsup`: **Build success (code 0)** producing `build/index.js` (36.28 KB).
- **Clean Diff:** [`patch_datadog_mcp_server.diff`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/patch_datadog_mcp_server.diff) (generated via `git diff`).
- **Patched Wire Capture:** [`raw_wire_datadog_patched.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/raw_wire_datadog_patched.json) (captured live stdio JSON-RPC handshake verifying all 21 tools).

---

## 2. Dropped Candidates & Factual Rationale

| # | Candidate Package | Reason for Dropping | Evidence / Verification Method |
| :---: | :--- | :--- | :--- |
| 1 | `@cyanheads/git-mcp-server` | **Already Fully Annotated** | Live wire capture saved in [`raw_wire_cyanheads_git-mcp-server.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/raw_wire_cyanheads_git-mcp-server.json). All 28 tools (`git_status`, `git_log`, `git_diff`, etc.) already declare `readOnlyHint: true`. |
| 2 | `mcp-server-docker` | **Unverified Runtime Dependency** | Server requires an active Docker daemon. Wire execution was not observed in a verified live environment. Dropped under the strict ground-truth rule. |
| 3 | `@modelcontextprotocol/server-fetch` | **Package 404 / Prior Upstream Commit** | npm package `@modelcontextprotocol/server-fetch` does not exist (HTTP 404). The reference Python implementation (`mcp-server-fetch`) already declared annotations in source (`src/mcp_server_fetch/server.py`). Dropped without speculative PR citation. |
| 4 | `@modelcontextprotocol/server-brave-search` | **Archived / Deprecated** | Repository is deprecated in favor of external Brave search servers; submitting maintenance PRs to deprecated repositories creates noise. |
| 5 | `@modelcontextprotocol/server-memory` | **Intentional Spec Design** | `create_entities` explicitly declares `idempotentHint: false` in upstream source. While entity upserts merge properties, the maintainers deliberately opted for a conservative non-idempotent annotation. This is a design preference, not an unannotated defect. |
