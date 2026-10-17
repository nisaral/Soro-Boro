"""OpenAPI 3.0 / Swagger specification importer and contract inferrer.

Extracts operations into ToolSpec / ExecutionContract and infers:
- HTTP verb heuristics:
    * GET -> READ_ONLY, idempotent=True
    * PUT -> IDEMPOTENT_WRITE, idempotent=True
    * DELETE -> IDEMPOTENT_WRITE, idempotent=True
    * POST -> NON_IDEMPOTENT_MUTATION (unless Idempotency-Key / client token parameter detected)
- Required parameter slot extraction
- Reversibility and probe inference
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from soro.core.execution_contract import SideEffectClass


@dataclass
class InferredContract:
    operation_id: str
    path: str
    http_verb: str
    summary: str
    description: str
    side_effect_class: SideEffectClass
    is_idempotent: bool
    required_slots: List[str]
    optional_slots: List[str]
    has_idempotency_key_param: bool
    status_code_probe: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "path": self.path,
            "http_verb": self.http_verb,
            "summary": self.summary,
            "description": self.description,
            "side_effect_class": self.side_effect_class.value,
            "is_idempotent": self.is_idempotent,
            "required_slots": self.required_slots,
            "optional_slots": self.optional_slots,
            "has_idempotency_key_param": self.has_idempotency_key_param,
        }


class OpenAPIImporter:
    """Parses OpenAPI documents and extracts inferred tool contracts."""

    @classmethod
    def load_spec(cls, file_path_or_str: str | Path) -> Dict[str, Any]:
        path = Path(file_path_or_str)
        if path.is_file():
            content = path.read_text(encoding="utf-8")
        else:
            content = str(file_path_or_str)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return yaml.safe_load(content)

    @classmethod
    def import_operations(cls, spec: Dict[str, Any]) -> List[InferredContract]:
        paths = spec.get("paths", {})
        contracts: List[InferredContract] = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method, op in path_item.items():
                verb = method.upper()
                if verb not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    continue
                if not isinstance(op, dict):
                    continue

                op_id = op.get("operationId") or f"{verb.lower()}_{path.replace('/', '_').strip('_')}"
                summary = op.get("summary", "")
                description = op.get("description", "")

                # Extract parameters
                required_slots = []
                optional_slots = []
                has_idemp_key = False

                params = list(path_item.get("parameters", [])) + list(op.get("parameters", []))
                for p in params:
                    if isinstance(p, dict):
                        p_name = p.get("name", "")
                        if not p_name:
                            continue
                        if p_name.lower() in ("idempotency-key", "idempotency_key", "x-idempotency-key", "request-id"):
                            has_idemp_key = True
                        if p.get("required", False):
                            required_slots.append(p_name)
                        else:
                            optional_slots.append(p_name)

                # Request body properties
                req_body = op.get("requestBody", {})
                if isinstance(req_body, dict):
                    content = req_body.get("content", {})
                    json_schema = content.get("application/json", {}).get("schema", {})
                    props = json_schema.get("properties", {})
                    req_list = json_schema.get("required", [])
                    for prop_name, prop_def in props.items():
                        if prop_name.lower() in ("idempotency-key", "idempotency_key", "request_id"):
                            has_idemp_key = True
                        if prop_name in req_list:
                            required_slots.append(prop_name)
                        else:
                            optional_slots.append(prop_name)

                # Contract inference rule
                if verb == "GET":
                    sec = SideEffectClass.READ_ONLY
                    idemp = True
                elif verb in ("PUT", "DELETE"):
                    sec = SideEffectClass.IDEMPOTENT_WRITE
                    idemp = True
                elif verb in ("POST", "PATCH"):
                    if has_idemp_key:
                        sec = SideEffectClass.IDEMPOTENT_WRITE
                        idemp = True
                    else:
                        sec = SideEffectClass.NON_IDEMPOTENT_MUTATION
                        idemp = False
                else:
                    sec = SideEffectClass.NON_IDEMPOTENT_MUTATION
                    idemp = False

                contracts.append(
                    InferredContract(
                        operation_id=op_id,
                        path=path,
                        http_verb=verb,
                        summary=summary,
                        description=description,
                        side_effect_class=sec,
                        is_idempotent=idemp,
                        required_slots=sorted(list(set(required_slots))),
                        optional_slots=sorted(list(set(optional_slots))),
                        has_idempotency_key_param=has_idemp_key,
                    )
                )

        return contracts
