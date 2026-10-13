"""Adapter for mini-swe-agent, the scaffold the SWE-bench bash board holds fixed.

One Veyra step calls ``DefaultAgent.step`` once, then copies the new messages
back into ``CommonExecutionState``. The upstream ``run()`` loop is not used:
that would hide the checkpoint where Veyra decides to switch or compact.

The package is optional. ``pip install 'veyra[miniswe]'`` (or
``mini-swe-agent``) enables it. Without it, the harness reports itself
unavailable and refuses to start, instead of pretending to be mini-swe-agent.
"""

from __future__ import annotations

from typing import Any

from soro.contract import add_message, add_observation, mark_done, mark_failed
from soro.harness.base import HarnessAdapter
from soro.v1 import runtime_pb2 as pb


def available() -> tuple[bool, str]:
    try:
        import minisweagent  # noqa: F401
    except ImportError:
        return False, "not installed; pip install 'veyra[miniswe]'"
    return True, "minisweagent import ok"


def load_classes() -> tuple[Any, Any]:
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.local import LocalEnvironment

    return DefaultAgent, LocalEnvironment


class MiniSweHarness(HarnessAdapter):
    id = "miniswe"
    kind = "miniswe"
    capabilities = ["reason", "act", "bash", "swebench-scaffold"]
    est_cost_usd_per_step = 0.0020
    est_latency_ms = 2000
    required_permissions = ["fs_read", "fs_write", "shell"]

    def __init__(self, opts: dict[str, Any] | None = None):
        super().__init__(opts)
        self._agent: Any = self.opts.get("agent")

    def on_start(self, state: pb.CommonExecutionState) -> None:
        if self._agent is None:
            ok, detail = available()
            if not ok:
                mark_failed(state, "harness_error", detail)
                add_observation(state, detail)
                return
            agent_cls, env_cls = load_classes()
            self._agent = agent_cls(self._model_for_upstream(), env_cls())
        messages = getattr(self._agent, "messages", None)
        if messages is not None and len(messages) == 0:
            self._agent.messages = [{"role": m.role, "content": m.content} for m in state.messages]
        state.variables["miniswe.engine"] = "minisweagent" if self.opts.get("agent") is None else "injected"

    def do_model_call(self, state: pb.CommonExecutionState, decision: pb.Decision) -> None:
        if self._agent is None:
            mark_failed(state, "harness_error", "mini-swe-agent is not available")
            return
        before = len(getattr(self._agent, "messages", []) or [])
        produced = self._agent.step()
        rows = list(produced or [])
        if not rows and getattr(self._agent, "messages", None):
            rows = list(self._agent.messages)[before:]
        for row in rows:
            role = str(row.get("role") or "assistant")
            content = str(row.get("content") or "")
            add_message(state, role, content[:4000])
            if role == "exit":
                mark_done(state, content[:200] or "mini-swe-agent exited")
        add_observation(state, f"miniswe step produced {len(rows)} message(s)")

    def _model_for_upstream(self) -> Any:
        """A model object is required by DefaultAgent. Live runs pass one in opts.

        The offline suite does not drive this harness. A live run supplies
        ``model`` pointing at the same endpoint as ``--model-mode openai``.
        """
        model = self.opts.get("model")
        if model is not None:
            return model
        raise RuntimeError(
            "miniswe needs opts['model'] (a mini-swe-agent model) or opts['agent'] for tests"
        )
