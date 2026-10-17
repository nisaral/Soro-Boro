"""Veyra Registry: Tool Metadata and Declared Equivalence Registry.

Maintains normalized tool definitions, permissions, protocol, and developer-declared equivalence groups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDefinition:
    """Registered metadata for an executable tool."""

    name: str
    schema: dict[str, Any] | None = None
    executable: Callable[..., Any] | None = None
    retryable: bool = False
    idempotent: bool = False
    risk_class: str = "low"  # low | medium | high | destructive
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    protocol: str = "python"  # python | mcp
    healthy: bool = True
    # Phase 14 Execution Contract metadata fields
    required_state: dict[str, Any] = field(default_factory=dict)
    freshness_sec: float | None = None
    consistency: str = "any"
    side_effect_class: str = "read_only"
    expected_output: str | None = None
    cost: float = 0.0
    latency_ms: float = 0.0
    reliability: float = 1.0
    provenance: str = "declared"
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """Central registry of known tools and declared equivalence groups."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        # Equivalence mappings: canonical_name -> list of equivalent tool names
        self._equivalences: dict[str, list[str]] = {}
        # Reverse mapping: tool_name -> canonical_name
        self._canonical_lookup: dict[str, str] = {}
        # Parameter aliases: tool_name/canonical -> {alias_key: canonical_key}
        self._param_aliases: dict[str, dict[str, str]] = {}
        # Bounded fallback chains: primary_tool -> [fallback_1, fallback_2]
        self._fallback_chains: dict[str, list[str]] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def register_equivalence(self, canonical_name: str, equivalent_names: list[str]) -> None:
        """Explicitly declare equivalent tools (e.g. ['crm.get_customer', 'legacy.get_customer']).

        CRITICAL: No automatic semantic discovery. Only developer-declared equivalence.
        """
        all_members = [canonical_name] + [name for name in equivalent_names if name != canonical_name]
        self._equivalences[canonical_name] = all_members
        for name in all_members:
            self._canonical_lookup[name] = canonical_name

    def get_equivalents(self, name: str) -> list[str]:
        """Return all declared equivalent tools for a given tool name."""
        canonical = self._canonical_lookup.get(name, name)
        return self._equivalences.get(canonical, [name])

    def register_parameter_aliases(self, tool_name: str, alias_map: dict[str, str]) -> None:
        """Register explicit parameter aliases (e.g. {'account_id': 'id', 'filename': 'path'})."""
        self._param_aliases[tool_name] = dict(alias_map)

    def get_parameter_aliases(self, tool_name: str) -> dict[str, str]:
        """Return parameter alias mappings for a tool or its canonical equivalent."""
        canonical = self._canonical_lookup.get(tool_name, tool_name)
        merged = {}
        if canonical in self._param_aliases:
            merged.update(self._param_aliases[canonical])
        if tool_name in self._param_aliases:
            merged.update(self._param_aliases[tool_name])
        return merged

    def register_fallback_chain(self, primary_tool: str, fallback_tools: list[str]) -> None:
        """Register ordered bounded fallback chain (e.g. ['query_primary_db', 'query_replica_db'])."""
        self._fallback_chains[primary_tool] = list(fallback_tools)

    def get_fallback_chain(self, primary_tool: str) -> list[str]:
        """Return declared fallback chain for a tool."""
        return self._fallback_chains.get(primary_tool, [])

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())
