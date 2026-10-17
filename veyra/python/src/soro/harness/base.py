"""The harness contract.

A harness is an *executor*, not a planner. It receives the portable state and a
decision the kernel already approved, performs exactly that one action, and
returns the updated state. It never chooses what to do next and never talks to
another harness.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from soro import grading, tools
from soro.contract import (
    GRADER_KEY,
    add_message,
    add_observation,
    add_tool_result,
    charge,
    clear_failure,
    mark_done,
    mark_failed,
    new_state,
    note_harness,
    options,
)
from soro.llm import LLMClient, make_llm
from soro.v1 import runtime_pb2 as pb

# Nominal economics for models that do not report their own price (local and
# scripted models). Mirrors planner.CheapTier / StrongTier in the Go kernel.
TIER_PRICE_USD = {"cheap": 0.0010, "strong": 0.0100}
NOMINAL_LATENCY_MS = {"cheap": 300, "strong": 900}

SYSTEM_PROMPT = (
    "You are executing a software task inside a sandboxed workspace.\n"
    "Work in small steps. Prefer inspecting the workspace before editing it.\n"
)


class HarnessError(RuntimeError):
    """Raised when a harness cannot continue (bad action, missing dependency)."""


class HarnessAdapter(ABC):
    id: str = "harness"
    kind: str = "generic"
    capabilities: list[str] = ["reason", "act", "verify"]
    est_cost_usd_per_step: float = 0.001
    est_latency_ms: int = 1000
    supports_checkpoint: bool = True
    required_permissions: list[str] = ["fs_read", "fs_write", "shell"]

    def __init__(self, opts: dict[str, Any] | None = None):
        self.opts = opts or {}
        self.llm: LLMClient = self._make_llm()
        self.allow_shell = bool(self.opts.get("allow_shell", True))

    # -- lifecycle ---------------------------------------------------------

    def start(self, task: pb.TaskSpec, state: pb.CommonExecutionState | None) -> pb.CommonExecutionState:
        if state is None:
            state = new_state(task, harness_id=self.id, workspace=task.workspace)
            add_message(state, "system", SYSTEM_PROMPT + self._task_brief(task))
            add_message(state, "user", task.instruction)
        else:
            # Resuming from a checkpoint: adopt the portable state as-is.
            add_observation(state, f"resumed in harness {self.id}")
        note_harness(state, self.id)
        state.harness_id = self.id
        self.on_start(state)
        return state

    def step(self, state: pb.CommonExecutionState, decision: pb.Decision) -> pb.CommonExecutionState:
        state.step += 1
        action = decision.chosen_id
        try:
            if action.startswith("model_call"):
                self.do_model_call(state, decision)
            elif action == "compact_context":
                self.do_compact(state)
            elif action.startswith("tool_call:"):
                self.do_tool_call(state, action.split(":", 1)[1])
            elif action == "verify":
                self.do_verify(state)
            elif action == "retry":
                self.do_retry(state)
            elif action == "terminate":
                pass
            else:
                raise HarnessError(f"{self.id} cannot execute action {action!r}")
        except HarnessError:
            raise
        except Exception as exc:
            mark_failed(state, "harness_error", f"{type(exc).__name__}: {exc}")
        self.on_step(state, decision)
        return state

    def control(self, op: pb.ControlOp) -> None:
        self.on_control(op)

    def inspect(self) -> pb.CommonExecutionState | None:
        return None

    # -- optional hooks ----------------------------------------------------

    def on_start(self, state: pb.CommonExecutionState) -> None: ...
    def on_step(self, state: pb.CommonExecutionState, decision: pb.Decision) -> None: ...
    def on_control(self, op: pb.ControlOp) -> None: ...

    # -- shared action implementations -------------------------------------

    def do_model_call(self, state: pb.CommonExecutionState, decision: pb.Decision) -> None:
        tier = "strong" if "strong" in decision.chosen_id else "cheap"
        reply = self.llm.complete(_prompt_messages(state), tier, tools.tool_names())
        # A hosted model reports its own price. A local or scripted model reports
        # zero, which would make the budget meaningless, so fall back to the
        # tier price the planner already advertises. Cost estimation belongs to
        # the runtime, not to the model.
        nominal = TIER_PRICE_USD["strong" if tier == "strong" else "cheap"]
        usd = reply.usd if reply.usd > 0 else nominal
        charge(state, usd=usd, wall_ms=max(reply.latency_ms, NOMINAL_LATENCY_MS[tier]), tokens=max(reply.tokens, 1))
        state.variables["last_model"] = reply.model
        add_message(state, "assistant", reply.text)

        if reply.final is not None:
            state.variables["candidate_final"] = str(reply.final)
            mark_done(state, f"model proposed a final answer ({reply.model})")
            return
        if reply.tool:
            self._execute_tool(state, reply.tool, reply.args)
            return
        add_observation(state, "model produced no action; treating as inconclusive")

    def do_tool_call(self, state: pb.CommonExecutionState, tool: str) -> None:
        self._execute_tool(state, tool, {})

    def do_compact(self, state: pb.CommonExecutionState, keep_first: int = 1, keep_last: int = 4) -> None:
        """OpenHands-style condenser: keep the first and last messages, summarize the middle.

        This is deterministic. It does not call a model. The summary is a stand-in
        for a condenser, and it is the action a later learned policy can choose
        when the history is the expensive part of the step.
        """
        msgs = list(state.messages)
        if len(msgs) <= keep_first + keep_last:
            add_observation(state, "compact skipped; history is already short")
            return
        head = msgs[:keep_first]
        tail = msgs[-keep_last:]
        middle = msgs[keep_first:-keep_last]
        lines = [f"[compacted {len(middle)} messages]"]
        for msg in middle[:8]:
            text = (msg.content or "").replace("\n", " ")
            lines.append(f"{msg.role}: {text[:180]}")
        del state.messages[:]
        for msg in head:
            state.messages.append(msg)
        add_message(state, "user", "\n".join(lines))
        for msg in tail:
            state.messages.append(msg)
        add_observation(state, f"compacted {len(middle)} messages; kept {keep_first}+{keep_last}")

    def do_retry(self, state: pb.CommonExecutionState) -> None:
        clear_failure(state)
        last = state.tool_results[-1] if state.tool_results else None
        if last is None:
            add_message(state, "user", "The previous attempt failed. Take a different approach.")
            add_observation(state, "retry: no tool result to replay, re-prompting the model")
            return
        self._execute_tool(state, last.tool, {"__retry_of__": last.tool})

    def do_verify(self, state: pb.CommonExecutionState) -> None:
        spec = state.variables.get(GRADER_KEY, "")
        if not spec:
            add_observation(state, "no grader configured; accepting the harness verdict")
            state.done = True
            return
        ok, detail = grading.run(spec, self.workspace(state))
        charge(state, usd=0.0, wall_ms=0, tokens=0)
        if ok:
            mark_done(state, f"verifier passed: {detail}")
        else:
            mark_failed(state, "verification", f"verifier failed: {detail}")

    def _execute_tool(self, state: pb.CommonExecutionState, tool: str, args: dict[str, Any]) -> None:
        ctx = tools.ToolContext(workspace=self.workspace(state), allow_shell=self.allow_shell)
        if tool == "__fault__":
            add_tool_result(state, tool, False, "injected fault")
            mark_failed(state, "environment", "injected fault in tool layer")
            return
        if tool not in tools.REGISTRY:
            add_tool_result(state, tool, False, f"unknown tool {tool!r}")
            mark_failed(state, "reasoning", f"model requested unknown tool {tool!r}")
            return
        ok, out = tools.call_tool(tool, args, ctx)
        add_tool_result(state, tool, ok, out)
        add_observation(state, f"{tool} -> {'ok' if ok else 'failed'}: {out[:300]}")
        if ok:
            clear_failure(state)
        else:
            # A failed tool is the escalation signal the runtime is built around:
            # it is what makes failure-directed routing observable at all.
            mark_failed(state, "tool", f"{tool} failed: {out[:200]}")

    def workspace(self, state: pb.CommonExecutionState) -> Path:
        return Path(self.opts.get("workspace") or state.workspace or ".").resolve()

    def _task_brief(self, task: pb.TaskSpec) -> str:
        lines = [f"Task id: {task.id}", f"Category: {', '.join(task.category) or 'general'}", ""]
        lines.append("Available tools:")
        lines.append(tools.describe_tools())
        return "\n".join(lines)

    def _make_llm(self) -> LLMClient:
        opts = dict(self.opts)
        scripts = opts.get("offline_scripts") or {}
        if self.id in scripts:
            opts["offline_script"] = scripts[self.id]
        return make_llm(opts)

    def info(self) -> pb.HarnessInfo:
        return pb.HarnessInfo(
            id=self.id,
            kind=self.kind,
            capabilities=self.capabilities,
            est_cost_usd_per_step=self.est_cost_usd_per_step,
            est_latency_ms=self.est_latency_ms,
            supports_checkpoint=self.supports_checkpoint,
            required_permissions=self.required_permissions,
        )


def _prompt_messages(state: pb.CommonExecutionState) -> list[dict[str, str]]:
    from soro.contract import messages_for_prompt, summarize

    msgs = messages_for_prompt(state)
    msgs.append({"role": "user", "content": "Current execution state:\n" + summarize(state)})
    return msgs


__all__ = ["HarnessAdapter", "HarnessError", "SYSTEM_PROMPT", "options"]