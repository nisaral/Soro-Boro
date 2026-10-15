"""Lexical overlap gate for protocol v2. Name tokens longer than 3 chars must not appear in the query."""

from __future__ import annotations

import re


def name_tokens(tool_name: str) -> set[str]:
    parts = re.findall(r"[A-Za-z][a-z]+|[A-Z]+(?=[A-Z][a-z]|$)|\d+", tool_name.replace("-", "_"))
    return {p.lower() for p in parts if len(p) > 3}


def query_tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z]+", text) if len(t) > 3}


def illegal_overlap(gold: str, text: str) -> set[str]:
    return name_tokens(gold) & query_tokens(text)
