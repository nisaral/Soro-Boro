# Security

## Reporting

Please report vulnerabilities privately via GitHub's "Report a vulnerability" (Security →
Advisories) on the repository, or email the maintainers listed on the GitHub profile. Do not open
a public issue for a live vulnerability. Expect an acknowledgement within a few days.

## Threat model

Veyra executes model-proposed actions against a workspace. The intended deployment for v0.1 is a
developer machine or a CI job running **trusted** benchmark tasks.

Controls that exist:

- **Workspace confinement.** File tools resolve paths and refuse anything outside the task
  workspace (`veyra.tools._safe_path`), including absolute paths.
- **Command allowlist.** `run_command` accepts only a small prefix allowlist and refuses
  everything else *before* spawning a shell.
- **No ambient credentials.** The offline benchmark mode makes no network calls. Live model modes
  (`ollama`, `openai`) talk only to the configured endpoint.
- **Loopback gRPC.** The kernel and sidecar bind to `127.0.0.1` by default and use insecure
  transport, which is appropriate only for a local, single-user setup.
- **Deterministic verification.** Success is decided by a grader that inspects the workspace, not
  by a model's opinion of its own work.

## Known limitations (please read)

- The shell allowlist and path checks are **defence in depth, not a sandbox**. A shell command the
  allowlist permits can still do damage within its own privileges, and `python -c`-style execution
  is not reachable but `python <file>` is. Run untrusted tasks in a container or VM with a
  read-only root and no network.
- `allow_shell` defaults to enabled because the benchmark needs it. Set `--no-shell` for
  filesystem-only work.
- The gRPC channel is unauthenticated. Do not expose the kernel or sidecar port beyond loopback.
- Event logs and checkpoints contain task text and tool output. Treat run directories as
  sensitive if your tasks contain secrets.
- Budgets are accounting limits, not security boundaries: they stop a run, they do not contain it.
