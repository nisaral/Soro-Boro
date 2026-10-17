"""Soro MCP Live Census: Ground-Truth stdio tools/list Inspection.

Completely drops static string/regex inspection in favor of live stdio wire execution.
1. Inspects top 50 packages by weekly npm downloads + random sample of 40 long-tail servers.
2. Uses dummy credentials in environment (safe sandbox execution).
3. Separates npm install from run phase to prevent cold-start download timeouts.
4. Tries default invocation and explicit stdio flags (--stdio / stdio) if required.
5. Reads JSON-RPC responses matching request IDs strictly (filtering server notifications/logs).
6. Categorizes every server into mutually exclusive buckets:
   - ANNOTATED: Server started, returned tools, >=1 tool declared hints.
   - UNANNOTATED: Server started, returned tools, 0 tools declared hints.
   - COULD_NOT_START: Server failed to install, timed out, exited with error, or requires runtime setup.
     (NEVER conflated with unannotated!)
7. Computes ecosystem census metrics and saves to reports/mcp_live_census_report.json.
"""

from __future__ import annotations

import json
import os
import queue
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "reports" / "mcp_live_census_report.json"

DUMMY_CREDENTIALS = {
    "CI": "true",
    "SORO_SANDBOX": "1",
    "NODE_ENV": "test",
    "BRAVE_API_KEY": "dummy_brave_key_for_audit",
    "GITHUB_TOKEN": "ghp_dummy_token_for_audit",
    "SLACK_BOT_TOKEN": "xoxb-dummy-slack-token-for-audit",
    "NOTION_API_KEY": "secret_dummy_notion_key_for_audit",
    "SENTRY_AUTH_TOKEN": "sntrys_dummy_sentry_key_for_audit",
    "OPENAI_API_KEY": "sk-dummy-openai-key-for-audit",
    "STRIPE_SECRET_KEY": "sk_test_dummy_stripe_key_for_audit",
    "AWS_ACCESS_KEY_ID": "dummy_aws_key_for_audit",
    "AWS_SECRET_ACCESS_KEY": "dummy_aws_secret_for_audit",
}


def install_package(pkg: str, target_dir: str, timeout_sec: float = 45.0) -> Tuple[bool, str]:
    """Installs package locally in target_dir, separating download from run."""
    try:
        res = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--omit=dev", pkg],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            shell=(sys.platform == "win32"),
        )
        if res.returncode == 0:
            return True, "Installed successfully"
        err = (res.stderr or res.stdout or "").strip()
        first_line = err.splitlines()[0] if err else f"exit code {res.returncode}"
        return False, f"npm install failed: {first_line[:120]}"
    except subprocess.TimeoutExpired:
        return False, f"npm install timed out after {timeout_sec}s"
    except Exception as e:
        return False, f"npm install error: {e}"


def resolve_package_executable(pkg: str, target_dir: str) -> Tuple[Optional[str], Optional[Path]]:
    """Resolves CLI executable script from package.json or node_modules/.bin."""
    pkg_dir = Path(target_dir) / "node_modules" / pkg
    pkg_json_file = pkg_dir / "package.json"
    if not pkg_json_file.exists():
        return None, None

    try:
        data = json.loads(pkg_json_file.read_text(encoding="utf-8"))
        bin_field = data.get("bin")
        if bin_field:
            if isinstance(bin_field, str):
                rel = bin_field
            elif isinstance(bin_field, dict):
                pkg_subname = pkg.split("/")[-1]
                rel = bin_field.get(pkg_subname) or bin_field.get(pkg) or next(iter(bin_field.values()))
            else:
                rel = None
            if rel:
                target = (pkg_dir / rel).resolve()
                if target.exists():
                    return "bin", target

        main_field = data.get("main")
        if main_field:
            target = (pkg_dir / main_field).resolve()
            if target.exists():
                return "main", target
    except Exception:
        pass
    return None, None


