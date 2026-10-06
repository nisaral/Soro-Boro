"""`veyra-py`: the Python-side command surface.

    veyra-py serve                       # harness + decision plane
    veyra-py compare --spawn --split dev # headline benchmark, one command
    veyra-py tasks                       # list the bundled suite
    veyra-py train --runs-dir runs       # fit the bandit policy from traces
    veyra-py doctor                      # environment check
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from veyra.bench import report, runner
from veyra.bench.report import write as write_report
from veyra.bench.tasks import all_tasks, by_split

DEFAULT_SIDECAR = "127.0.0.1:7777"
DEFAULT_KERNEL = "127.0.0.1:7788"


def _wait_port(addr: str, timeout: float = 20.0) -> bool:
    host, _, port = addr.rpartition(":")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host or "127.0.0.1", int(port)), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def _find_kernel(explicit: str) -> str:
    if explicit:
        return explicit
    for candidate in ("dist/veyra.exe", "dist/veyra", "veyra.exe", "veyra", "go/veyra.exe"):
        if Path(candidate).exists():
            return candidate
    return ""


def cmd_serve(args: argparse.Namespace) -> int:
    from veyra.server import serve

    serve(args.addr, harness_opts={"workspace": args.workspace} if args.workspace else {},
          default_backend=args.decision,
          decision_opts={"endpoint": args.von_endpoint or None, "kev_endpoint": args.kev_endpoint or None,
                         "state_path": args.bandit_state or None})
    return 0


def cmd_mcpagentbench(args: argparse.Namespace) -> int:
    import asyncio

    from veyra.bench import mcpagent

    mcpagent.require_llm(base_url=args.base_url or None, api_key=args.api_key or None)
    name = args.output_name or f"{args.agent}_{args.model.replace('/', '_')}_{args.tasks_type}"
    if args.limit:
        name = f"{name}_limit{args.limit}"
        print(f"mcpagentbench: limit={args.limit} is a plumbing smoke, not a public score", flush=True)
    kwargs = dict(
        model=args.model, tasks_type=args.tasks_type,
        concurrency=args.concurrency, num_servers=args.num_servers,
        output_name=name, base_url=args.base_url or None,
        api_key=args.api_key or None, limit=args.limit,
    )
    if args.agent == "react":
        score = asyncio.run(mcpagent.run_official(**kwargs))
    else:
        score = asyncio.run(mcpagent.run_veyra(policy=args.agent, **kwargs))
    print(f"TFS (model_score from official evaluator): {score}")
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    from veyra.handoff import compile_handoff

    payload = compile_handoff(Path(args.events), to_harness=args.to or None, shadow=not args.act)
    text = json.dumps(payload, indent=2)
    Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_headroom(args: argparse.Namespace) -> int:
    from pathlib import Path

    from veyra.analysis.headroom import write_report

    trials = Path(args.trials)
    out = Path(args.out)
    summary = write_report(trials, out)
    print(out.read_text(encoding="utf-8"))
    print("gate1_stop", summary["gate1_stop"])
    return 0


def cmd_gate1_leaderboard(args: argparse.Namespace) -> int:
    from collections import defaultdict
    from pathlib import Path
    from veyra.analysis.gate1_leaderboard import (
        calculate_matched_headroom,
        format_report_markdown,
        scan_leaderboard_directory,
    )

    data_dir = Path(args.dir)
    if args.download:
        from huggingface_hub import snapshot_download

        print(f"Downloading {args.dataset} (metadata + result.json only) to {data_dir}...")
        snapshot_download(
            repo_id=args.dataset,
            repo_type="dataset",
            allow_patterns=[
                "**/result.json",
                "**/metadata.yaml",
                "**/metadata.yml",
                "result.json",
                "metadata.yaml",
                "metadata.yml",
            ],
            local_dir=str(data_dir),
        )

    trials = scan_leaderboard_directory(data_dir)
    print(f"Loaded {len(trials)} valid trial records across qualifying submissions.")
    if not trials:
        print("No valid trials found matching submission criteria.")
        return 1

    by_model: dict[str, dict[str, dict[str, list[bool]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    cost_by_model: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for t in trials:
        by_model[t.model][t.agent][t.task].append(t.passed)
        cost_by_model[t.model][t.agent][t.task].append(t.cost_usd)

    analyses = []
    for model, agents_dict in sorted(by_model.items()):
        if args.model and args.model.lower() not in model.lower():
            continue
        analysis = calculate_matched_headroom(agents_dict, cost_by_model[model], model=model)
        if analysis:
            analyses.append(analysis)

    if not analyses:
        print("No model groups found with >= 2 qualifying agent harnesses.")
        return 1

    report = format_report_markdown(analyses)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(report)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    from veyra.boundary.audit import audit_from_file

    traces_path = Path(args.traces)
    if not traces_path.exists():
        print(f"audit: traces file not found: {traces_path}", file=sys.stderr)
        return 1

    summary = audit_from_file(traces_path)
    if args.json:
        print(json.dumps(summary.to_dict(), indent=2))
    else:
        print(summary.to_text())
    return 0


def cmd_toolmisuse(args: argparse.Namespace) -> int:
    from veyra.bench.toolmisuse.runner import run_toolmisuse_benchmark

    results = run_toolmisuse_benchmark()
    if args.json:
        print(json.dumps({k: v.to_dict() for k, v in results.items()}, indent=2))
    else:
        print("=" * 80)
        print("         TOOLMISUSEBENCH EVALUATION SUMMARY (v0.1 Controlled Baseline)")
        print("=" * 80)
        header = f"{'System Arm':<22} | {'Success':<8} | {'Recoveries':<11} | {'Unsafe Retries':<15} | {'Replans':<8}"
        print(header)
        print("-" * 80)
        for arm_name, r in results.items():
            print(f"{arm_name:<22} | {r.task_success_rate:>6.1f}% | {r.boundary_recovery_rate:>10.1f}% | {r.unsafe_retries:>15d} | {r.agent_replans:>8d}")
        print("=" * 80)
    return 0


def cmd_targets(_args: argparse.Namespace) -> int:
    from veyra.bench.targets import checklist

    print(checklist())
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    tasks = all_tasks() if args.split == "all" else by_split(args.split)
    for t in tasks:
        print(f"{t.id:20s} {t.category:13s} {t.split:5s} {t.instruction[:70]}")
    print(f"\n{len(tasks)} tasks")
    return 0


def _load_results(path: str) -> list[dict[str, Any]]:
    src = Path(path)
    if src.is_dir():
        src = src / "results.json"
    if not src.exists():
        return []
    data = json.loads(src.read_text(encoding="utf-8"))
    return list(data.get("results") or [])


def _caveats(results: list[dict[str, Any]], args: argparse.Namespace | None = None) -> list[str]:
    mode = getattr(args, "model_mode", "offline")
    first = (
        "model_mode=offline: the scripted model proves the kernel/harness/decision plumbing and the wire "
        "protocol, not model behaviour. Headline numbers require a live model (--model-mode ollama)."
        if mode == "offline"
        else f"model_mode={mode}: a single deterministic run per (task, arm) at temperature 0. No seed "
        "sweep, so variance across samples is unmeasured."
    )
    out = [
        first,
        "Harness cost is charged as a per-step overhead on top of measured model usage, so harness "
        "selection is an economic decision rather than a free one.",
    ]
    backends = {b for r in results for b in (r.get("backends") or [])}
    engines = {e for r in results for e in (r.get("harness_engines") or [])}
    if "von-surrogate" in backends:
        out.append("veyra:von ran as `von-surrogate` (no --von-endpoint): it is NOT a real Jev-style model "
                   "and must not be reported as one.")
    if "kev-unconfigured" in backends:
        out.append("veyra:kev had no --kev-endpoint: the kernel fell back and this arm is not a Kev result.")
    if "bandit-untrained" in backends:
        out.append("veyra:bandit ran untrained (no --bandit-state): it defers to the heuristic baseline "
                   "and is labelled `bandit-untrained` in the event log.")
    if "builtin-graph" in engines:
        out.append("the `langgraph` arm used the in-repo MiniGraph fallback (LangGraph unavailable in this "
                   "environment), reported as engine:builtin-graph.")
    return out


def cmd_compare(args: argparse.Namespace) -> int:
    tasks = all_tasks() if args.split == "all" else by_split(args.split)
    out = Path(args.out)
    dev_results: list[dict[str, Any]] = []
    include_kev = bool(args.kev_endpoint) or (bool(args.arms) and "veyra:kev" in args.arms)
    if args.arms:
        wanted = {a.strip() for a in args.arms.split(",")}
        arms = [a for a in runner.default_arms(include_kev=True) if a.name in wanted]
    elif args.select_from:
        dev_results = _load_results(args.select_from)
        best, _ = report.pick_best_fixed(dev_results)
        if not best:
            print(f"compare: no fixed:* arms found in {args.select_from}", file=sys.stderr)
            return 2
        arms = runner.test_arms(best, include_kev=include_kev)
        print(f"compare: dev selected fixed:{best}; held-out arms = {[a.name for a in arms]}")
    else:
        arms = runner.default_arms(include_kev=include_kev)

    sidecar = None
    kernel = None
    try:
        if args.spawn:
            kernel_bin = _find_kernel(args.kernel_bin)
            if not kernel_bin:
                print("compare: --spawn needs the Go kernel; build it with `make build` or pass --kernel-bin",
                      file=sys.stderr)
                return 2
            from veyra.server import build_server

            if _wait_port(args.sidecar, timeout=0.4):
                print(f"compare: something is already listening on {args.sidecar}; refusing to start a "
                      "second sidecar", file=sys.stderr)
                return 2
            decision_opts = {"endpoint": args.von_endpoint or None,
                             "kev_endpoint": args.kev_endpoint or None,
                             "state_path": args.bandit_state or None}
            server, _ = build_server(args.sidecar, {}, "heuristic", decision_opts)
            server.start()
            sidecar = server
            if not _wait_port(args.sidecar):
                print(f"compare: sidecar did not come up on {args.sidecar}", file=sys.stderr)
                return 2
            if _wait_port(args.addr, timeout=0.4):
                print(f"compare: something is already listening on {args.addr}; refusing to --spawn over "
                      "it (a stale kernel would silently serve old code). Stop it, or drop --spawn to "
                      "attach to it deliberately.", file=sys.stderr)
                return 2
            kernel = subprocess.Popen(
                [kernel_bin, "serve", "--addr", args.addr, "--python", args.sidecar,
                 "--runs-dir", str(out / "runs")],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            deadline = time.time() + 30
            while time.time() < deadline:
                if kernel.poll() is not None:
                    output = kernel.stdout.read() if kernel.stdout else ""
                    print("compare: kernel exited immediately (stale binary or port already held):\n" + output,
                          file=sys.stderr)
                    return 2
                if _wait_port(args.addr, timeout=0.5):
                    break
            else:
                print("compare: kernel did not come up", file=sys.stderr)
                return 2

        print(f"comparing {len(tasks)} tasks x {len(arms)} arms against {args.addr}")

        def progress(record: dict) -> None:
            if not args.quiet:
                flag = "ok " if record["status"] == "SUCCEEDED" else "   "
                print(f"  {flag}{record['task']:20s} {record['arm']:16s} {record['status']:16s} "
                      f"${record['usd']:.4f} {record['actions']:>3d} actions sw={record['switches']}", flush=True)

        started = time.time()
        model = {"mode": args.model_mode, "cheap": args.model_cheap, "strong": args.model_strong,
                 "base_url": args.base_url}
        results = runner.run_all(tasks, arms, args.addr, out / "workspaces", timeout_s=args.timeout,
                                 on_result=progress, model=model)
        info = runner.meta(args.split, len(tasks), args.model_mode, runner.model_detail(model))
        info["elapsed_s"] = round(time.time() - started, 1)
        info["caveats"] = _caveats(results, args)
        paths = write_report(results, info, out, dev_results=dev_results or None)
        print()
        print(write_report.__module__ and Path(paths["markdown"]).read_text(encoding="utf-8"))
        print(f"wrote {paths['markdown']}")
        if paths["png"]:
            print(f"wrote {paths['png']}")
        return 0
    finally:
        if kernel is not None:
            kernel.terminate()
            try:
                kernel.wait(timeout=5)
            except subprocess.TimeoutExpired:
                kernel.kill()
        if sidecar is not None:
            sidecar.stop(grace=1.0)


def cmd_train(args: argparse.Namespace) -> int:
    from veyra.decision.bandit import train_from_events

    runs = sorted(Path(args.runs_dir).glob("*/events.jsonl"))
    if not runs:
        print(f"train: no run logs under {args.runs_dir}", file=sys.stderr)
        return 1
    model = train_from_events([str(p) for p in runs], alpha=args.alpha)
    model.state_path = Path(args.out)
    model.save()
    print(f"trained {len(model.theta)} arms from {len(runs)} runs -> {args.out}")
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    from veyra.view import Viewer

    Viewer(Path(args.runs)).serve(args.host, args.port)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    from veyra.boundary.audit import audit_from_file

    summary = audit_from_file(args.traces)
    if args.json:
        import json
        print(json.dumps(summary.__dict__, indent=2))
    else:
        print(summary.format_text())
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from veyra.harness.registry import HarnessRegistry

    print(f"python:  {sys.version.split()[0]} at {sys.executable}")
    registry = HarnessRegistry()
    for row in registry.triage():
        mark = "OK " if row["available"] else "NO "
        print(f"{mark}{row['id']:10s} {row['detail']}")
    from veyra.decision import kev, von

    ok, detail = von.available(args.von_endpoint or None)
    print(f"{'OK ' if ok else 'NO '}von        {detail}")
    ok, detail = kev.available(args.kev_endpoint or None)
    print(f"{'OK ' if ok else 'NO '}kev        {detail}")
    ready = _wait_port(args.addr, timeout=1.5)
    print(f"{'OK ' if ready else 'NO '}kernel     {args.addr} {'reachable' if ready else 'not running'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="veyra-py", description="Veyra Python sidecar and benchmark")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="run the harness + decision sidecar")
    p_serve.add_argument("--addr", default=DEFAULT_SIDECAR)
    p_serve.add_argument("--decision", default="heuristic")
    p_serve.add_argument("--workspace", default="")
    p_serve.add_argument("--von-endpoint", default="")
    p_serve.add_argument("--kev-endpoint", default="")
    p_serve.add_argument("--bandit-state", default="")
    p_serve.set_defaults(func=cmd_serve)

    p_mcp = sub.add_parser("mcpagentbench", help="official MCPAgentBench (ROUTER_API_KEY or --base-url)")
    p_mcp.add_argument("--agent", choices=["react", "heuristic", "kev"], default="react")
    p_mcp.add_argument("--model", required=True, help="model id (cloud config or local LM Studio id)")
    p_mcp.add_argument("--tasks_type", default="general_test", choices=["day", "pro", "general_test"])
    p_mcp.add_argument("--concurrency", type=int, default=None)
    p_mcp.add_argument("--num_servers", type=int, default=None)
    p_mcp.add_argument("--output_name", default=None)
    p_mcp.add_argument("--base-url", default="", help="OpenAI-compatible base URL, e.g. LM Studio http://127.0.0.1:1234/v1")
    p_mcp.add_argument("--api-key", default="", help="API key for --base-url (use local for LM Studio)")
    p_mcp.add_argument("--limit", type=int, default=None, help="truncate task file for plumbing smoke only")
    p_mcp.set_defaults(func=cmd_mcpagentbench)

    p_ho = sub.add_parser("handoff", help="compile HandoffV1 from events.jsonl (shadow by default)")
    p_ho.add_argument("--events", required=True)
    p_ho.add_argument("--out", default="handoff.json")
    p_ho.add_argument("--to", default="", help="destination harness id")
    p_ho.add_argument("--act", action="store_true", help="mark shadow=false (still does not execute a switch)")
    p_ho.set_defaults(func=cmd_handoff)

    p_hr = sub.add_parser("headroom", help="Gate 1: net oracle headroom vs same-harness null")
    p_hr.add_argument("--trials", required=True, help="CSV with columns task,harness,seed,pass,cost")
    p_hr.add_argument("--out", default="out/headroom.md")
    p_hr.set_defaults(func=cmd_headroom)

    p_g1 = sub.add_parser("gate1-leaderboard", help="Gate 1: public Terminal-Bench 2.0 leaderboard evaluation")
    p_g1.add_argument("--dir", default="data/tb2_leaderboard", help="local directory for leaderboard files")
    p_g1.add_argument("--download", action="store_true", help="download result.json and metadata.yaml from huggingface")
    p_g1.add_argument("--dataset", default="harborframework/terminal-bench-2-leaderboard")
    p_g1.add_argument("--model", default="", help="filter to specific model group (e.g. gpt-5.3-codex, gemini-3.1-pro)")
    p_g1.add_argument("--out", default="out/gate1_leaderboard.md")
    p_g1.set_defaults(func=cmd_gate1_leaderboard)

    p_audit = sub.add_parser("audit", help="audit tool execution boundary traces")
    p_audit.add_argument("--traces", default="runs/traces.jsonl", help="path to JSONL trace log")
    p_audit.add_argument("--json", action="store_true", help="output audit summary as JSON")
    p_audit.set_defaults(func=cmd_audit)

    p_tm = sub.add_parser("toolmisuse", help="ToolMisuseBench comparative evaluation (v0.1 Controlled Baseline)")
    p_tm.add_argument("--json", action="store_true", help="output evaluation metrics as JSON")
    p_tm.set_defaults(func=cmd_toolmisuse)

    p_targets = sub.add_parser("targets", help="list the public benchmarks this project is aiming at")
    p_targets.set_defaults(func=cmd_targets)

    p_tasks = sub.add_parser("tasks", help="list the bundled benchmark tasks")
    p_tasks.add_argument("--split", default="all", choices=["dev", "test", "all"])
    p_tasks.set_defaults(func=cmd_tasks)

    p_cmp = sub.add_parser("compare", help="run the harness-switching comparison")
    p_cmp.add_argument("--addr", default=DEFAULT_KERNEL)
    p_cmp.add_argument("--sidecar", default=DEFAULT_SIDECAR)
    p_cmp.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    p_cmp.add_argument("--arms", default="")
    p_cmp.add_argument("--out", default="out/dev")
    p_cmp.add_argument("--timeout", type=float, default=180.0)
    p_cmp.add_argument("--spawn", action="store_true", help="start the sidecar and the Go kernel")
    p_cmp.add_argument("--kernel-bin", default="")
    p_cmp.add_argument("--quiet", action="store_true")
    p_cmp.add_argument("--select-from", default="",
                       help="dev results dir/file; restricts test arms to the dev-selected baseline")
    p_cmp.add_argument("--bandit-state", default="", help="trained LinUCB policy json")
    p_cmp.add_argument("--von-endpoint", default="", help="Jev-style typed decision model HTTP endpoint")
    p_cmp.add_argument("--kev-endpoint", default="",
                       help="local Kev server, e.g. http://127.0.0.1:8009; adds the veyra:kev arm")
    p_cmp.add_argument("--model-mode", default="offline", choices=["offline", "ollama", "openai"],
                       help="offline = scripted, deterministic; ollama/openai = live model")
    p_cmp.add_argument("--model-cheap", default="", help="cheap tier model name for live modes")
    p_cmp.add_argument("--model-strong", default="", help="strong tier model name for live modes")
    p_cmp.add_argument("--base-url", default="", help="endpoint for live modes (default: provider default)")
    p_cmp.set_defaults(func=cmd_compare)

    p_train = sub.add_parser("train", help="fit the contextual bandit from recorded runs")
    p_train.add_argument("--runs-dir", default="out/dev/runs")
    p_train.add_argument("--out", default="policies/bandit.json")
    p_train.add_argument("--alpha", type=float, default=0.6)
    p_train.set_defaults(func=cmd_train)

    p_view = sub.add_parser("dashboard", help="product dashboard for a runs directory")
    p_view.add_argument("--runs", default="out/dev")
    p_view.add_argument("--host", default="127.0.0.1")
    p_view.add_argument("--port", type=int, default=7860)
    p_view.set_defaults(func=cmd_view)

    p_view_alias = sub.add_parser("view", help="alias for dashboard")
    p_view_alias.add_argument("--runs", default="out/dev")
    p_view_alias.add_argument("--host", default="127.0.0.1")
    p_view_alias.add_argument("--port", type=int, default=7860)
    p_view_alias.set_defaults(func=cmd_view)

    p_doc = sub.add_parser("doctor", help="environment check")
    p_doc.add_argument("--addr", default=DEFAULT_KERNEL)
    p_doc.add_argument("--von-endpoint", default="")
    p_doc.add_argument("--kev-endpoint", default="")
    p_doc.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())