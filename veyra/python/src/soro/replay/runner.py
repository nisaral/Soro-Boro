"""Trajectory Replayer for Veyra (Phase 14).

Reconstructs decision paths from trace/trajectory JSON files without executing dangerous side effects by default (DRY_RUN).
Requires explicit opt-in for --execute.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


class TrajectoryReplayer:
    """Replays trajectory traces under Veyra execution policies."""

    def __init__(self, veyra_instance: Any, mode: str = "DRY_RUN"):
        self.veyra = veyra_instance
        self.mode = mode.upper()

    def replay_file(self, filepath: str, execute: bool = False) -> Dict[str, Any]:
        """Replay execution trajectory from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        steps = data.get("steps", data.get("traces", []))
        if not isinstance(steps, list):
            steps = [data]

        results = []
        for idx, step in enumerate(steps):
            tool = step.get("proposed_tool") or step.get("tool", "unknown")
            arguments = step.get("arguments", {})
            decision = "SIMULATED_SELECT"

            if execute and self.mode == "EXECUTE":
                try:
                    res = self.soro.call(tool_name=tool, arguments=arguments)
                    status = "EXECUTED"
                except Exception as e:
                    res = str(e)
                    status = "FAILED"
            else:
                res = {"simulated": True, "notice": "Dry-run execution. No mutations performed."}
                status = "DRY_RUN"

            results.append({
                "step": idx + 1,
                "tool": tool,
                "arguments": arguments,
                "decision": decision,
                "status": status,
                "outcome": res,
            })

        return {
            "file": filepath,
            "mode": "EXECUTE" if (execute and self.mode == "EXECUTE") else "DRY_RUN",
            "total_steps": len(steps),
            "step_results": results,
        }