def execute_stdio_handshake(cmd_args: List[str], cwd: str, timeout_sec: float = 12.0) -> Tuple[str, int, int, List[Dict[str, Any]], str]:
    """Runs server via stdio, handles notifications/logs, and queries tools/list matching response IDs."""
    safe_keys = [
        "PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "HOME",
        "PATHEXT", "COMSPEC", "APPDATA", "LOCALAPPDATA", "NODE_PATH"
    ]
    env = {k: os.environ[k] for k in safe_keys if k in os.environ}
    env.update(DUMMY_CREDENTIALS)
    env["MEMORY_FILE_PATH"] = os.path.join(cwd, "memory.json")

    proc = None
    try:
        proc = subprocess.Popen(
            cmd_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd,
        )

        q: queue.Queue = queue.Queue()

        def reader():
            try:
                for line in iter(proc.stdout.readline, b""):
                    q.put(line)
            except Exception:
                pass

        t_reader = threading.Thread(target=reader, daemon=True)
        t_reader.start()

        req_id = 0

        def call_rpc(method: str, params: Optional[dict] = None, is_notif: bool = False) -> Optional[dict]:
            nonlocal req_id
            req = {"jsonrpc": "2.0", "method": method}
            if not is_notif:
                req_id += 1
                req["id"] = req_id
            if params is not None:
                req["params"] = params

            payload = (json.dumps(req) + "\n").encode("utf-8")
            try:
                proc.stdin.write(payload)
                proc.stdin.flush()
            except (BrokenPipeError, OSError):
                return None

            if is_notif:
                return None

            start_t = time.time()
            while time.time() - start_t < timeout_sec:
                remaining = max(0.1, timeout_sec - (time.time() - start_t))
                try:
                    line_bytes = q.get(timeout=remaining)
                except queue.Empty:
                    return None
                line_str = line_bytes.decode("utf-8", errors="replace").strip()
                if line_str.startswith("{"):
                    try:
                        parsed = json.loads(line_str)
                        if parsed.get("id") == req_id:
                            return parsed
                    except Exception:
                        continue
            return None

        # 1. Initialize
        init_res = call_rpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "soro-census", "version": "0.3.0"}
        })
        if not init_res:
            return "COULD_NOT_START", 0, 0, [], "Handshake timed out or failed to reply to initialize"

        # 2. Initialized notification
        call_rpc("notifications/initialized", is_notif=True)

        # 3. tools/list
        tools_res = call_rpc("tools/list", {})
        if not tools_res:
            return "COULD_NOT_START", 0, 0, [], "tools/list timed out or returned no response"

        tools = tools_res.get("result", {}).get("tools", [])
        total_tools = len(tools)
        annotated_count = 0
        for t in tools:
            ann = t.get("annotations")
            if ann and isinstance(ann, dict) and any(v is not None for v in ann.values()):
                annotated_count += 1

        category = "ANNOTATED" if annotated_count > 0 else "UNANNOTATED"
        return category, total_tools, annotated_count, tools, "OK"

    except Exception as e:
        return "COULD_NOT_START", 0, 0, [], f"Process execution error: {e}"
    finally:
        if proc:
            try:
                if sys.platform == "win32":
                    subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, capture_output=True)
                else:
                    proc.kill()
            except Exception:
                pass


def audit_live_package(pkg: str, timeout_sec: float = 12.0) -> Tuple[str, int, int, List[Dict[str, Any]], str]:
    """Installs and audits a single package, trying standard invocation variants."""
    with tempfile.TemporaryDirectory(prefix="soro_census_", ignore_cleanup_errors=True) as td:
        # Step 1: Separate npm install
        ok, msg = install_package(pkg, td, timeout_sec=40.0)
        if not ok:
            return "COULD_NOT_START", 0, 0, [], msg

        # Step 2: Locate entrypoint
        kind, script_path = resolve_package_executable(pkg, td)
        if not script_path:
            return "COULD_NOT_START", 0, 0, [], "Package has no runnable bin or main entrypoint"

        base_cmd = ["node", str(script_path)]
        if "filesystem" in pkg:
            base_cmd.append(td)

        # Step 3: Attempt stdio handshake with base command
        cat, tot, ann, tools, status_msg = execute_stdio_handshake(base_cmd, cwd=td, timeout_sec=timeout_sec)
        if cat in ("ANNOTATED", "UNANNOTATED"):
            return cat, tot, ann, tools, status_msg

        # Step 4: If base failed, try passing --stdio or stdio
        for stdio_arg in ["--stdio", "stdio"]:
            retry_cmd = list(base_cmd) + [stdio_arg]
            r_cat, r_tot, r_ann, r_tools, r_msg = execute_stdio_handshake(retry_cmd, cwd=td, timeout_sec=timeout_sec)
            if r_cat in ("ANNOTATED", "UNANNOTATED"):
                return r_cat, r_tot, r_ann, r_tools, f"OK ({stdio_arg})"

        return "COULD_NOT_START", 0, 0, [], status_msg


