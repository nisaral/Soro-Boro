"""Microsoft Agent Framework middleware adapter for soro.

Exposes function-call middleware providing Veyra's contract validation, state management, transaction safety, and recovery.
"""

from __future__ import annotations

from typing import Any, Callable, Dict


class VeyraMicrosoftAgentMiddleware:
    """Function-call middleware for Microsoft Agent Framework."""

    def __init__(self, veyra_instance: Any):
        self.veyra = veyra_instance

    def process_function_call(self, tool_name: str, arguments: Dict[str, Any], fn: Callable[..., Any]) -> Any:
        """Process function call through Veyra execution boundary."""
        return self.soro.call(
            tool_name=tool_name,
            arguments=arguments,
            fn=fn,
        )

    def __call__(self, tool_name: str, arguments: Dict[str, Any], fn: Callable[..., Any]) -> Any:
        return self.process_function_call(tool_name, arguments, fn)
