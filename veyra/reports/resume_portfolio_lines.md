# Verified Resume & Portfolio Lines

These lines are strictly verified against machine artifacts, regression suites, and the Soro claims ledger.

---

- **Built an MCP server audit CLI and GitHub Action:** JSON-RPC stdio client, schema-based argument synthesis, and a state-diff oracle for idempotency, with golden-file tests against official servers' wire captures; hint semantics follow the MCP spec defaults.
- **Evaluated conformal tool shortlists on a public 505-query benchmark:** across 1,000 random calibration/test splits at nominal $\alpha=0.05$, LAC sets averaged 95.1% coverage with mean set size 2.87 tools (vs. fixed $k=3$ at 91.7% and $k=4$ at 93.7%; intervals overlap).
- **Injected 4,000 transport faults across SQLite, a stdio MCP server, git and a local HTTP ledger under an author-designed fault mix:** 0 duplicates in 2,800 at-risk trials (95% upper bound 0.43% per system, 0.11% pooled) vs. blind retry duplicating all of them; ID-based verification deferred 5.4% to confirmation (30% for opaque tools).
- **Built a validation pipeline that caught my own survey errors (parser bug, static-detector false negatives) before publication, backed by a machine-checked claims ledger.**
