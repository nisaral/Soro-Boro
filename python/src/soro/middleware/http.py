"""HTTP middleware wrapper for HTTP client objects."""

from __future__ import annotations

from typing import Any, Dict

class HTTPWrapper:
    """Wraps an HTTP client to validate outbound API tool calls with Veyra policy."""

    def __init__(self, veyra_instance: Any, client: Any):
        self.veyra = veyra_instance
        self.client = client

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        def _execute_http(**params):
            if hasattr(self.client, "request"):
                return self.client.request(method, url, **params)
            raise AttributeError("HTTP client does not expose a request method.")

        tool_name = f"http_{method.lower()}"
        return self.soro.call(
            tool_name=tool_name,
            arguments={"url": url, "kwargs": kwargs},
            fn=_execute_http,
        )

    def get(self, url: str, **kwargs: Any) -> Any:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self.request("POST", url, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.client, name)
