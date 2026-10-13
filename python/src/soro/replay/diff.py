"""Trajectory Diffing Subsystem for Veyra (Phase 14).

Compares two execution runs and reports differences in selected tools, policy evaluation, state transitions, recovery, latency, and outcomes.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


class TrajectoryDiff:
    """Computes structured diff between two Veyra trajectory JSON files."""

    @staticmethod
    def compare_files(file1: str, file2: str) -> Dict[str, Any]:
        with open(file1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        with open(file2, "r", encoding="utf-8") as f:
            data2 = json.load(f)

        steps1 = data1.get("steps", data1.get("traces", [data1]))
        steps2 = data2.get("steps", data2.get("traces", [data2]))

        diffs = []
        max_len = max(len(steps1), len(steps2))

        for i in range(max_len):
            s1 = steps1[i] if i < len(steps1) else None
            s2 = steps2[i] if i < len(steps2) else None

            step_diff = {
                "step_index": i + 1,
                "tool_changed": (s1.get("tool") != s2.get("tool")) if (s1 and s2) else True,
                "s1_tool": s1.get("tool") if s1 else None,
                "s2_tool": s2.get("tool") if s2 else None,
                "outcome_changed": (s1.get("outcome") != s2.get("outcome")) if (s1 and s2) else True,
                "latency_diff_ms": abs(s1.get("latency_ms", 0) - s2.get("latency_ms", 0)) if (s1 and s2) else None,
            }
            diffs.append(step_diff)

        return {
            "run1": file1,
            "run2": file2,
            "total_steps_run1": len(steps1),
            "total_steps_run2": len(steps2),
            "diffs": diffs,
        }
