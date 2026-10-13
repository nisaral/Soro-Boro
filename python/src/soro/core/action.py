"""Veyra Core: ExecutableAction abstraction.

Represents an action proposed by an agent or resolved by soro.
Independent of any specific transport (Python function, MCP, RPC).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ExecutableAction:
    """Core action unit in Veyra execution boundary."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    executable: Callable[..., Any] | None = None

    @property
    def is_idempotent(self) -> bool:
        return bool(self.metadata.get("idempotent", self.metadata.get("is_idempotent", False)))

    @property
    def is_retryable(self) -> bool:
        return bool(self.metadata.get("retryable", False))

    @property
    def risk_class(self) -> str:
        return str(self.metadata.get("risk_class", "low"))

    @property
    def capabilities(self) -> list[str]:
        return list(self.metadata.get("capabilities", []))

    @property
    def required_permissions(self) -> list[str]:
        return list(self.metadata.get("permissions", []))

    @property
    def equivalence_group(self) -> str | None:
        return self.metadata.get("equivalence_group")

    @property
    def capability(self) -> str | None:
        return self.metadata.get("capability")

    @property
    def required_state(self) -> dict[str, Any]:
        return dict(self.metadata.get("required_state", {}))

    @property
    def freshness_sec(self) -> float | None:
        return self.metadata.get("freshness_sec") or self.metadata.get("freshness")

    @property
    def consistency(self) -> str:
        return str(self.metadata.get("consistency", "any"))

    @property
    def permission_scope(self) -> list[str]:
        return list(self.metadata.get("permission_scope", self.required_permissions))

    @property
    def side_effect_class(self) -> str:
        return str(self.metadata.get("side_effect_class", "read_only" if self.is_idempotent else "mutation"))

    @property
    def expected_output(self) -> str | None:
        return self.metadata.get("expected_output")

    @property
    def cost(self) -> float:
        return float(self.metadata.get("cost", 0.0))

    @property
    def latency_ms(self) -> float:
        return float(self.metadata.get("latency_ms", 0.0))

    @property
    def reliability(self) -> float:
        return float(self.metadata.get("reliability", 1.0))

    @property
    def protocol(self) -> str:
        return str(self.metadata.get("protocol", "python"))

    @property
    def provenance(self) -> str:
        return str(self.metadata.get("provenance", "declared"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "metadata": {k: v for k, v in self.metadata.items() if k != "executable"},
        }
