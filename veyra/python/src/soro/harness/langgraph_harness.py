"""A harness whose control flow is a graph of nodes.

Each kernel action becomes exactly one node execution:

    START -> dispatch -> { reason | act | grade } -> END

The point of the experiment is that this harness is *not* the native one. It has
a different state container, a different transition model and a different
failure surface, while the kernel sees only the portable execution state.

Engine selection: the adapter prefers the real `langgraph` package. If it cannot
be imported (version skew, optional extra not installed) it falls back to a
~40-line in-repo graph runtime with the same node/edge API, and says so in its
capabilities. The fallback exists so the switching experiment is reproducible on
any machine; it is never silently presented as LangGraph.
"""

from __future__ import annotations

import time
from typing import Any, Callable, TypedDict

from soro import grading, tools
from soro.contract import (
    add_message,
    add_observation,
    add_tool_result,
    charge,
    clear_failure,
    mark_done,
    mark_failed,
)
from soro.harness.base import HarnessAdapter
from soro.v1 import runtime_pb2 as pb

START_SENTINEL = "__start__"
END_SENTINEL = "__end__"

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
    LANGGRAPH_ERROR = ""
    ENGINE = "langgraph"
except Exception as exc:  # pragma: no cover - depends on the local environment
    LANGGRAPH_AVAILABLE = False
    LANGGRAPH_ERROR = f"{type(exc).__name__}: {exc}"
    ENGINE = "builtin-graph"
    END, START = END_SENTINEL, START_SENTINEL


