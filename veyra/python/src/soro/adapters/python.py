"""Python native function adapter."""

from __future__ import annotations
import inspect
from typing import Any, Callable, Dict

class PythonAdapter:
    """Adapts native Python callables into Veyra ToolDefinitions."""

    @staticmethod
    def adapt_function(fn: Callable[..., Any], name: str | None = None) -> Dict[str, Any]:
        fn_name = name or fn.__name__
        sig = inspect.signature(fn)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            properties[param_name] = {"type": "string"}
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "object",
            "properties": properties,
            "required": required,
        }
        return {
            "name": fn_name,
            "executable": fn,
            "schema": schema,
            "protocol": "python",
        }
