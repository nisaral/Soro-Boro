"""Veyra Config: Declarative Equivalence, Alias, and Fallback Configuration.

Supports defining developer-declared equivalence groups, parameter aliases,
and bounded fallback chains in YAML or JSON, eliminating code changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from soro.registry.tool_registry import ToolDefinition, ToolRegistry


@dataclass
class CapabilityConfig:
    """Configuration for a declared capability group."""

    name: str
    tools: list[str]
    primary_tool: str | None = None
    parameter_aliases: dict[str, dict[str, str]] = field(default_factory=dict)
    fallback_chains: dict[str, list[str]] = field(default_factory=dict)
    idempotent: bool = False
    retryable: bool = False
    risk_class: str = "low"
    permissions: list[str] = field(default_factory=list)


class EquivalenceConfig:
    """Declarative specification of tool equivalence, aliases, and fallbacks."""

    def __init__(self, version: str = "1.0", capabilities: list[CapabilityConfig] | None = None):
        self.version = version
        self.capabilities: list[CapabilityConfig] = capabilities or []

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EquivalenceConfig:
        version = str(data.get("version", "1.0"))
        caps_raw = data.get("capabilities", {})

        caps: list[CapabilityConfig] = []
        if isinstance(caps_raw, dict):
            for cap_name, cdata in caps_raw.items():
                tools = list(cdata.get("tools", []))
                primary = cdata.get("primary_tool") or (tools[0] if tools else None)

                # Process parameter aliases
                # Format can be: {tool_name: {alias: canonical}} or {canonical: [aliases]}
                aliases_raw = cdata.get("parameter_aliases", {})
                norm_aliases: dict[str, dict[str, str]] = {}

                for tool_or_canon, mapping in aliases_raw.items():
                    if isinstance(mapping, dict):
                        # {tool: {alias: canon}}
                        norm_aliases[tool_or_canon] = dict(mapping)
                    elif isinstance(mapping, list):
                        # {canon: [alias1, alias2]} -> apply to all tools in capability
                        for t in tools:
                            if t not in norm_aliases:
                                norm_aliases[t] = {}
                            for alias in mapping:
                                norm_aliases[t][alias] = tool_or_canon

                # Process fallback chains
                fb_raw = cdata.get("fallback_chains") or cdata.get("fallbacks", {})
                norm_fallbacks: dict[str, list[str]] = {}
                if isinstance(fb_raw, dict):
                    for src, tgts in fb_raw.items():
                        norm_fallbacks[src] = list(tgts)
                elif isinstance(fb_raw, list) and primary:
                    norm_fallbacks[primary] = list(fb_raw)

                caps.append(
                    CapabilityConfig(
                        name=cap_name,
                        tools=tools,
                        primary_tool=primary,
                        parameter_aliases=norm_aliases,
                        fallback_chains=norm_fallbacks,
                        idempotent=bool(cdata.get("idempotent", False)),
                        retryable=bool(cdata.get("retryable", False)),
                        risk_class=str(cdata.get("risk_class", "low")),
                        permissions=list(cdata.get("permissions", [])),
                    )
                )

        return cls(version=version, capabilities=caps)

    @classmethod
    def from_json(cls, path_or_str: str | Path) -> EquivalenceConfig:
        p = Path(path_or_str)
        if p.exists():
            content = p.read_text(encoding="utf-8")
        else:
            content = str(path_or_str)
        return cls.from_dict(json.loads(content))

    @classmethod
    def from_yaml(cls, path_or_str: str | Path) -> EquivalenceConfig:
        p = Path(path_or_str)
        if p.exists():
            content = p.read_text(encoding="utf-8")
        else:
            content = str(path_or_str)
        return cls.from_dict(yaml.safe_load(content) or {})

    def apply_to_registry(self, registry: ToolRegistry) -> None:
        """Register all declared equivalence groups, aliases, and fallbacks into ToolRegistry."""
        for cap in self.capabilities:
            if not cap.tools:
                continue

            primary = cap.primary_tool or cap.tools[0]

            # 1. Register tools if not already present
            for tool_name in cap.tools:
                if not registry.has(tool_name):
                    registry.register(
                        ToolDefinition(
                            name=tool_name,
                            idempotent=cap.idempotent,
                            retryable=cap.retryable,
                            risk_class=cap.risk_class,
                            capabilities=[cap.name],
                            permissions=cap.permissions,
                        )
                    )

            # 2. Register equivalence group
            registry.register_equivalence(canonical_name=primary, equivalent_names=cap.tools)

            # 3. Register parameter aliases
            for tool_name, alias_map in cap.parameter_aliases.items():
                registry.register_parameter_aliases(tool_name, alias_map)

            # 4. Register fallback chains
            for src_tool, fallback_list in cap.fallback_chains.items():
                registry.register_fallback_chain(src_tool, fallback_list)


def load_equivalence_config(source: str | Path | dict[str, Any]) -> EquivalenceConfig:
    """Convenience helper to load an EquivalenceConfig from a dict, JSON, or YAML file."""
    if isinstance(source, dict):
        return EquivalenceConfig.from_dict(source)
    p = Path(source)
    if p.suffix in (".yaml", ".yml"):
        return EquivalenceConfig.from_yaml(p)
    if p.suffix == ".json":
        return EquivalenceConfig.from_json(p)
    # Try parsing as YAML/JSON string
    try:
        data = yaml.safe_load(str(source))
        if isinstance(data, dict):
            return EquivalenceConfig.from_dict(data)
    except Exception:
        pass
    return EquivalenceConfig.from_json(str(source))