def get_top_packages_and_downloads(limit: int = 100) -> List[Tuple[str, int]]:
    """Gets packages and real download counts from npm."""
    pkgs = set()
    try:
        url = "https://registry.npmjs.org/-/v1/search?text=mcp-server&size=250"
        req = urllib.request.Request(url, headers={"User-Agent": "soro-census"})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
            for obj in data.get("objects", []):
                pkgs.add(obj["package"]["name"])
    except Exception as e:
        print("Search error:", e)

    # Core reference and community servers
    core = [
        "@modelcontextprotocol/server-filesystem",
        "@modelcontextprotocol/server-memory",
        "@modelcontextprotocol/server-everything",
        "@modelcontextprotocol/server-sequential-thinking",
        "@modelcontextprotocol/server-brave-search",
        "@modelcontextprotocol/server-github",
        "@modelcontextprotocol/server-slack",
        "@modelcontextprotocol/server-fetch",
        "@modelcontextprotocol/server-puppeteer",
        "@playwright/mcp",
        "chrome-devtools-mcp",
        "mcp-server-docker",
        "@cyanheads/git-mcp-server",
    ]
    for c in core:
        pkgs.add(c)

    results = []
    print(f"Fetching weekly downloads for {len(pkgs)} packages...")
    for p in sorted(list(pkgs)):
        try:
            url = f"https://api.npmjs.org/downloads/point/last-week/{p}"
            req = urllib.request.Request(url, headers={"User-Agent": "soro-census"})
            with urllib.request.urlopen(req, timeout=3) as res:
                data = json.loads(res.read())
                cnt = int(data.get("downloads", 0))
                results.append((p, cnt))
        except Exception:
            results.append((p, 0))
        time.sleep(0.01)

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def run_census(top_n: int = 50, sample_tail_n: int = 40):
    start_t = time.time()
    ranked = get_top_packages_and_downloads()
    top_stratum = ranked[:top_n]
    tail_candidates = ranked[top_n:]
    tail_stratum = random.sample(tail_candidates, min(sample_tail_n, len(tail_candidates)))

    full_sample = [("TOP_TIER", p, dl) for p, dl in top_stratum] + [("TAIL_SAMPLE", p, dl) for p, dl in tail_stratum]

    print(f"\nRunning Live Stdio Census on {len(full_sample)} packages ({top_n} top-tier + {len(tail_stratum)} tail sample)...")
    print("=" * 80)

    evaluated = []
    cat_counts = {"ANNOTATED": 0, "UNANNOTATED": 0, "COULD_NOT_START": 0}
    tools_by_cat = {"ANNOTATED": 0, "UNANNOTATED": 0}

    for i, (stratum, pkg, dls) in enumerate(full_sample):
        sys.stdout.write(f"[{i+1:02d}/{len(full_sample)}] {pkg:<42} ({dls:>7} dl/wk) ... ")
        sys.stdout.flush()

        cat, total_tools, ann_tools, tools_list, msg = audit_live_package(pkg, timeout_sec=12.0)
        cat_counts[cat] += 1
        if cat in tools_by_cat:
            tools_by_cat[cat] += total_tools

        print(f"{cat} (tools={total_tools}, ann={ann_tools}) [{msg}]")

        entry = {
            "package": pkg,
            "stratum": stratum,
            "weekly_downloads": dls,
            "category": cat,
            "total_tools": total_tools,
            "annotated_tools": ann_tools,
            "status_message": msg,
            "tools_summary": [{"name": t.get("name"), "annotations": t.get("annotations")} for t in tools_list[:10]],
        }
        evaluated.append(entry)

    started_total = cat_counts["ANNOTATED"] + cat_counts["UNANNOTATED"]
    unann_rate_of_started = cat_counts["UNANNOTATED"] / max(1, started_total)

    report = {
        "census_name": "Soro Live stdio MCP Census (Top 50 + Stratified Tail)",
        "conducted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sample_size": len(full_sample),
        "breakdown": {
            "total_attempted": len(full_sample),
            "annotated_servers": cat_counts["ANNOTATED"],
            "unannotated_servers": cat_counts["UNANNOTATED"],
            "could_not_start": cat_counts["COULD_NOT_START"],
            "total_started": started_total,
            "start_success_rate": round(started_total / len(full_sample), 4),
            "unannotated_share_of_started": round(unann_rate_of_started, 4),
            "unannotated_percent_of_started": round(unann_rate_of_started * 100, 2),
        },
        "tools_breakdown": {
            "tools_in_annotated_servers": tools_by_cat["ANNOTATED"],
            "tools_in_unannotated_servers": tools_by_cat["UNANNOTATED"],
            "total_live_tools_exercised": tools_by_cat["ANNOTATED"] + tools_by_cat["UNANNOTATED"],
        },
        "top_tier_census": [e for e in evaluated if e["stratum"] == "TOP_TIER"],
        "tail_sample": [e for e in evaluated if e["stratum"] == "TAIL_SAMPLE"],
        "elapsed_seconds": round(time.time() - start_t, 2),
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n" + "=" * 80)
    print("                      CENSUS RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total Attempted:                {len(full_sample)}")
    print(f"Successfully Started Servers:   {started_total}")
    print(f"  - Annotated Servers:          {cat_counts['ANNOTATED']} ({cat_counts['ANNOTATED']/max(1, started_total)*100:.1f}%)")
    print(f"  - Unannotated Servers:        {cat_counts['UNANNOTATED']} ({cat_counts['UNANNOTATED']/max(1, started_total)*100:.1f}%)")
    print(f"Could Not Start (Separate Cat): {cat_counts['COULD_NOT_START']} ({cat_counts['COULD_NOT_START']/len(full_sample)*100:.1f}%)")
    print(f"Report saved to: {OUTPUT_FILE}")
    print("=" * 80)
    return report


if __name__ == "__main__":
    run_census(top_n=50, sample_tail_n=40)
