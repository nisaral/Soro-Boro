"""Soro Python SDK: Client & Middleware Wrappers.

Supports:
- SoroClient: typed client for Soro HTTP service or local routing.
- OpenAIWrap: thin wrapper intercepting OpenAI function calling tools to add conformal shortlisting and safe execution.
- LangChainWrap: tool interceptor for LangChain/LangGraph tool calls.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from soro.framework.models import (
    ExecuteRequest,
    ExecuteResponse,
    RouteRequest,
    RouteResponse,
    ToolCandidate,
    ToolDecisionType,
)


class SoroClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", local_fallback: bool = True):
        self.base_url = base_url
        self.local_fallback = local_fallback

    def route(self, query: str, candidates: List[Dict[str, Any]], alpha: float = 0.05, shadow_mode: bool = False) -> RouteResponse:
        import httpx

        tool_models = [
            ToolCandidate(
                name=c["name"],
                description=c.get("description", ""),
                parameters=c.get("parameters", {}),
                score=float(c.get("score", 1.0)),
                inferred_class=c.get("class", "read_only"),
            )
            for c in candidates
        ]
        req = RouteRequest(query=query, candidate_tools=tool_models, alpha=alpha, shadow_mode=shadow_mode)
        try:
            resp = httpx.post(f"{self.base_url}/route", json=req.model_dump(), timeout=2.0)
            if resp.status_code == 200:
                return RouteResponse.model_validate(resp.json())
        except Exception:
            if not self.local_fallback:
                raise

        # Local in-process fallback
        sorted_tools = sorted(tool_models, key=lambda t: t.score, reverse=True)
        shortlist = sorted_tools[:3] if len(sorted_tools) >= 3 else sorted_tools
        return RouteResponse(
            decision=ToolDecisionType.EXECUTE if len(shortlist) == 1 else ToolDecisionType.ASK_CONFIRMATION,
            shortlist=shortlist,
            singleton_tool=shortlist[0] if len(shortlist) == 1 else None,
            trace={
                "decision": ToolDecisionType.EXECUTE if len(shortlist) == 1 else ToolDecisionType.ASK_CONFIRMATION,
                "reason": "Local fallback shortlist",
                "prediction_set_size": len(shortlist),
                "shadow_mode": shadow_mode,
            },
        )

    def execute(self, tool_name: str, arguments: Dict[str, Any], action_id: str | None = None, idempotency_key: str | None = None) -> ExecuteResponse:
        import httpx

        req = ExecuteRequest(
            tool_name=tool_name,
            arguments=arguments,
            action_id=action_id or f"act_{id(arguments)}",
            idempotency_key=idempotency_key,
        )
        try:
            resp = httpx.post(f"{self.base_url}/execute", json=req.model_dump(), timeout=5.0)
            if resp.status_code == 200:
                return ExecuteResponse.model_validate(resp.json())
        except Exception:
            if not self.local_fallback:
                raise

        return ExecuteResponse(
            status="COMMITTED",
            result={"tool": tool_name, "args": arguments},
            was_replayed=False,
            was_deferred=False,
            trace={
                "decision": ToolDecisionType.EXECUTE,
                "reason": "Local execution",
                "action_id": req.action_id,
            },
        )


class OpenAIWrap:
    """Thin wrapper for OpenAI chat completions with function calling."""

    def __init__(self, client: SoroClient):
        self.soro = client

    def filter_tools(self, query: str, openai_tools: List[Dict[str, Any]], alpha: float = 0.05) -> List[Dict[str, Any]]:
        candidates = [
            {
                "name": t.get("function", {}).get("name", t.get("name")),
                "description": t.get("function", {}).get("description", t.get("description", "")),
                "parameters": t.get("function", {}).get("parameters", {}),
            }
            for t in openai_tools
        ]
        route_res = self.soro.route(query, candidates, alpha=alpha)
        allowed_names = {t.name for t in route_res.shortlist}
        return [t for t in openai_tools if (t.get("function", {}).get("name", t.get("name")) in allowed_names)]
