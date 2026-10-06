"""Tests for Veyra MCP Tool Middleware."""

import pytest
from veyra.boundary.interceptor import Veyra
from veyra.boundary.mcp import MCPToolMiddleware
from veyra.boundary.retry import SafeRetryPolicy
from veyra.boundary.trace import TraceRecorder


class TestMCPToolMiddleware:
    def setup_method(self):
        self.recorder = TraceRecorder()
        self.retry_policy = SafeRetryPolicy(max_attempts=3, base_backoff_sec=0.01, max_backoff_sec=0.05, jitter=False)
        self.veyra = Veyra(recorder=self.recorder, retry_policy=self.retry_policy)
        self.middleware = MCPToolMiddleware(veyra=self.veyra)

    def test_mcp_tool_call_successful_coercion(self):
        input_schema = {
            "type": "object",
            "properties": {
                "page": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["page"],
        }

        def handler(kwargs):
            return {"items": [1, 2, 3], "page": kwargs["page"]}

        response = self.middleware.handle_call_tool(
            tool_name="list_items",
            arguments={"page": "2", "limit": "50"},
            handler=handler,
            input_schema=input_schema,
            retryable=True,
            idempotent=True,
        )

        assert response["isError"] is False
        assert response["structured_result"]["page"] == 2
        assert len(self.recorder.traces) == 1
        assert self.recorder.traces[0].decision == "corrected_and_executed"

    def test_mcp_tool_call_returns_structured_error_on_precondition_failure(self):
        def handler(kwargs):
            raise ValueError("Precondition failed: repository branch is locked")

        response = self.middleware.handle_call_tool(
            tool_name="git_push",
            arguments={"branch": "main"},
            handler=handler,
            retryable=False,
            idempotent=False,
        )

        assert response["isError"] is True
        assert "error_classification" in response
        assert response["error_classification"]["kind"] == "precondition_error"
        assert response["error_classification"]["requires_agent"] is True
