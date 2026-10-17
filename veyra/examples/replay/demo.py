"""Veyra Replay & Trajectory Diffing Example."""

import json
from veyra import Veyra
from veyra.replay import TrajectoryReplayer, TrajectoryDiff

def main():
    veyra = Veyra()
    replayer = TrajectoryReplayer(veyra, mode="DRY_RUN")

    sample_trajectory = {
        "traces": [
            {"proposed_tool": "create_user", "arguments": {"username": "alice"}},
            {"proposed_tool": "delete_user", "arguments": {"username": "bob"}}
        ]
    }

    with open("sample_run.json", "w", encoding="utf-8") as f:
        json.dump(sample_trajectory, f, indent=2)

    replay_result = replayer.replay_file("sample_run.json")
    print("Replay result (DRY_RUN mode):", json.dumps(replay_result, indent=2))

    diff_result = TrajectoryDiff.compare_files("sample_run.json", "sample_run.json")
    print("Trajectory Diff result:", json.dumps(diff_result, indent=2))

if __name__ == "__main__":
    main()
