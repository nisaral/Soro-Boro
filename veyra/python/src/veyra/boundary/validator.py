"""Veyra Safe Argument Validator & Normalizer.

Applies ONLY provably safe, semantics-preserving normalizations:
- "42" -> 42 (when target is integer)
- "42.5" -> 42.5 (when target is float/number)
- "true" / "false" -> True / False (when target is boolean)
- "ACTIVE" -> "active" (when unique case-insensitive enum match exists)
- Normalized ISO date formatting (e.g. "2026/10/06" -> "2026-10-06")
- Whitespace stripping on text parameters
- Safe dropping of unknown extra properties if schema forbids additionalProperties

Zero semantic guessing. If ambiguous or missing required fields, raises SchemaValidationError.
"""

from __future__ import annotations

import datetime
import inspect
import re
from typing import Any, Callable, get_type_hints


class SchemaValidationError(ValueError):
    """Raised when proposed arguments cannot be safely normalized or violate schema."""

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None):
        self.field = field
        self.details = details or {}
        super().__init__(message)


def normalize_iso_date(val: str) -> str:
    """Normalize date strings like '2026/10/06' or '2026-10-06T00:00:00Z' to '2026-10-06'."""
    val = val.strip()
    # Check YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        return val
    # Check YYYY/MM/DD
    if re.match(r"^\d{4}/\d{2}/\d{2}$", val):
        return val.replace("/", "-")
    # Check ISO datetime e.g. 2026-10-06T14:00:00
    if "T" in val:
        date_part = val.split("T")[0]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
            return date_part
    # Fallback to date parsing
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.datetime.strptime(val, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return val


def normalize_value(val: Any, target_type: str | type, allowed_enums: list[Any] | None = None) -> Any:
    """Safely normalize a single parameter value preserving strict semantics."""
    if val is None:
        return None

    # Handle enums with unique case-insensitive match
    if allowed_enums:
        if val in allowed_enums:
            return val
        if isinstance(val, str):
            matches = [e for e in allowed_enums if str(e).strip().lower() == val.strip().lower()]
            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                raise SchemaValidationError(f"Ambiguous enum match for '{val}' across {allowed_enums}")
            else:
                raise SchemaValidationError(f"Value '{val}' is not in allowed enum set: {allowed_enums}")

    # Determine type name
    type_name = ""
    if isinstance(target_type, str):
        type_name = target_type.lower()
    elif isinstance(target_type, type):
        type_name = target_type.__name__.lower()

    # 1. Integer normalization
    if type_name in ("int", "integer"):
        if isinstance(val, int) and not isinstance(val, bool):
            return val
        if isinstance(val, str):
            val_clean = val.strip()
            if re.match(r"^-?\d+$", val_clean):
                return int(val_clean)
        if isinstance(val, float) and val.is_integer():
            return int(val)
        raise SchemaValidationError(f"Cannot safely coerce '{val}' ({type(val).__name__}) to integer")

    # 2. Float / Number normalization
    if type_name in ("float", "number"):
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
        if isinstance(val, str):
            val_clean = val.strip()
            try:
                return float(val_clean)
            except ValueError:
                pass
        raise SchemaValidationError(f"Cannot safely coerce '{val}' ({type(val).__name__}) to float")

    # 3. Boolean normalization
    if type_name in ("bool", "boolean"):
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            v = val.strip().lower()
            if v in ("true", "1", "yes", "on"):
                return True
            if v in ("false", "0", "no", "off"):
                return False
        if isinstance(val, int):
            if val == 1:
                return True
            if val == 0:
                return False
        raise SchemaValidationError(f"Cannot safely coerce '{val}' to boolean")

    # 4. String normalization (strip whitespace, date check)
    if type_name in ("str", "string"):
        if isinstance(val, str):
            val_str = val.strip()
            return val_str
        # Allow scalar string conversion only for int/float
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return str(val)

    return val


def validate_and_normalize(
    proposed_args: dict[str, Any],
    schema: dict[str, Any] | None = None,
    fn: Callable[..., Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Validate and safely normalize tool call arguments.

    Returns:
        (normalized_arguments, list_of_applied_corrections)
    """
    normalized: dict[str, Any] = {}
    corrections: list[str] = []

    # If JSON schema is provided
    if schema and "properties" in schema:
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        additional_allowed = schema.get("additionalProperties", True)

        # Check required fields
        for req in required:
            if req not in proposed_args or proposed_args[req] is None:
                raise SchemaValidationError(f"Missing required argument '{req}'", field=req)

        # Normalize provided arguments
        for k, val in proposed_args.items():
            if k not in properties:
                if not additional_allowed:
                    corrections.append(f"Dropped unknown property '{k}'")
                    continue
                else:
                    normalized[k] = val
                    continue

            prop_def = properties[k]
            target_type = prop_def.get("type", "string")
            allowed_enums = prop_def.get("enum")
            format_spec = prop_def.get("format")

            # Format-specific normalization
            if format_spec == "date" and isinstance(val, str):
                orig = val
                norm_date = normalize_iso_date(val)
                if norm_date != orig:
                    corrections.append(f"Normalized date '{k}': '{orig}' -> '{norm_date}'")
                val = norm_date

            norm_val = normalize_value(val, target_type, allowed_enums)
            if norm_val != val:
                corrections.append(f"Coerced '{k}': {val!r} -> {norm_val!r}")
            normalized[k] = norm_val

        return normalized, corrections

    # If Python callable signature is available
    if fn is not None:
        sig = inspect.signature(fn)
        type_hints = get_type_hints(fn) if hasattr(fn, "__annotations__") else {}
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())

        # Check required parameters
        for p_name, param in sig.parameters.items():
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if param.default is inspect.Parameter.empty and p_name not in proposed_args:
                raise SchemaValidationError(f"Missing required parameter '{p_name}'", field=p_name)

        # Normalize arguments
        for k, val in proposed_args.items():
            if k not in sig.parameters:
                if not has_kwargs:
                    corrections.append(f"Dropped parameter '{k}' not in function signature")
                    continue
                else:
                    normalized[k] = val
                    continue

            target_type = type_hints.get(k, sig.parameters[k].annotation)
            if target_type is inspect.Parameter.empty:
                normalized[k] = val
                continue

            norm_val = normalize_value(val, target_type)
            if norm_val != val:
                corrections.append(f"Coerced '{k}': {val!r} -> {norm_val!r}")
            normalized[k] = norm_val

        return normalized, corrections

    # Fallback when neither schema nor fn signature is known: identity
    return dict(proposed_args), []
