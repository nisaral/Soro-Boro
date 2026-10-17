"""End-to-end harness behaviour with the deterministic scripted model."""

import json

from veyra.harness.native import NativeHarness
from veyra.v1 import runtime_pb2 as pb


def _task(ws, grader=""):
    return pb.TaskSpec(id="t", instruction="write x.txt", workspace=str(ws),
                       metadata={"grader": grader})


def _harness(ws, script):
    return NativeHarness({"workspace": str(ws), "offline_scripts": {"native": script}})


def test_offline_script_writes_a_file_then_finishes(tmp_path):
    h = _harness(tmp_path, [
        {"thought": "write", "tool": "write_file", "args": {"path": "x.txt", "content": "hi"}},
        {"thought": "done", "final": "done"},
    ])
    state = h.start(_task(tmp_path), None)
    state = h.step(state, pb.Decision(chosen_id="model_call:cheap"))
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "hi"
    assert not state.done
    state = h.step(state, pb.Decision(chosen_id="model_call:cheap"))
    assert state.done and not state.failed


def test_a_refused_tool_marks_a_recoverable_failure(tmp_path):
    h = _harness(tmp_path, [
        {"thought": "escape", "tool": "write_file", "args": {"path": "../evil.txt", "content": "x"}},
    ])
    state = h.start(_task(tmp_path), None)
    state = h.step(state, pb.Decision(chosen_id="model_call:cheap"))
    assert state.failed and state.failure_kind == "tool"


def test_verify_runs_the_grader_and_gates_success(tmp_path):
    (tmp_path / "x.txt").write_text("hi", encoding="utf-8")
    spec = json.dumps({"kind": "file_contains", "path": "x.txt", "text": "hi"})
    h = _harness(tmp_path, [])
    state = h.start(_task(tmp_path, spec), None)
    state = h.step(state, pb.Decision(chosen_id="verify"))
    assert state.done and not state.failed


def test_verify_fails_honestly_when_the_artifact_is_missing(tmp_path):
    spec = json.dumps({"kind": "file_contains", "path": "absent.txt", "text": "hi"})
    h = _harness(tmp_path, [])
    state = h.start(_task(tmp_path, spec), None)
    state = h.step(state, pb.Decision(chosen_id="verify"))
    assert state.failed and state.failure_kind == "verification"
