# Security Policy

## Reporting Security Issues

Please report vulnerabilities privately via GitHub Security Advisories or email the maintainer. Do not file public issues for active security vulnerabilities.

---

## Security Model & Audit Safety

`soro-audit` inspects and verifies Model Context Protocol (MCP) servers. Because MCP servers can register tools with file or network side effects, `soro-audit` enforces strict safety invariants:

### 1. Ambient Credential Isolation
Dynamic tool execution strictly forbids ambient production credentials. By default, `soro-audit` inspects the environment for cloud and production tokens (`AWS_ACCESS_KEY_ID`, `STRIPE_SECRET_KEY`, `GITHUB_TOKEN`, `DATABASE_URL`, etc.). If production tokens are present, the CLI refuses execution (`PermissionError`) unless `--allow-dirty-env` is explicitly provided. Subprocesses are executed in scrubbed environments (`create_scrubbed_env`).

### 2. Ephemeral Sandbox Execution
When verifying tools dynamically, arguments are synthesized against isolated temporary directories (`tempfile.mkdtemp`), preventing modifications to host user files or configuration.

### 3. Static Dry-Run Separation
When `--dry-run` is active (the default in CI), tools are analyzed purely from their JSON-RPC `tools/list` schema and description without calling `tools/call`. No side effects occur on the host machine.
