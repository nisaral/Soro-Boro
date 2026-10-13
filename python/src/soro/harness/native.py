"""The built-in harness: an imperative ReAct loop.

It is deliberately plain. It exists as the baseline implementation, the one a
reader can check in a single sitting, and as the harness the switching
experiment starts in.
"""

from __future__ import annotations

from soro.harness.base import HarnessAdapter


class NativeHarness(HarnessAdapter):
    id = "native"
    kind = "react"
    capabilities = ["reason", "act", "verify", "tool_use"]
    est_cost_usd_per_step = 0.0010
    est_latency_ms = 900
    required_permissions = ["fs_read", "fs_write", "shell"]

    def on_step(self, state, decision) -> None:
        # One model step per action keeps the comparison with the graph harness
        # fair: both spend the same number of actions on the same task.
        if decision.chosen_id.startswith("model_call"):
            state.variables["native.saw_model"] = "1"