"""Helpers for building and reading the portable execution state.

The contract is the checkpoint, not any harness's private state: switching
harnesses means handing this message to the next adapter.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

from soro.v1 import runtime_pb2 as pb

TRIED_KEY = "soro.tried_harnesses"
SCRIPT_KEY = "offline_script"
GRADER_KEY = "grader"


def new_state(task: pb.TaskSpec, harness_id: str = "", workspace: str = "") -> pb.CommonExecutionState:
    return pb.CommonExecutionState(
        task_id=task.id,
        instruction=task.instruction,
        harness_id=harness_id,
        workspace=workspace or task.workspace,
        variables=dict(task.metadata),
        usage=pb.BudgetUsage(),
    )


def add_message(state: pb.CommonExecutionState, role: str, content: str) -> None:
    state.messages.append(pb.Message(role=role, content=content))


def add_observation(state: pb.CommonExecutionState, text: str) -> None:
    if text:
        state.observations.append(text)


def add_tool_result(state: pb.CommonExecutionState, tool: str, ok: bool, output: str, usd: float = 0.0) -> None:
    state.tool_results.append(pb.ToolResult(tool=tool, ok=ok, output=output, usd=usd))


def charge(state: pb.CommonExecutionState, *, usd: float = 0.0, wall_ms: int = 0, tokens: int = 0) -> None:
    """Add to the *cumulative* usage. The kernel charges the delta."""
    state.usage.actions += 1
    state.usage.usd += usd
    state.usage.wall_ms += wall_ms
    state.usage.tokens += tokens


def mark_done(state: pb.CommonExecutionState, note: str = "") -> None:
    state.done = True
    state.failed = False
    add_observation(state, note)


def mark_failed(state: pb.CommonExecutionState, kind: str, note: str = "") -> None:
    state.failed = True
    state.done = False
    state.failure_kind = kind
    add_observation(state, note)


def clear_failure(state: pb.CommonExecutionState) -> None:
    state.failed = False
    state.failure_kind = ""


def tried_harnesses(state: pb.CommonExecutionState) -> list[str]:
    raw = state.variables.get(TRIED_KEY, "")
    return [x for x in raw.split(",") if x]


def note_harness(state: pb.CommonExecutionState, harness_id: str) -> None:
    tried = tried_harnesses(state)
    if harness_id not in tried:
        tried.append(harness_id)
    state.variables[TRIED_KEY] = ",".join(tried)


def messages_for_prompt(state: pb.CommonExecutionState, limit: int = 24) -> list[dict[str, str]]:
    msgs = [{"role": m.role, "content": m.content} for m in state.messages]
    if len(msgs) > limit:
        msgs = msgs[-limit:]
    return msgs


def summarize(state: pb.CommonExecutionState, limit: int = 1200) -> str:
    obs = list(state.observations)[-4:]
    tools = list(state.tool_results)[-3:]
    lines = [
        f"step={state.step}",
        f"done={state.done} failed={state.failed} failure_kind={state.failure_kind!r}",
        f"artifacts={[a.path for a in state.artifacts]}",
        f"recent_observations={json.dumps(obs)[:limit]}",
        f"recent_tool_results={[{'tool': t.tool, 'ok': t.ok, 'out': t.output[:200]} for t in tools]}",
    ]
    return "\n".join(lines)


def options(state: pb.CommonExecutionState) -> dict[str, Any]:
    return dict(state.variables)


def parse_options(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        got = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return got if isinstance(got, dict) else {}


def as_dict(state: pb.CommonExecutionState) -> dict[str, Any]:
    return {
        "task_id": state.task_id,
        "harness": state.harness_id,
        "step": state.step,
        "done": state.done,
        "failed": state.failed,
        "observations": list(state.observations),
        "artifacts": [a.path for a in state.artifacts],
        "usage": {"actions": state.usage.actions, "usd": round(state.usage.usd, 6), "tokens": state.usage.tokens},
        "variables": dict(state.variables),
    }


def tail(xs: Iterable[str], n: int) -> list[str]:
    items = list(xs)
    return items[-n:]