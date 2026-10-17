# Veyra Changelog

## [0.2.0] - 2026-10-07

### Added
- **Unified Veyra Python Surface (`from veyra import Veyra`)**: `wrap()`, `wrap_mcp()`, `wrap_http()`, and `wrap_agent()`.
- **Framework Integrations**: Built-in adapters for OpenAI Agents SDK, LangGraph, AutoGen, and Microsoft Agent Framework.
- **Veyra MCP Proxy (`veyra proxy mcp`)**: Stdio and Streamable HTTP execution control proxy between MCP clients and servers.
- **Configuration Subsystem (`veyra config validate`, `veyra config explain`)**: Human-readable YAML configuration parsing, policy validation, and active policy explanation.
- **Plugin System (`@veyra_plugin`)**: Extensible metadata-driven plugin registry for custom policies, adapters, and verification hooks.
- **Replay & Diff Subsystem (`veyra replay`, `veyra diff`)**: Safe dry-run trajectory reconstruction and step-by-step diffing.
- **Production Execution Modes**: Support for `NORMAL`, `SHADOW`, `DRY_RUN`, `FAIL_CLOSED`, and `FAIL_OPEN` execution modes.
- **Idempotency Store Abstraction**: `InMemoryIdempotencyStore`, `SQLiteIdempotencyStore`, `FileIdempotencyStore`.
- **Production CLI (`veyra`)**: Full-featured CLI for configuration, inspection, policy linting, tracing, replay, diffing, proxying, and benchmarking.
