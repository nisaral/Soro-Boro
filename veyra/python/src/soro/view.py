"""Local trace viewer.

Reads run directories produced by the kernel (`events.jsonl`) and serves four
screens: run list, timeline, decision debugger, and comparison table. No login
and no database. The same files are what a later hosted history view would show.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


def load_runs(root: Path) -> list[dict[str, Any]]:
    runs_dir = root / "runs" if (root / "runs").is_dir() else root
    found: list[dict[str, Any]] = []
    if not runs_dir.is_dir():
        return found
    for events in sorted(runs_dir.glob("*/events.jsonl")):
        summary = _summarize(events)
        if summary:
            found.append(summary)
    return found


def _summarize(path: Path) -> dict[str, Any] | None:
    events = _read_events(path)
    if not events:
        return None
    first = events[0]
    last = events[-1]
    payload = _payload(first)
    state = last.get("state") or {}
    usage = last.get("usage") or {}
    switches = sum(1 for ev in events if ev.get("kind") == "harness_switch")
    decisions = [ev for ev in events if ev.get("kind") == "decision"]
    backends = sorted({(ev.get("decision") or {}).get("backend", "") for ev in decisions if (ev.get("decision") or {}).get("backend")})
    return {
        "id": path.parent.name,
        "task": payload.get("task") or state.get("task_id") or "",
        "policy": payload.get("policy") or "",
        "harness": payload.get("harness") or state.get("harness_id") or "",
        "status": str(last.get("status") or ""),
        "usd": float(usage.get("usd") or 0),
        "actions": int(usage.get("actions") or 0),
        "switches": switches,
        "backends": backends,
        "events": len(events),
        "path": str(path.parent),
    }


def _read_events(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("json_payload") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def run_detail(run_dir: Path) -> dict[str, Any]:
    events = _read_events(run_dir / "events.jsonl")
    steps = []
    for ev in events:
        kind = ev.get("kind")
        if kind not in {"decision", "action", "observation", "harness_switch", "verify", "decision_rejected", "decision_fallback", "run_finished"}:
            continue
        decision = ev.get("decision") or {}
        payload = _payload(ev)
        steps.append({
            "seq": ev.get("seq"),
            "kind": kind,
            "status": ev.get("status") or "",
            "chosen": decision.get("chosen_id") or "",
            "backend": decision.get("backend") or "",
            "rationale": decision.get("rationale") or "",
            "candidates": payload.get("candidates") or [],
            "dropped": payload.get("dropped") or {},
            "payload": {k: v for k, v in payload.items() if k not in {"candidates"}},
            "usd": (ev.get("usage") or {}).get("usd"),
            "harness": (ev.get("state") or {}).get("harness_id") or "",
            "failed": (ev.get("state") or {}).get("failed"),
        })
    return {"id": run_dir.name, "steps": steps}


def comparison_text(root: Path) -> str:
    path = root / "comparison.md" if root.is_dir() else Path()
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def page_bytes() -> bytes:
    return (Path(__file__).with_name("dashboard.html")).read_bytes()


def overview(root: Path) -> dict[str, Any]:
    from soro import __version__
    from soro.bench.targets import TARGETS

    return {
        "version": __version__,
        "runs": load_runs(root),
        "comparison": comparison_text(root),
        "targets": [
            {"id": t.id, "role": t.role, "status": t.status, "upstream": t.upstream}
            for t in TARGETS
        ],
    }


class Viewer:
    def __init__(self, root: Path):
        self.root = root

    def serve(self, host: str, port: int) -> None:
        viewer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path in {"/", "/index.html"}:
                    body = page_bytes()
                    self._send(200, "text/html; charset=utf-8", body)
                    return
                if parsed.path == "/api/overview":
                    self._json(overview(viewer.root))
                    return
                if parsed.path == "/api/runs":
                    self._json({"runs": load_runs(viewer.root), "comparison": comparison_text(viewer.root)})
                    return
                if parsed.path == "/api/run":
                    run_id = parse_qs(parsed.query).get("id", [""])[0]
                    target = (viewer.root / "runs" / run_id)
                    if not (target / "events.jsonl").is_file():
                        target = viewer.root / run_id
                    if not (target / "events.jsonl").is_file():
                        self._send(404, "application/json", b'{"error":"missing run"}')
                        return
                    self._json(run_detail(target))
                    return
                self._send(404, "text/plain", b"not found")

            def _json(self, data: dict[str, Any]) -> None:
                self._send(200, "application/json", json.dumps(data).encode("utf-8"))

            def _send(self, code: int, ctype: str, body: bytes) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args: Any) -> None:
                return

        httpd = ThreadingHTTPServer((host, port), Handler)
        print(f"veyra dashboard  http://{host}:{port}   runs: {self.root}")
        httpd.serve_forever()
