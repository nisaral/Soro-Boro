# Veyra eval lab

Local tools and MCP stubs for UNKNOWN_ACK and filesystem pilots. No proxy. Secrets stay in `.env`.

- `tools/payment.py` — non-idempotent transfer + read-only verify
- `contracts/payment.yaml` — side-effect class and verify hook
- `faults/` — timeout-after-commit
- Odyssey: `ODYSSEY_API_KEY` via `os.environ`; LM Studio fallback
