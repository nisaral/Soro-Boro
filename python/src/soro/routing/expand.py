"""Document expansion for retrieval. Never copies test queries."""

from __future__ import annotations

import re

from soro.routing.scale import ToolSpec


def split_identifier(name: str) -> str:
    parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|$)|\d+", name.replace("-", "_"))
    return " ".join(p.lower() for p in parts)


def synthetic_examples(spec: ToolSpec) -> list[str]:
    """Offline templates from the tool's own name/description. Provenance: template, not test set."""
    words = split_identifier(spec.name)
    first = spec.description.split(".")[0][:160]
    return [
        f"I need to {words}",
        f"Can you {words} for me",
        first,
    ]


def expand_document(spec: ToolSpec, extra_params: list[str] | None = None) -> str:
    bits = [
        f"Name: {spec.name}",
        f"Tokens: {split_identifier(spec.name)}",
        f"Purpose: {spec.description}",
    ]
    if extra_params:
        bits.append("Parameters: " + " ".join(extra_params))
    bits.append("Typical requests:")
    bits.extend(f"- {ex}" for ex in synthetic_examples(spec))
    return "\n".join(bits)
