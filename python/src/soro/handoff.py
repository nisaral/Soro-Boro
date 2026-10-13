"""Compile HandoffV1 from a kernel event log.

Kev does not write this document. An extractor proposes items; a selector may
later drop them. Shadow mode writes the payload without switching.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1"


def items_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for ev in events:
        kind = ev.get("kind")
        decision = ev.get("decision") or {}
        state = ev.get("state") or {}
        if kind == "decision":
            items.append({
                "kind": "decision",
                "text": f"{decision.get('chosen_id') or ''} {decision.get('rationale') or ''}".strip(),
                "keep_score": None,
            })
        if kind in {"decision_rejected", "decision_fallback"}:
            items.append({
                "kind": "failed_action",
                "text": str(ev.get("json_payload") or kind),
                "keep_score": None,
            })
        if state.get("failed"):
            items.append({
                "kind": "failed_action",
                "text": str(state.get("failure_kind") or "failed"),
                "keep_score": None,
            })
        if kind == "verify":
            items.append({
                "kind": "verification",
                "text": str(ev.get("status") or "verify"),
                "keep_score": None,
            })
    return items


def compile_handoff(events_path: Path, *, to_harness: str | None = None, shadow: bool = True) -> dict[str, Any]:
    events = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    first = events[0] if events else {}
    payload = first.get("json_payload") or "{}"
    if isinstance(payload, str):
        try:
            meta = json.loads(payload)
        except json.JSONDecodeError:
            meta = {}
    else:
        meta = payload
    last_state = (events[-1].get("state") if events else {}) or {}
    usage = (events[-1].get("usage") if events else {}) or {}
    return {
        "version": SCHEMA_VERSION,
        "task_id": meta.get("task") or last_state.get("task_id") or "",
        "from_harness": meta.get("harness") or last_state.get("harness_id") or "",
        "to_harness": to_harness,
        "shadow": shadow,
        "budget": {
            "usd_spent": float(usage.get("usd") or 0),
            "usd_remaining": None,
            "actions": int(usage.get("actions") or 0),
        },
        "items": items_from_events(events),
    }


def shadow_record(instruction: str, reason: str) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "task_id": "",
        "from_harness": "",
        "to_harness": None,
        "shadow": True,
        "budget": {},
        "items": [{"kind": "open_subgoal", "text": instruction[:500], "keep_score": None},
                  {"kind": "decision", "text": reason, "keep_score": None}],
    }
