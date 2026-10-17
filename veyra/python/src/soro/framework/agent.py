"""Thin agent loop: model proposes, DeterministicRouter filters, wrapped tools execute."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from soro.framework.router import RouteKind
from soro.llm import LLMClient, OfflineLLM, TOOL_PROTOCOL

if TYPE_CHECKING:
    from soro.production.production_layer import Soro


class Agent:
    """Personal harness loop. Routing and UNKNOWN_ACK stay on Soro, not the model."""

    def __init__(self, soro: Soro, llm: LLMClient | None = None, max_turns: int = 8) -> None:
        self.soro = soro
        self.llm = llm or OfflineLLM()
        self.max_turns = max_turns

    def run(self, task: str, *, state=None) -> dict[str, Any]:
        messages = [{"role": "user", "content": task}]
        traces: list[dict[str, Any]] = []
        names = list(self.soro.tools)
        for turn in range(self.max_turns):
            route = self.soro.route(task if turn == 0 else messages[-1]["content"], state=state)
            allowed = [c.tool for c in route.shortlist] or names
            if route.kind == RouteKind.DENY:
                traces.append({"turn": turn, "route": route.to_dict()})
                return {"status": "DENIED", "task": task, "traces": traces, "route": route.to_dict()}
            if route.kind == RouteKind.ABSTAIN:
                traces.append({"turn": turn, "route": route.to_dict()})
                return {"status": "ABSTAINED", "task": task, "traces": traces, "route": route.to_dict()}

            reply = self.llm.complete(messages, tier="cheap", tools=allowed)
            if reply.final:
                traces.append({"turn": turn, "final": reply.final, "route": route.to_dict()})
                return {"status": "DONE", "result": reply.final, "task": task, "traces": traces}

            proposed = reply.tool
            if not proposed:
                traces.append({"turn": turn, "error": "empty tool", "route": route.to_dict()})
                return {"status": "ABSTAINED", "task": task, "traces": traces, "route": route.to_dict()}

            decided = self.soro.route(
                task,
                proposed_tool=proposed,
                arguments=reply.args or {},
                state=state,
            )
            traces.append({"turn": turn, "proposed": proposed, "route": decided.to_dict(), "thought": reply.text})
            if decided.kind in (RouteKind.DENY, RouteKind.ABSTAIN):
                return {"status": decided.kind.value, "task": task, "traces": traces, "route": decided.to_dict()}
            if decided.kind == RouteKind.ASK:
                return {
                    "status": "ASK",
                    "task": task,
                    "shortlist": [c.tool for c in decided.shortlist],
                    "traces": traces,
                    "route": decided.to_dict(),
                }

            fn = self.soro.tools.get(decided.tool or proposed)
            if fn is None:
                return {"status": "DENIED", "reason": "tool not registered", "traces": traces}
            result = fn(**(reply.args or {}))
            messages.append({"role": "assistant", "content": reply.text})
            messages.append({"role": "user", "content": f"tool {decided.tool} result: {result}"})
            traces[-1]["result"] = result
        return {"status": "MAX_TURNS", "task": task, "traces": traces}
