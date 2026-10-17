"""Grader resolution.

Two spec forms:

  {"kind": "file_contains", ...}      built-in grader (see soro.graders)
  "module:function"                   a project-local grader

A grader is always deterministic and always run inside the task workspace, so
`verify` is a real check and never a model's opinion of its own work.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Callable

Grader = Callable[[Path], tuple[bool, str]]


def load(spec: str) -> Grader:
    if not spec:
        raise ValueError("no grader configured for this task")

    if spec.strip().startswith("{"):
        from soro import graders

        parsed = json.loads(spec)

        def _builtin(workspace: Path) -> tuple[bool, str]:
            return graders.run_spec(parsed, workspace)

        return _builtin

    if ":" not in spec:
        raise ValueError(f"grader spec {spec!r} must be JSON or 'module:function'")
    module_name, func_name = spec.split(":", 1)
    fn = getattr(importlib.import_module(module_name), func_name)
    if not callable(fn):
        raise TypeError(f"grader {spec!r} is not callable")
    return fn


def run(spec: str, workspace: Path) -> tuple[bool, str]:
    return load(spec)(workspace)