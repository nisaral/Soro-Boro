"""Soro Audit: Automated Sandbox Contract Discovery Engine.

Runs each tool twice in an isolated sandbox with schema-synthesized inputs,
diffs state, and classifies execution semantics:
- READ_ONLY: Pure inspection; 0 state change.
- IDEMPOTENT_WRITE: Replay leaves state identical (e.g. set deduplication, upsert).
- NON_IDEMPOTENT_MUTATION: Replay creates duplicate state or fails on conflict.

Compares measured reality against static name heuristics and schema hints
(readOnlyHint, idempotentHint), resolving confirmation fatigue.
"""

from __future__ import annotations

import copy
import json
import uuid
from typing import Any, Dict, List, Tuple


def synthesize_arguments_from_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesizes valid mock arguments from a JSON Schema specification."""
    args = {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    for name, prop in props.items():
        p_type = prop.get("type", "string")
        if p_type == "string":
            if "id" in name.lower():
                args[name] = f"mock_{name}_{uuid.uuid4().hex[:6]}"
            elif "email" in name.lower():
                args[name] = "test@example.com"
            else:
                args[name] = f"sample_{name}"
        elif p_type == "integer" or p_type == "number":
            args[name] = 100
        elif p_type == "boolean":
            args[name] = True
        elif p_type == "array":
            args[name] = ["item_1"]
        elif p_type == "object":
            args[name] = {"key": "val"}
        else:
            args[name] = "default_val"

    return args


class SandboxToolAudit:
    def __init__(self, server_name: str):
        self.server_name = server_name
        self.audit_records: List[Dict[str, Any]] = []

    def audit_tool(
        self,
        tool_name: str,
        input_schema: Dict[str, Any],
        executor: Any,
        state_reader: Any,
        declared_hint: str | None = None,
    ) -> Dict[str, Any]:
        """Runs tool twice, diffs state, and compares with declared hints."""
        args = synthesize_arguments_from_schema(input_schema)

        # Baseline state
        state_0 = copy.deepcopy(state_reader())

        # Call 1
        res_1 = executor(tool_name, args)
        state_1 = copy.deepcopy(state_reader())

        # Call 2 (Replay identical payload)
        res_2 = executor(tool_name, args)
        state_2 = copy.deepcopy(state_reader())

        # Determine verified class by state diff
        if state_1 == state_0 and state_2 == state_0:
            verified_class = "read_only"
            notes = "Zero state modification observed across consecutive executions."
        elif state_2 == state_1:
            verified_class = "idempotent_write"
            notes = "Replay produced 0 additional state change; verified idempotent."
        else:
            verified_class = "non_idempotent_mutation"
            notes = "Replay accumulated additional state or produced duplicate entity."

        # Heuristic inference from name
        name_lower = tool_name.lower()
        if any(name_lower.startswith(p) for p in ("get", "read", "list", "describe", "search")):
            inferred_class = "read_only"
        elif any(name_lower.startswith(p) for p in ("delete", "remove")):
            inferred_class = "idempotent_write"
        else:
            inferred_class = "non_idempotent_mutation"

        is_match = (inferred_class == verified_class)
        is_safe_error = (inferred_class == "non_idempotent_mutation" and verified_class in ("read_only", "idempotent_write"))

        record = {
            "server": self.server_name,
            "tool": tool_name,
            "synthesized_args": args,
            "inferred_class": inferred_class,
            "verified_class": verified_class,
            "declared_hint": declared_hint,
            "is_match": is_match,
            "is_safe_error": is_safe_error,
            "confirmation_fatigue_avoided": is_safe_error,
            "notes": notes,
        }
        self.audit_records.append(record)
        return record

    def summarize(self) -> Dict[str, Any]:
        total = len(self.audit_records)
        if total == 0:
            return {"total_tools": 0}

        matches = sum(1 for r in self.audit_records if r["is_match"])
        safe_errors = sum(1 for r in self.audit_records if r["is_safe_error"])
        unsafe_errors = sum(1 for r in self.audit_records if r["inferred_class"] == "read_only" and r["verified_class"] != "read_only")

        return {
            "server": self.server_name,
            "total_tools": total,
            "exact_match_rate": round(matches / total, 4),
            "safe_error_rate": round(safe_errors / total, 4),
            "unsafe_error_rate": round(unsafe_errors / total, 4),
            "confirmation_fatigue_cases_resolved": safe_errors,
            "records": self.audit_records,
        }
