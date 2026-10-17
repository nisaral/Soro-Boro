"""Built-in deterministic graders.

A grader is the task's ground truth: it inspects the workspace and returns
(passed, detail). Graders never call a model.

Specs are JSON objects so a task file stays readable:

    {"kind": "file_contains", "path": "app.py", "text": "@app.get"}
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


def _file_exists(ws: Path, path: str = "", **_) -> tuple[bool, str]:
    target = ws / path
    return target.exists(), f"{path} {'exists' if target.exists() else 'missing'}"


def _file_contains(ws: Path, path: str = "", text: str = "", **_) -> tuple[bool, str]:
    target = ws / path
    if not target.exists():
        return False, f"{path} missing"
    body = target.read_text(encoding="utf-8", errors="replace")
    ok = text in body
    return ok, f"{path} {'contains' if ok else 'does not contain'} {text!r}"


def _file_not_contains(ws: Path, path: str = "", text: str = "", **_) -> tuple[bool, str]:
    target = ws / path
    if not target.exists():
        return False, f"{path} missing"
    ok = text not in target.read_text(encoding="utf-8", errors="replace")
    return ok, f"{path} {'no longer contains' if ok else 'still contains'} {text!r}"


def _python_ok(ws: Path, path: str = "", **_) -> tuple[bool, str]:
    target = ws / path
    if not target.exists():
        return False, f"{path} missing"
    proc = subprocess.run([sys.executable, str(target)], cwd=str(ws), capture_output=True, text=True, timeout=60)
    detail = (proc.stdout + proc.stderr).strip().splitlines()
    tail = detail[-1] if detail else ""
    return proc.returncode == 0, f"{path} exit={proc.returncode} {tail[:160]}"


def _stdout_contains(ws: Path, path: str = "", text: str = "", **_) -> tuple[bool, str]:
    target = ws / path
    if not target.exists():
        return False, f"{path} missing"
    proc = subprocess.run([sys.executable, str(target)], cwd=str(ws), capture_output=True, text=True, timeout=60)
    out = proc.stdout + proc.stderr
    ok = text in out
    return ok, f"stdout {'contains' if ok else 'missing'} {text!r}"


def _pytest_ok(ws: Path, **_ ) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "-x"],
        cwd=str(ws), capture_output=True, text=True, timeout=180,
    )
    tail = [l for l in (proc.stdout + proc.stderr).splitlines() if l.strip()]
    return proc.returncode == 0, (tail[-1] if tail else "pytest produced no output")[:200]


def _all_of(ws: Path, specs: list[dict[str, Any]] | None = None, **_) -> tuple[bool, str]:
    details: list[str] = []
    ok_all = True
    for spec in specs or []:
        ok, detail = run_spec(spec, ws)
        ok_all = ok_all and ok
        details.append(("ok " if ok else "FAIL ") + detail)
        if not ok_all:
            break
    return ok_all, "; ".join(details)


KINDS: dict[str, Callable[..., tuple[bool, str]]] = {
    "all_of": _all_of,
    "file_exists": _file_exists,
    "file_contains": _file_contains,
    "file_not_contains": _file_not_contains,
    "python_ok": _python_ok,
    "stdout_contains": _stdout_contains,
    "pytest_ok": _pytest_ok,
}


def run_spec(spec: dict[str, Any], workspace: Path) -> tuple[bool, str]:
    kind = str(spec.get("kind", ""))
    fn = KINDS.get(kind)
    if fn is None:
        return False, f"unknown grader kind {kind!r}; known: {sorted(KINDS)}"
    return fn(workspace, **{k: v for k, v in spec.items() if k != "kind"})