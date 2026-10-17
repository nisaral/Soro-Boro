"""Veyra Registry Module."""

from soro.registry.resolver import CandidateResolver, DeterministicCandidateResolver
from soro.registry.tool_registry import ToolDefinition, ToolRegistry

__all__ = [
    "ToolDefinition",
    "ToolRegistry",
    "CandidateResolver",
    "DeterministicCandidateResolver",
]
