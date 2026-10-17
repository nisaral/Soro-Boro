"""Submit construction: the scripted and live model paths must not be confused."""

import json
from pathlib import Path

from veyra.bench import runner
from veyra.bench.tasks import by_split


def _task():
    return by_split("dev")[0]


def _arm():
    return runner.Arm("fixed:native", "fixed", "native", "fixed")


def _options(req):
    return json.loads(req.options_json)


def test_offline_submit_carries_per_harness_scripts(tmp_path):
    req = runner.build_submit(_task(), _arm(), tmp_path)
    opts = _options(req)
    assert opts["model_mode"] == "offline"
    assert set(opts["offline_scripts"]) == {"native", "repair", "langgraph"}
    assert opts["workspace"] == str(tmp_path)


def test_live_submit_drops_scripts_and_sets_model_names(tmp_path):
    model = {"mode": "ollama", "cheap": "qwen2.5-coder:3b", "strong": "qwen2.5-coder:7b",
             "base_url": "http://127.0.0.1:11434"}
    opts = _options(runner.build_submit(_task(), _arm(), tmp_path, model))
    assert opts["model_mode"] == "ollama"
    assert "offline_scripts" not in opts
    assert opts["model_cheap"] == "qwen2.5-coder:3b"
    assert opts["model_strong"] == "qwen2.5-coder:7b"
    assert opts["base_url"] == "http://127.0.0.1:11434"


def test_blank_live_model_names_are_not_sent(tmp_path):
    opts = _options(runner.build_submit(_task(), _arm(), tmp_path, {"mode": "ollama", "cheap": "", "strong": ""}))
    assert "model_cheap" not in opts and "model_strong" not in opts


def test_submit_carries_grader_and_oracle_metadata(tmp_path):
    req = runner.build_submit(_task(), _arm(), tmp_path)
    assert req.task.metadata["oracle.prefer_harness"]
    assert req.task.metadata["grader"]


def test_test_arms_keeps_the_offline_ceiling_and_the_dev_pick():
    names = [a.name for a in runner.test_arms("langgraph")]
    assert names[0] == "fixed:langgraph"
    assert "oracle" in names
    assert all(not n.startswith("fixed:") for n in names[1:])


def test_model_detail_is_readable_for_both_modes():
    assert "scripted" in runner.model_detail({"mode": "offline"})
    assert "qwen" in runner.model_detail({"mode": "ollama", "cheap": "qwen", "strong": "qwen"})
