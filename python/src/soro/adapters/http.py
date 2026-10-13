"""HTTP protocol adapter."""

from __future__ import annotations
from typing import Any, Dict

class HTTPAdapter:
    """Adapts HTTP endpoint specifications into Veyra ToolDefinitions."""

    @staticmethod
    def adapt_endpoint(name: str, url: str, method: str = "POST", schema: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {
            "name": name,
            "url": url,
            "method": method.upper(),
            "schema": schema or {},
            "protocol": "http",
        }
