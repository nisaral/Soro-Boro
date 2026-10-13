"""Drive the kernel over gRPC, one run per (task, arm).

The runner is deliberately dumb: it submits, watches, and records. All the
intelligence under test lives in the kernel and in the decision backends, which
is what makes the comparison meaningful.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import grpc

from soro.bench.tasks import BenchTask
from soro.v1 import runtime_pb2 as pb
from soro.v1 import runtime_pb2_grpc as pb_grpc


@dataclass(frozen=True)
class Arm:
    name: str
    policy: str
    harness: str
    kind: str  # fixed | adaptive | oracle


def default_arms(include_kev: bool = False) -> list[Arm]:
    arms = [
        Arm("fixed:native", "fixed", "native", "fixed"),
        Arm("fixed:repair", "fixed", "repair", "fixed"),
        Arm("fixed:langgraph", "fixed", "langgraph", "fixed"),
        Arm("veyra:heuristic", "heuristic", "native", "adaptive"),
        Arm("veyra:von", "von", "native", "adaptive"),
        Arm("veyra:bandit", "bandit", "native", "adaptive"),
        Arm("oracle", "oracle", "native", "oracle"),
    ]
    if include_kev:
        arms.insert(4, Arm("veyra:kev", "kev", "native", "adaptive"))
    return arms


def test_arms(best_fixed: str, include_kev: bool = False) -> list[Arm]:
    """The held-out protocol: only the dev-selected baseline plus adaptives.

    Running every fixed arm on test as well would invite post-hoc selection of a
    different baseline, which is exactly what pre-registration is meant to stop.
    """
    return [
        Arm(f"fixed:{best_fixed}", "fixed", best_fixed, "fixed"),
        Arm("veyra:heuristic", "heuristic", "native", "adaptive"),
        *( [Arm("veyra:kev", "kev", "native", "adaptive")] if include_kev else [] ),
        Arm("veyra:von", "von", "native", "adaptive"),
        Arm("veyra:bandit", "bandit", "native", "adaptive"),
        Arm("oracle", "oracle", "native", "oracle"),
    ]


def materialize(task: BenchTask, root: Path) -> Path:
    ws = root / task.id
    if ws.exists():
        import shutil

        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)
    for rel, content in task.seed.items():
        target = ws / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return ws


def model_detail(model: dict[str, Any] | None) -> str:
    model = model or {"mode": "offline"}
    mode = str(model.get("mode", "offline"))
    if mode == "offline":
        return "scripted model"
    cheap = model.get("cheap") or "default"
    strong = model.get("strong") or "default"
    return f"{cheap} / {strong} @ {model.get('base_url') or 'default endpoint'}"


def build_submit(task: BenchTask, arm: Arm, ws: Path, model: dict[str, Any] | None = None) -> pb.SubmitRequest:
    metadata = {
        "grader": task.grader_spec(),
        "category": task.category,
        "split": task.split,
        "oracle.prefer_harness": task.oracle_prefer,
    }
    model = model or {"mode": "offline"}
    mode = str(model.get("mode", "offline"))
    options: dict[str, Any] = {"model_mode": mode, "workspace": str(ws)}
    if mode == "offline":
        # The scripted model replays a per-harness script; a live model does not.
        options["offline_scripts"] = {
            "native": task.script_native,
            "repair": task.script_repair or task.script_native,
            "langgraph": task.script_langgraph,
        }
    else:
        for key in ("cheap", "strong", "base_url", "api_key"):
            if model.get(key):
                options[f"model_{key}" if key in ("cheap", "strong") else key] = model[key]
    budget = task.budget
    return pb.SubmitRequest(
        task=pb.TaskSpec(
            id=task.id,
            instruction=task.instruction,
            workspace=str(ws),
            metadata=metadata,
            category=[task.category],
            budget=pb.Budget(
                max_actions=int(budget.get("max_actions", 16)),
                max_usd=float(budget.get("max_usd", 0.6)),
                max_wall_ms=int(budget.get("max_wall_ms", 0)),
                max_tokens=int(budget.get("max_tokens", 0)),
            ),
        ),
        policy_backend=arm.policy,
        start_harness=arm.harness,
        options_json=json.dumps(options),
    )


def watch_until_done(stub: pb_grpc.KernelServiceStub, run_id: str, timeout_s: float = 180.0) -> dict[str, Any]:
    summary: dict[str, Any] = {"status": "UNKNOWN", "usd": 0.0, "wall_ms": 0, "actions": 0, "switches": 0,
                              "decisions": 0, "events": 0, "checkpoints": 0, "error": "",
                              "backends": [], "harness_engines": []}
    deadline = time.time() + timeout_s
    try:
        for ev in stub.Watch(pb.WatchRequest(run_id=run_id), timeout=timeout_s):
            summary["events"] += 1
            if ev.kind == "harness_switch":
                summary["switches"] += 1
            elif ev.kind == "decision":
                summary["decisions"] += 1
                backend = ev.decision.backend if ev.HasField("decision") else ""
                if backend and backend != "kernel" and backend not in summary["backends"]:
                    summary["backends"].append(backend)
            elif ev.kind == "checkpoint":
                summary["checkpoints"] += 1
            if ev.HasField("state"):
                engine = ev.state.variables.get("langgraph.engine", "")
                if engine and engine not in summary["harness_engines"]:
                    summary["harness_engines"].append(engine)
            if ev.usage:
                summary["usd"] = ev.usage.usd
                summary["wall_ms"] = ev.usage.wall_ms
                summary["actions"] = ev.usage.actions
            if ev.kind == "run_finished":
                summary["status"] = pb.RunStatus.Name(ev.status)
                if ev.json_payload:
                    try:
                        summary["error"] = json.loads(ev.json_payload).get("error", "")
                    except json.JSONDecodeError:
                        pass
                break
            if time.time() > deadline:
                summary["status"] = "TIMEOUT"
                break
    except grpc.RpcError as exc:
        summary["status"] = "RPC_ERROR"
        summary["error"] = str(exc)
    return summary


def run_arm(addr: str, task: BenchTask, arm: Arm, ws_root: Path, timeout_s: float = 180.0,
            attempts: int = 3, model: dict[str, Any] | None = None) -> dict[str, Any]:
    ws = materialize(task, ws_root / arm.name.replace(":", "_"))
    last: dict[str, Any] | None = None
    for attempt in range(attempts):
        with grpc.insecure_channel(addr) as channel:
            stub = pb_grpc.KernelServiceStub(channel)
            try:
                resp = stub.Submit(build_submit(task, arm, ws, model), timeout=30)
            except grpc.RpcError as exc:
                last = {"task": task.id, "arm": arm.name, "category": task.category, "split": task.split,
                        "status": "SUBMIT_FAILED", "usd": 0.0, "wall_ms": 0, "actions": 0, "switches": 0,
                        "decisions": 0, "events": 0, "checkpoints": 0, "error": str(exc), "run_id": "",
                        "backends": [], "harness_engines": []}
                time.sleep(0.5 * (attempt + 1))
                continue
            summary = watch_until_done(stub, resp.run_id, timeout_s)
        if summary["status"] not in ("RPC_ERROR", "TIMEOUT") or attempt == attempts - 1:
            return {"task": task.id, "arm": arm.name, "category": task.category, "split": task.split,
                    "run_id": resp.run_id, **summary}
        last = {"task": task.id, "arm": arm.name, "category": task.category, "split": task.split,
                "run_id": resp.run_id, **summary}
        time.sleep(0.5 * (attempt + 1))
    assert last is not None
    return last


def run_all(tasks: list[BenchTask], arms: list[Arm], addr: str, ws_root: Path,
            timeout_s: float = 180.0, on_result=None,
            model: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for task in tasks:
        for arm in arms:
            record = run_arm(addr, task, arm, ws_root, timeout_s, model=model)
            results.append(record)
            if on_result:
                on_result(record)
    return results


def meta(split: str, tasks: int, model_mode: str = "offline", model_detail: str = "scripted model",
         caveats: list[str] | None = None, margin_pp: float = 5.0) -> dict[str, Any]:
    return {
        "split": split,
        "tasks": tasks,
        "model_mode": model_mode,
        "model_detail": model_detail,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "caveats": list(caveats or []),
        "margin_pp": margin_pp,
    }


def iter_events(path: str) -> Iterator[dict[str, Any]]:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)