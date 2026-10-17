"""Graders are the ground truth, so they must be deterministic and honest."""

from pathlib import Path

from veyra import graders


def test_file_contains_pass_and_fail(tmp_path):
    (tmp_path / "m.py").write_text("value = 1\n", encoding="utf-8")
    assert graders.run_spec({"kind": "file_contains", "path": "m.py", "text": "value"}, tmp_path)[0]
    ok, detail = graders.run_spec({"kind": "file_contains", "path": "m.py", "text": "missing"}, tmp_path)
    assert not ok and "does not contain" in detail


def test_missing_file_is_a_failure_not_an_exception(tmp_path):
    ok, detail = graders.run_spec({"kind": "file_contains", "path": "nope.py", "text": "x"}, tmp_path)
    assert not ok and "missing" in detail


def test_all_of_short_circuits_on_first_failure(tmp_path):
    (tmp_path / "m.py").write_text("value = 1\n", encoding="utf-8")
    ok, detail = graders.run_spec(
        {"kind": "all_of", "specs": [
            {"kind": "file_contains", "path": "m.py", "text": "value"},
            {"kind": "file_contains", "path": "m.py", "text": "absent"},
        ]}, tmp_path)
    assert not ok and "FAIL" in detail


def test_unknown_kind_is_reported(tmp_path):
    ok, detail = graders.run_spec({"kind": "quantum"}, tmp_path)
    assert not ok and "unknown grader kind" in detail


def test_grader_is_deterministic(tmp_path):
    (tmp_path / "m.py").write_text("value = 1\n", encoding="utf-8")
    spec = {"kind": "file_contains", "path": "m.py", "text": "value"}
    assert graders.run_spec(spec, tmp_path) == graders.run_spec(spec, tmp_path)


def test_stdout_contains_runs_the_file(tmp_path):
    (tmp_path / "check.py").write_text("print('PASS')\n", encoding="utf-8")
    ok, detail = graders.run_spec({"kind": "stdout_contains", "path": "check.py", "text": "PASS"}, tmp_path)
    assert ok, detail
