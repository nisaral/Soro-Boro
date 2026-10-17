"""Repair harness loads the failing file before the model acts."""

from veyra.harness.repair import RepairHarness
from veyra.v1 import runtime_pb2 as pb


def test_repair_loads_workspace_python_before_the_first_call(tmp_path):
    (tmp_path / "broken.py").write_text("raise RuntimeError('missing')\n", encoding="utf-8")
    h = RepairHarness({"workspace": str(tmp_path), "offline_scripts": {"repair": [
        {"thought": "rewrite", "tool": "write_file",
         "args": {"path": "broken.py", "content": "print('OK-1')\n"}},
        {"thought": "done", "final": "done"},
    ]}})
    task = pb.TaskSpec(id="recovery-01", instruction="fix broken.py", workspace=str(tmp_path))
    state = h.start(task, None)
    assert any("broken.py" in m.content for m in state.messages)
    assert any(o.startswith("repair loaded") for o in state.observations)
    state = h.step(state, pb.Decision(chosen_id="model_call:cheap"))
    assert "print('OK-1')" in (tmp_path / "broken.py").read_text(encoding="utf-8")
    state = h.step(state, pb.Decision(chosen_id="model_call:cheap"))
    assert state.done and not state.failed
