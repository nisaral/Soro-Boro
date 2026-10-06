"""Veyra Core: ExecutableAction abstraction.

Represents an action proposed by an agent or resolved by Veyra.
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
        return bool(self.metadata.get("idempotent", False))

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "metadata": {k: v for k, v in self.metadata.items() if k != "executable"},
        }
