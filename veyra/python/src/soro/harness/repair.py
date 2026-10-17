"""Failure-directed harness.

Native reruns the broken command. The graph harness can rewrite the file, and
it charges graph overhead on every step of every task. Repair sits between
them: before the model acts, it loads the workspace files that the failure
points at, and its scripted policy edits before it executes.

The diagnosis is an observation, not a new action. The kernel still chooses
whether this harness runs at all.
"""

from __future__ import annotations

import re
from pathlib import Path

from soro.contract import add_message, add_observation
from soro.harness.base import HarnessAdapter
from soro.v1 import runtime_pb2 as pb

_PY_PATH = re.compile(r"[\w./\\-]+\.py")
_MAX_FILES = 3
_MAX_BYTES = 4000


class RepairHarness(HarnessAdapter):
    id = "repair"
    kind = "repair"
    capabilities = ["reason", "act", "verify", "diagnose", "tool_use"]
    est_cost_usd_per_step = 0.0012
    est_latency_ms = 1000
    required_permissions = ["fs_read", "fs_write", "shell"]

    def on_start(self, state: pb.CommonExecutionState) -> None:
        self._diagnose(state, reason="workspace on entry")

    def do_model_call(self, state: pb.CommonExecutionState, decision: pb.Decision) -> None:
        if state.failed or any(not r.ok for r in state.tool_results):
            self._diagnose(state, reason="previous step failed")
        super().do_model_call(state, decision)

    def _diagnose(self, state: pb.CommonExecutionState, reason: str) -> None:
        key = "repair.diagnosed"
        stamp = f"{state.step}:{reason}"
        if state.variables.get(key) == stamp:
            return
        root = self.workspace(state)
        blobs: list[str] = []
        for rel in _candidate_files(state, root):
            path = (root / rel).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")[:_MAX_BYTES]
            blobs.append(f"----- {rel} -----\n{text}")
            if len(blobs) >= _MAX_FILES:
                break
        if not blobs:
            return
        state.variables[key] = stamp
        body = f"Repair diagnosis ({reason}). Do not repeat a command that just failed. Edit the file, then run it.\n\n" + "\n".join(blobs)
        add_message(state, "user", body)
        add_observation(state, f"repair loaded {len(blobs)} file(s) before the next model call")


def _candidate_files(state: pb.CommonExecutionState, root: Path) -> list[str]:
    seen: list[str] = []

    def add(raw: str) -> None:
        name = raw.replace("\\", "/").lstrip("./")
        if name and name not in seen:
            seen.append(name)

    for result in reversed(list(state.tool_results)):
        if result.ok:
            continue
        for match in _PY_PATH.findall(result.output or ""):
            add(match)
    for obs in reversed(list(state.observations)):
        for match in _PY_PATH.findall(obs):
            add(match)
    if root.is_dir():
        for path in sorted(root.glob("*.py")):
            add(path.name)
    return seen
