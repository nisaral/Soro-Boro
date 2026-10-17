# Community Engagement & Two-Week Stop Rule Tracker

**Two-Week Clock Start Date:** *Pending first PR submission*  
**Evaluation Stop Date:** *TBD (+14 days)*  
**Decision Criteria:**
- **Continue if:** $\ge 2$ PRs merge, OR $\ge 3$ maintainers engage constructively, OR $\ge 5$ outsiders run the audit.
- **Wrap up if:** Thresholds not met after 14 days. Deliver clean repository, methodology write-up, conformal routing evaluation, and honest negative results.

---

## 1. Outgoing Pull Requests & Issues

| # | Repository | Target Branch | Type | Description | Raw Wire Evidence | Diff / Tests | Status | Maintainer Response |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `ericthered926/duckduckgo-mcp-server` | `main` | PR | Add explicit MCP annotations (`readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: true`) to both `duckduckgo_web_search` and `duckduckgo_news_search` + unit assertions | [`raw_wire_duckduckgo_tools_list.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/raw_wire_duckduckgo_tools_list.json) & [`raw_wire_duckduckgo_patched.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/raw_wire_duckduckgo_patched.json) | [`patch_duckduckgo_mcp_server.diff`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/patch_duckduckgo_mcp_server.diff) (5/5 passed in `node --test`) | Ready to Submit | Awaiting post |
| 2 | `winor30/mcp-server-datadog` | `main` | PR | Add `ToolAnnotations` parameter to `createToolSchema` utility and classify all 21 tools (17 read-only query tools, 4 mutating tools: `schedule_downtime`, `cancel_downtime`, `mute_host`, `unmute_host`) + unit tests | [`raw_wire_datadog_patched.json`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/raw_wire_datadog_patched.json) (all 21 live tools captured) | [`patch_datadog_mcp_server.diff`](file:///c:/Users/nisar/OneDrive/Desktop/EB-JEPA/veyra/reports/patch_datadog_mcp_server.diff) (vitest passed, tsup built) | Ready to Submit | Awaiting post |

---

## 2. Outsider Audit Runs

| # | Date | User / Repository | Mode (`dry-run` vs dynamic) | Result Summary | Source Link |
| :---: | :---: | :--- | :---: | :--- | :--- |
| 1 | — | *Awaiting public release* | — | — | — |

---

## 3. Weekly Status Log

- **Week 1 Status:** *Clock begins upon PR submission.*
- **Week 2 Status:** *TBD*