class MiniGraph:
    """Minimal node/conditional-edge runtime used when LangGraph is absent.

    Supports exactly the API this adapter uses, so the two engines are
    interchangeable for the experiment.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, Callable[[dict], dict]] = {}
        self.conditional: dict[str, tuple[Callable[[dict], str], dict[str, str]]] = {}
        self.edges: dict[str, str] = {}

    def add_node(self, name: str, fn: Callable[[dict], dict]) -> None:
        self.nodes[name] = fn

    def add_conditional_edges(self, source: str, router: Callable[[dict], str], path_map: dict[str, str]) -> None:
        self.conditional[source] = (router, path_map)

    def add_edge(self, source: str, target: str) -> None:
        self.edges[source] = target

    def compile(self) -> "MiniGraph":
        return self

    def _resolve(self, name: str, state: dict) -> str:
        if name in self.conditional:
            router, path_map = self.conditional[name]
            return path_map[router(state)]
        return name

    def invoke(self, state: dict) -> dict:
        out = dict(state)
        node = self._resolve(START_SENTINEL, out)
        guard = 0
        while node != END_SENTINEL and guard < 64:
            guard += 1
            fn = self.nodes.get(node)
            if fn is None:
                break
            out = {**out, **(fn(out) or {})}
            nxt = self.edges.get(node)
            if nxt is None:
                break
            node = self._resolve(nxt, out)
        return out


class GraphState(TypedDict, total=False):
    messages: list[dict[str, str]]
    observations: list[str]
    results: list[dict[str, Any]]
    pending_action: str
    tool: str
    args: dict[str, Any]
    final: str
    done: bool
    failed: bool
    failure_kind: str
    usd: float
    tokens: int
    model: str


class LangGraphHarness(HarnessAdapter):
    id = "langgraph"
    kind = "graph"
    est_cost_usd_per_step = 0.0030
    est_latency_ms = 1400
    required_permissions = ["fs_read", "fs_write", "shell"]

    @property
    def capabilities(self) -> list[str]:  # type: ignore[override]
        return ["reason", "act", "verify", "graph", f"engine:{ENGINE}"]

    def __init__(self, opts: dict[str, Any] | None = None):
        super().__init__(opts)
        self._pb: pb.CommonExecutionState | None = None
        self._graph = self._build_graph()

    # -- graph definition --------------------------------------------------

    def _build_graph(self):
        graph = StateGraph(GraphState) if LANGGRAPH_AVAILABLE else MiniGraph()
        graph.add_node("reason", self._node_reason)
        graph.add_node("act", self._node_act)
        graph.add_node("grade", self._node_grade)
        graph.add_conditional_edges(
            START, self._dispatch, {"reason": "reason", "act": "act", "grade": "grade"}
        )
        graph.add_edge("reason", END)
        graph.add_edge("act", END)
        graph.add_edge("grade", END)
        return graph.compile()

    @staticmethod
    def _dispatch(state: GraphState) -> str:
        pending = state.get("pending_action", "model_call:cheap")
        if pending.startswith("tool_call:"):
            return "act"
        if pending == "verify":
            return "grade"
        return "reason"

    # -- nodes -------------------------------------------------------------

    def _node_reason(self, state: GraphState) -> GraphState:
        tier = "strong" if "strong" in state.get("pending_action", "") else "cheap"
        reply = self.llm.complete(state.get("messages", []), tier, tools.tool_names())
        msgs = list(state.get("messages", [])) + [{"role": "assistant", "content": reply.text}]
        obs = list(state.get("observations", []))
        out: GraphState = {
            "messages": msgs,
            "usd": state.get("usd", 0.0) + (reply.usd or self._nominal(tier)),
            "tokens": state.get("tokens", 0) + max(reply.tokens, 1),
            "model": reply.model,
        }
        if reply.final is not None:
            out["final"] = str(reply.final)
            out["done"] = True
            obs.append(f"langgraph: model returned a final answer ({reply.model})")
        elif reply.tool:
            # A ReAct step is reason *and* act, so the node executes the tool it
            # just selected. Keeping the granularity identical to the native
            # harness is what makes the two arms comparable.
            out["tool"] = reply.tool
            out["args"] = reply.args
            assert self._pb is not None
            ctx = tools.ToolContext(workspace=self.workspace(self._pb), allow_shell=self.allow_shell)
            ok, res = tools.call_tool(reply.tool, reply.args, ctx)
            obs.append(f"langgraph[{reply.tool}] -> {'ok' if ok else 'failed'}: {res[:300]}")
            out["results"] = [{"tool": reply.tool, "ok": ok, "output": res}]
            if not ok:
                out["failed"] = True
                out["failure_kind"] = "tool"
        else:
            obs.append("langgraph: model produced no action")
        out["observations"] = obs
        return out

    def _node_act(self, state: GraphState) -> GraphState:
        tool = state.get("tool") or state.get("pending_action", "tool_call:").split(":", 1)[-1]
        args = state.get("args") or {}
        assert self._pb is not None
        ctx = tools.ToolContext(workspace=self.workspace(self._pb), allow_shell=self.allow_shell)
        ok, out = tools.call_tool(tool, args, ctx)
        obs = list(state.get("observations", []))
        obs.append(f"langgraph[{tool}] -> {'ok' if ok else 'failed'}: {out[:300]}")
        return {"observations": obs, "tool": tool, "args": args,
                "results": [{"tool": tool, "ok": ok, "output": out}]}

    def _node_grade(self, state: GraphState) -> GraphState:
        assert self._pb is not None
        spec = self._pb.variables.get("grader", "")
        obs = list(state.get("observations", []))
        if not spec:
            obs.append("langgraph: no grader configured")
            return {"observations": obs, "done": True, "failed": False}
        ok, detail = grading.run(spec, self.workspace(self._pb))
        obs.append(f"langgraph verifier: {'passed' if ok else 'failed'} - {detail}")
        return {"observations": obs, "done": ok, "failed": not ok,
                "failure_kind": "" if ok else "verification"}

    def _nominal(self, tier: str) -> float:
        return 0.010 if tier == "strong" else 0.001

    # -- bridge ------------------------------------------------------------

    def on_start(self, state: pb.CommonExecutionState) -> None:
        self._pb = state

    def step(self, state: pb.CommonExecutionState, decision: pb.Decision) -> pb.CommonExecutionState:
        if decision.chosen_id == "compact_context":
            state.step += 1
            self.do_compact(state)
            return state
        self._pb = state
        state.step += 1
        inner: GraphState = {
            "messages": [{"role": m.role, "content": m.content} for m in state.messages],
            "observations": [],
            "pending_action": decision.chosen_id,
        }
        started = time.perf_counter()
        result = self._graph.invoke(inner)
        elapsed = int((time.perf_counter() - started) * 1000)

        msgs = result.get("messages", [])
        if len(msgs) > len(state.messages):
            for m in msgs[len(state.messages):]:
                add_message(state, m["role"], m["content"])
        for obs in result.get("observations", []):
            add_observation(state, obs)
        for r in result.get("results", []) or []:
            add_tool_result(state, r["tool"], r["ok"], r["output"])

        charge(state, usd=float(result.get("usd", 0.0)), wall_ms=max(elapsed, 300),
               tokens=int(result.get("tokens", 0)))

        if result.get("done"):
            mark_done(state, f"graph harness finished the task ({ENGINE})")
        elif result.get("failed"):
            mark_failed(state, result.get("failure_kind") or "environment", "graph node reported failure")
        else:
            clear_failure(state)
        state.variables["langgraph.engine"] = ENGINE
        state.variables["langgraph.last_node"] = self._dispatch(inner)
        state.variables["langgraph.model"] = str(result.get("model", ""))[:40]
        return state


def available() -> tuple[bool, str]:
    if LANGGRAPH_AVAILABLE:
        return True, "langgraph package"
    return True, f"builtin graph fallback ({LANGGRAPH_ERROR[:120]})"