"""The tool surface exposed to a harness.

Tools act on the environment; decision models never touch them. The kernel
plans `TOOL_CALL` actions, the policy engine gates them by permission, and the
harness executes them here.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# Commands a benchmark task is allowed to run. Anything else is refused before
# a shell is involved, which keeps the demo safe to run unattended.
SHELL_ALLOWLIST = (
    "python", "python3", "pytest", "echo", "dir", "ls", "cat", "type",
    "git status", "git diff", "git log", "findstr", "grep", "sort", "wc",
)


@dataclass
class ToolSpec:
    name: str
    description: str
    permissions: list[str]
    fn: Callable[[dict[str, Any], "ToolContext"], tuple[bool, str]]


@dataclass
class ToolContext:
    workspace: Path
    allow_shell: bool = True
    timeout_s: float = 30.0
    max_output: int = 4000


def _arg_path(args: dict) -> str:
    """Accept the documented `path` key and the `filename` alias models often emit."""
    return str(args.get("path") or args.get("filename") or args.get("file") or "")


def _safe_path(ctx: ToolContext, raw: str) -> Path:
    """Resolve a path and refuse to escape the task workspace."""
    candidate = (ctx.workspace / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
    root = ctx.workspace.resolve()
    if root != candidate and root not in candidate.parents:
        raise PermissionError(f"path {raw!r} escapes the workspace")
    return candidate


def _read_file(args: dict[str, Any], ctx: ToolContext) -> tuple[bool, str]:
    path = _safe_path(ctx, _arg_path(args))
    if not path.exists():
        return False, f"file not found: {path.name}"
    text = path.read_text(encoding="utf-8", errors="replace")
    return True, text[: ctx.max_output]


def _write_file(args: dict[str, Any], ctx: ToolContext) -> tuple[bool, str]:
    path = _safe_path(ctx, _arg_path(args))
    path.parent.mkdir(parents=True, exist_ok=True)
    content = str(args.get("content", ""))
    if args.get("append"):
        with path.open("a", encoding="utf-8") as fh:
            fh.write(content)
    else:
        path.write_text(content, encoding="utf-8")
    return True, f"wrote {len(content)} bytes to {path.name}"


def _list_dir(args: dict[str, Any], ctx: ToolContext) -> tuple[bool, str]:
    rel = str(args.get("path", "."))
    path = _safe_path(ctx, rel)
    if not path.exists():
        return False, f"no such directory: {rel}"
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
    return True, "\n".join(entries[:200])


def _grep(args: dict[str, Any], ctx: ToolContext) -> tuple[bool, str]:
    pattern = str(args.get("pattern", ""))
    if not pattern:
        return False, "grep needs a pattern"
    regex = re.compile(pattern)
    hits: list[str] = []
    for path in sorted(ctx.workspace.rglob("*")):
        if not path.is_file():
            continue
        try:
            for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if regex.search(line):
                    hits.append(f"{path.relative_to(ctx.workspace)}:{lineno}: {line.strip()[:200]}")
                    if len(hits) >= 50:
                        return True, "\n".join(hits)
        except OSError:
            continue
    return True, "\n".join(hits) if hits else "no matches"


def _run_command(args: dict[str, Any], ctx: ToolContext) -> tuple[bool, str]:
    command = str(args.get("command", "")).strip()
    if not command:
        return False, "run_command needs a command"
    if not ctx.allow_shell:
        return False, "shell access is disabled by policy"
    lowered = command.lower()
    if not any(lowered.startswith(prefix) for prefix in SHELL_ALLOWLIST):
        return False, f"command not in the allowlist: {command.split()[0]!r}"
    # `python` is not guaranteed to be on the PATH of the shell we spawn (it is
    # not on Windows), so bind it to the interpreter running this harness.
    if lowered.startswith(("python ", "python3 ")):
        command = f'"{sys.executable}"' + command[len(command.split(" ", 1)[0]):]
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(ctx.workspace),
            capture_output=True,
            text=True,
            timeout=ctx.timeout_s,
        )
    except subprocess.TimeoutExpired:
        return False, f"command timed out after {ctx.timeout_s}s"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out[: ctx.max_output] or f"(exit {proc.returncode})"


def _run_python_file(args: dict[str, Any], ctx: ToolContext) -> tuple[bool, str]:
    rel = _arg_path(args)
    path = _safe_path(ctx, rel)
    if not path.exists():
        return False, f"file not found: {rel}"
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(ctx.workspace), capture_output=True, text=True, timeout=ctx.timeout_s,
        )
    except subprocess.TimeoutExpired:
        return False, f"python {rel} timed out"
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out[: ctx.max_output]


REGISTRY: dict[str, ToolSpec] = {
    "read_file": ToolSpec("read_file", "Read a UTF-8 text file inside the workspace.",
                          ["fs_read"], _read_file),
    "write_file": ToolSpec("write_file", "Write (or append) a UTF-8 text file inside the workspace.",
                           ["fs_write"], _write_file),
    "list_dir": ToolSpec("list_dir", "List the entries of a directory inside the workspace.",
                         ["fs_read"], _list_dir),
    "grep": ToolSpec("grep", "Search the workspace with a regular expression.",
                     ["fs_read"], _grep),
    "run_command": ToolSpec("run_command", "Run an allowlisted shell command in the workspace.",
                            ["shell"], _run_command),
    "run_python_file": ToolSpec("run_python_file", "Execute a Python file inside the workspace.",
                                ["shell"], _run_python_file),
}


def tool_names() -> list[str]:
    return sorted(REGISTRY)


def describe_tools(names: list[str] | None = None) -> str:
    chosen = names or tool_names()
    return "\n".join(f"- {n}: {REGISTRY[n].description}" for n in chosen if n in REGISTRY)


def required_permissions(names: list[str] | None = None) -> list[str]:
    perms: list[str] = []
    for n in names or tool_names():
        spec = REGISTRY.get(n)
        if spec:
            for p in spec.permissions:
                if p not in perms:
                    perms.append(p)
    return perms


def call_tool(name: str, args: dict[str, Any], ctx: ToolContext) -> tuple[bool, str]:
    spec = REGISTRY.get(name)
    if spec is None:
        return False, f"unknown tool {name!r}"
    if name == "__fault__":
        return False, "injected fault"
    try:
        return spec.fn(args, ctx)
    except PermissionError as exc:
        return False, str(exc)
    except Exception as exc:  # tool failures are observations, not crashes
        return False, f"{type(exc).__name__}: {exc}"