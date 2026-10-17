"""The graph harness executes one kernel action per node and records its engine."""

from veyra.harness.langgraph_harness import ENGINE, LangGraphHarness
from veyra.v1 import runtime_pb2 as pb


def test_reason_node_executes_the_selected_tool(tmp_path):
    h = LangGraphHarness({"workspace": str(tmp_path), "offline_scripts": {"langgraph": [
        {"thought": "write", "tool": "write_file", "args": {"path": "y.txt", "content": "yo"}},
    ]}})
    task = pb.TaskSpec(id="t", instruction="write y.txt", workspace=str(tmp_path))
    state = h.start(task, None)
    state = h.step(state, pb.Decision(chosen_id="model_call:cheap"))
    assert (tmp_path / "y.txt").read_text(encoding="utf-8") == "yo"
    assert state.variables["langgraph.engine"] == ENGINE
    assert state.usage.usd > 0


def test_resuming_from_a_checkpoint_adopts_the_portable_state(tmp_path):
    h = LangGraphHarness({"workspace": str(tmp_path), "offline_scripts": {"langgraph": []}})
    task = pb.TaskSpec(id="t", instruction="x", workspace=str(tmp_path))
    state = h.start(task, None)
    resumed = LangGraphHarness({"workspace": str(tmp_path), "offline_scripts": {"langgraph": []}})
    same = resumed.start(task, state)
    assert same.task_id == "t"
    assert "resumed in harness langgraph" in list(same.observations)
