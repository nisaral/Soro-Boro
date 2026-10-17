"""Golden-file and schema stability tests for HandoffV1."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from veyra.handoff import compile_handoff, shadow_record

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "handoff.v1.json"
GOLDEN_DIR = Path(__file__).parent / "data" / "golden"


@pytest.fixture
def handoff_schema() -> dict:
    assert SCHEMA_PATH.exists(), f"Schema missing at {SCHEMA_PATH}"
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_golden_minimal_validates(handoff_schema: dict):
    minimal_path = GOLDEN_DIR / "handoff_v1_minimal.json"
    doc = json.loads(minimal_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=doc, schema=handoff_schema)
    assert doc["version"] == "1"
    assert doc["shadow"] is True
    assert doc["items"] == []


def test_golden_full_validates(handoff_schema: dict):
    full_path = GOLDEN_DIR / "handoff_v1_full.json"
    doc = json.loads(full_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=doc, schema=handoff_schema)
    assert doc["version"] == "1"
    assert doc["shadow"] is False
    assert len(doc["items"]) == 5
    kinds = {item["kind"] for item in doc["items"]}
    assert kinds == {"decision", "failed_action", "open_subgoal", "verification", "observation"}


def test_compile_handoff_strictly_validates_against_schema(tmp_path: Path, handoff_schema: dict):
    events_file = tmp_path / "events.jsonl"
    events_file.write_text(
        json.dumps({"kind": "run_started", "json_payload": json.dumps({"task": "tb2-golden-task", "harness": "native"})}) + "\n"
        + json.dumps({"kind": "decision", "decision": {"chosen_id": "switch", "rationale": "stuck on error"}}) + "\n"
        + json.dumps({"kind": "decision_fallback", "json_payload": "timeout fallback"}) + "\n"
        + json.dumps({"kind": "verify", "status": "assertions passed"}) + "\n",
        encoding="utf-8",
    )

    doc = compile_handoff(events_file, to_harness="repair", shadow=False)
    jsonschema.validate(instance=doc, schema=handoff_schema)
    assert doc["version"] == "1"
    assert doc["task_id"] == "tb2-golden-task"
    assert doc["from_harness"] == "native"
    assert doc["to_harness"] == "repair"
    assert doc["shadow"] is False
    assert len(doc["items"]) >= 3


def test_schema_rejects_missing_required_fields(handoff_schema: dict):
    invalid_doc = {
        "version": "1",
        "task_id": "tb2-task-01",
        # missing from_harness and items
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_doc, schema=handoff_schema)


def test_schema_rejects_invalid_item_kind(handoff_schema: dict):
    invalid_doc = {
        "version": "1",
        "task_id": "tb2-task-01",
        "from_harness": "native",
        "items": [
            {"kind": "unsupported_arbitrary_kind", "text": "bad item"}
        ]
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_doc, schema=handoff_schema)


def test_schema_rejects_unsupported_version(handoff_schema: dict):
    invalid_doc = {
        "version": "2",  # Schema enforces const "1"
        "task_id": "tb2-task-01",
        "from_harness": "native",
        "items": []
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=invalid_doc, schema=handoff_schema)
