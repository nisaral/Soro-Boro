"""Detector Validation & Cluster-Bootstrap Statistical Engine.

Validates the static tarball detector against live stdio tools/list ground truth:
1. Samples 40+ candidate MCP servers across download tiers.
2. Runs live stdio handshake (initialize -> tools/list) in an isolated sandbox.
3. Compares static tarball prediction vs live wire ground truth.
4. Computes Precision, Recall, Specificity, F1 score, False Positive/Negative rates.
5. Queries npm weekly downloads to compute download-weighted unannotated rates.
6. Computes Cluster Bootstrap 95% Confidence Intervals across servers.
7. Saves results to reports/detector_validation_report.json.
"""

from __future__ import annotations

import io
import json
import math
import os
import random
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
REPORT_FILE = ROOT / "reports" / "detector_validation_report.json"
PHASE_A_SURVEY_FILE = ROOT / "reports" / "mcp_phase_a_static_survey.json"

# Candidate servers for live ground-truth validation (no mandatory paid API keys for tools/list)
VALIDATION_CANDIDATES = [
    # Reference / Official
    {"pkg": "@modelcontextprotocol/server-filesystem", "cmd": "npx -y @modelcontextprotocol/server-filesystem {SANDBOX}"},
    {"pkg": "@modelcontextprotocol/server-memory", "cmd": "npx -y @modelcontextprotocol/server-memory"},
    {"pkg": "@modelcontextprotocol/server-everything", "cmd": "npx -y @modelcontextprotocol/server-everything"},
    {"pkg": "@modelcontextprotocol/server-sequential-thinking", "cmd": "npx -y @modelcontextprotocol/server-sequential-thinking"},
    {"pkg": "@modelcontextprotocol/server-sqlite", "cmd": "npx -y @modelcontextprotocol/server-sqlite {SANDBOX}/test.db"},
    # Standalone utilities & community servers
    {"pkg": "@playwright/mcp", "cmd": "npx -y @playwright/mcp"},
    {"pkg": "mcp-server-docker", "cmd": "npx -y mcp-server-docker"},
    {"pkg": "@cyanheads/git-mcp-server", "cmd": "npx -y @cyanheads/git-mcp-server"},
    {"pkg": "@aborruso/ckan-mcp-server", "cmd": "npx -y @aborruso/ckan-mcp-server"},
    {"pkg": "@adpharm/mcp-server-filesystem-ro", "cmd": "npx -y @adpharm/mcp-server-filesystem-ro {SANDBOX}"},
    {"pkg": "@agentage/server-memory", "cmd": "npx -y @agentage/server-memory"},
    {"pkg": "@ericthered926/duckduckgo-mcp-server", "cmd": "npx -y @ericthered926/duckduckgo-mcp-server"},
    {"pkg": "@knip/mcp", "cmd": "npx -y @knip/mcp"},
    {"pkg": "@react-aria/mcp", "cmd": "npx -y @react-aria/mcp"},
    {"pkg": "@eslint/mcp", "cmd": "npx -y @eslint/mcp"},
    {"pkg": "@drawio/mcp", "cmd": "npx -y @drawio/mcp"},
    {"pkg": "chrome-devtools-mcp", "cmd": "npx -y chrome-devtools-mcp"},
    {"pkg": "@hasna/todos", "cmd": "npx -y @hasna/todos"},
    {"pkg": "@mcp-monorepo/weather", "cmd": "npx -y @mcp-monorepo/weather"},
    {"pkg": "@mdavieds/mcp-tmp-files", "cmd": "npx -y @mdavieds/mcp-tmp-files {SANDBOX}"},
    {"pkg": "@mseep/mcp-typescript-server-starter", "cmd": "npx -y @mseep/mcp-typescript-server-starter"},
    {"pkg": "@cardor/email-summarizer", "cmd": "npx -y @cardor/email-summarizer"},
    {"pkg": "@driflyte/mcp-server", "cmd": "npx -y @driflyte/mcp-server"},
    {"pkg": "@ehrocks/fe-mcp-server", "cmd": "npx -y @ehrocks/fe-mcp-server"},
    {"pkg": "@elgato/mcp-server", "cmd": "npx -y @elgato/mcp-server"},
    {"pkg": "@enfyra/mcp-server", "cmd": "npx -y @enfyra/mcp-server"},
    {"pkg": "@esaio/esa-mcp-server", "cmd": "npx -y @esaio/esa-mcp-server"},
    {"pkg": "@ezmodo/mcp-server", "cmd": "npx -y @ezmodo/mcp-server"},
    {"pkg": "@ffschrattenecker/tm1-mcp-server", "cmd": "npx -y @ffschrattenecker/tm1-mcp-server"},
    {"pkg": "@postman/postman-mcp-server", "cmd": "npx -y @postman/postman-mcp-server"},
    {"pkg": "@qase/mcp-server", "cmd": "npx -y @qase/mcp-server"},
    {"pkg": "@runpod/mcp-server", "cmd": "npx -y @runpod/mcp-server"},
    {"pkg": "@solvapay/mcp", "cmd": "npx -y @solvapay/mcp"},
    {"pkg": "@stellarwp/learndash-mcp-server", "cmd": "npx -y @stellarwp/learndash-mcp-server"},
    {"pkg": "@structured-world/gitlab-mcp", "cmd": "npx -y @structured-world/gitlab-mcp"},
    {"pkg": "@ivotoby/openapi-mcp-server", "cmd": "npx -y @ivotoby/openapi-mcp-server"},
    {"pkg": "@jsonresume/mcp", "cmd": "npx -y @jsonresume/mcp"},
    {"pkg": "@bitwarden/mcp-server", "cmd": "npx -y @bitwarden/mcp-server"},
    {"pkg": "@cap-js/mcp-server", "cmd": "npx -y @cap-js/mcp-server"},
    {"pkg": "@doist/todoist-mcp", "cmd": "npx -y @doist/todoist-mcp"},
    {"pkg": "@dokploy/mcp", "cmd": "npx -y @dokploy/mcp"},
    {"pkg": "@storybook/mcp", "cmd": "npx -y @storybook/mcp"},
    {"pkg": "@kintone/mcp-server", "cmd": "npx -y @kintone/mcp-server"},
    {"pkg": "@sentry/mcp-server", "cmd": "npx -y @sentry/mcp-server"},
    {"pkg": "@azure/mcp", "cmd": "npx -y @azure/mcp"},
]


def get_weekly_downloads(pkg_name: str) -> int:
    """Fetches real weekly download count from npm API."""
    try:
        url = f"https://api.npmjs.org/downloads/point/last-week/{pkg_name}"
        req = urllib.request.Request(url, headers={"User-Agent": "soro-detector-validator"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read())
            return int(data.get("downloads", 0))
    except Exception:
        return 0


def run_live_tools_list(cmd: str, timeout_sec: float = 8.0) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Runs server via stdio and extracts tools/list with strict non-blocking timeout."""
    with tempfile.TemporaryDirectory(prefix="soro_val_", ignore_cleanup_errors=True) as td:
        full_cmd = cmd.replace("{SANDBOX}", td)
        # Safe environment
        safe_keys = [
            "PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "HOME",
            "PATHEXT", "COMSPEC", "APPDATA", "LOCALAPPDATA", "NODE_PATH"
        ]
        env = {k: os.environ[k] for k in safe_keys if k in os.environ}
        env["SORO_SANDBOX"] = "1"
        env["CI"] = "true"
        env["NODE_ENV"] = "test"

        proc = None
        try:
            proc = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=td,
                shell=True,
            )

            import queue
            import threading

            q = queue.Queue()

            def reader():
                try:
                    for line in iter(proc.stdout.readline, b""):
                        q.put(line)
                except Exception:
                    pass

            t_reader = threading.Thread(target=reader, daemon=True)
            t_reader.start()

            req_id = 0

            def call_rpc(method: str, params: Optional[dict] = None, is_notif: bool = False):
                nonlocal req_id
                req = {"jsonrpc": "2.0", "method": method}
                if not is_notif:
                    req_id += 1
                    req["id"] = req_id
                if params is not None:
                    req["params"] = params
                payload = (json.dumps(req) + "\n").encode("utf-8")
                proc.stdin.write(payload)
                proc.stdin.flush()
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
                            return json.loads(line_str)
                        except Exception:
                            continue
                return None

            # 1. Initialize
            init_res = call_rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "soro-validator", "version": "1.0.0"}
            })
            if not init_res:
                return False, None, "Initialize timeout or no response"

            # 2. Initialized
            call_rpc("notifications/initialized", is_notif=True)

            # 3. tools/list
            tools_res = call_rpc("tools/list", {})
            if not tools_res:
                return False, None, "tools/list timeout or no response"

            return True, tools_res, "OK"

        except Exception as e:
            return False, None, f"Execution exception: {e}"
        finally:
            if proc:
                try:
                    if sys.platform == "win32":
                        subprocess.run(f"taskkill /F /T /PID {proc.pid}", shell=True, capture_output=True)
                    else:
                        proc.kill()
                except Exception:
                    pass




def inspect_package_static(pkg_name: str) -> Dict[str, Any] | None:
    """The Phase A static tarball detector under test."""
    try:
        url = f"https://registry.npmjs.org/{pkg_name}"
        req = urllib.request.Request(url, headers={"User-Agent": "soro-val"})
        with urllib.request.urlopen(req, timeout=8) as res:
            meta = json.loads(res.read())

        latest = meta.get("dist-tags", {}).get("latest")
        if not latest or latest not in meta.get("versions", {}):
            return None

        ver_info = meta["versions"][latest]
        tarball_url = ver_info.get("dist", {}).get("tarball")
        if not tarball_url:
            return None

        req_tar = urllib.request.Request(tarball_url, headers={"User-Agent": "soro-val"})
        with urllib.request.urlopen(req_tar, timeout=12) as res_tar:
            tar_bytes = res_tar.read()

        tar = tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz")
        all_code = []
        for member in tar.getmembers():
            if member.name.endswith((".js", ".ts", ".mjs", ".cjs", ".json")) and member.size < 2_000_000:
                f = tar.extractfile(member)
                if f:
                    try:
                        all_code.append(f.read().decode("utf-8", errors="ignore"))
                    except Exception:
                        pass

        combined = "\n".join(all_code)
        has_ro = "readOnlyHint" in combined
        has_idem = "idempotentHint" in combined
        has_destr = "destructiveHint" in combined
        has_ow = "openWorldHint" in combined
        has_annotations_obj = "annotations:" in combined or '"annotations":' in combined

        has_any_hint = has_ro or has_idem or has_destr or has_ow or has_annotations_obj

        tool_matches = set(re.findall(r'name:\s*["\']([a-zA-Z0-9_\-]+)["\']', combined))
        tool_matches.update(re.findall(r'tool\(\s*["\']([a-zA-Z0-9_\-]+)["\']', combined))
        noise = {"type", "string", "number", "boolean", "object", "array", "required", "description", "properties", "name", "id", "default", "title"}
        valid_tools = [t for t in tool_matches if t.lower() not in noise and len(t) > 2]

        return {
            "has_any_hint": has_any_hint,
            "estimated_tool_count": max(1, len(valid_tools)),
            "hints": {
                "readOnlyHint": has_ro,
                "idempotentHint": has_idem,
                "destructiveHint": has_destr,
                "openWorldHint": has_ow,
            }
        }
    except Exception:
        return None


def run_cluster_bootstrap(
    servers: List[Dict[str, Any]],
    n_boot: int = 2000,
    alpha: float = 0.05
) -> Dict[str, Any]:
    """Computes cluster bootstrap confidence intervals across server clusters."""
    n_servers = len(servers)
    if n_servers == 0:
        return {}

    boot_unann_rates = []
    boot_dw_unann_rates = []

    for _ in range(n_boot):
        sample = [random.choice(servers) for _ in range(n_servers)]
        # Unweighted server rate
        unann_count = sum(1 for s in sample if not s["has_any_hint"])
        boot_unann_rates.append(unann_count / n_servers)

        # Download-weighted rate
        total_downloads = sum(s.get("weekly_downloads", 1) for s in sample)
        if total_downloads > 0:
            unann_downloads = sum(s.get("weekly_downloads", 1) for s in sample if not s["has_any_hint"])
            boot_dw_unann_rates.append(unann_downloads / total_downloads)
        else:
            boot_dw_unann_rates.append(unann_count / n_servers)

    boot_unann_rates.sort()
    boot_dw_unann_rates.sort()

    low_idx = int((alpha / 2) * n_boot)
    high_idx = int((1 - alpha / 2) * n_boot)

    return {
        "n_bootstraps": n_boot,
        "server_unannotated_ci": [round(boot_unann_rates[low_idx], 4), round(boot_unann_rates[high_idx], 4)],
        "download_weighted_ci": [round(boot_dw_unann_rates[low_idx], 4), round(boot_dw_unann_rates[high_idx], 4)],
    }


def main():
    print("=" * 72)
    print("      SORO DETECTOR VALIDATION: LIVE TOOLS/LIST GROUND TRUTH")
    print("=" * 72)
    print(f"Sampling {len(VALIDATION_CANDIDATES)} candidates for live stdio execution...\n")

    validation_results = []
    tp = 0
    fp = 0
    tn = 0
    fn = 0

    for i, item in enumerate(VALIDATION_CANDIDATES):
        pkg = item["pkg"]
        cmd = item["cmd"]
        sys.stdout.write(f"[{i+1:02d}/{len(VALIDATION_CANDIDATES)}] {pkg:<42} ... ")
        sys.stdout.flush()

        # 1. Run live tools/list
        ok, wire_data, msg = run_live_tools_list(cmd, timeout_sec=12.0)
        if not ok or not wire_data:
            print(f"LAUNCH SKIPPED ({msg})")
            continue

        tools = wire_data.get("result", {}).get("tools", [])
        live_tools_count = len(tools)
        live_annotated_count = 0
        for t in tools:
            ann = t.get("annotations")
            if ann and isinstance(ann, dict) and any(v is not None for v in ann.values()):
                live_annotated_count += 1

        live_has_hints = live_annotated_count > 0

        # 2. Run static detector on package
        static_res = inspect_package_static(pkg)
        if not static_res:
            print("STATIC FETCH FAILED")
            continue

        static_has_hints = static_res["has_any_hint"]

        # 3. Classify: Positive = Annotated, Negative = Unannotated
        if static_has_hints and live_has_hints:
            tp += 1
            classification = "TP (Both Annotated)"
        elif static_has_hints and not live_has_hints:
            fp += 1
            classification = "FP (Static Annotated, Live Unannotated)"
        elif not static_has_hints and not live_has_hints:
            tn += 1
            classification = "TN (Both Unannotated)"
        else:  # not static_has_hints and live_has_hints
            fn += 1
            classification = "FN (Static Unannotated, Live Annotated)"

        downloads = get_weekly_downloads(pkg)

        res_entry = {
            "package": pkg,
            "live_status": "SUCCESS",
            "live_tools_count": live_tools_count,
            "live_annotated_tools": live_annotated_count,
            "live_has_hints": live_has_hints,
            "static_has_hints": static_has_hints,
            "classification": classification,
            "weekly_downloads": downloads,
        }
        validation_results.append(res_entry)
        print(f"{classification} (tools={live_tools_count}, ann={live_annotated_count})")

    total_evaluated = tp + fp + tn + fn
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    accuracy = (tp + tn) / max(1, total_evaluated)
    f1 = 2 * precision * recall / max(1e-6, precision + recall)

    print("\n" + "=" * 72)
    print("                    DETECTOR VALIDATION METRICS")
    print("=" * 72)
    print(f"Total Evaluated Servers (Live Ground Truth): {total_evaluated}")
    print(f"True Positives  (TP - Both Annotated):        {tp}")
    print(f"False Positives (FP - Static Overclaim):      {fp}")
    print(f"True Negatives  (TN - Both Unannotated):      {tn}")
    print(f"False Negatives (FN - Static Underclaim):     {fn}")
    print("-" * 72)
    print(f"Precision:   {precision * 100:.2f}%  (TP / [TP + FP])")
    print(f"Recall:      {recall * 100:.2f}%  (TP / [TP + FN])")
    print(f"Specificity: {specificity * 100:.2f}%  (TN / [TN + FP])")
    print(f"Accuracy:    {accuracy * 100:.2f}%")
    print(f"F1 Score:    {f1:.4f}")
    print("=" * 72)

    # Now load Phase A survey and compute download-weighted rate and cluster bootstrap
    augmented_phase_a = []
    if PHASE_A_SURVEY_FILE.exists():
        phase_a_data = json.loads(PHASE_A_SURVEY_FILE.read_text(encoding="utf-8"))
        servers_list = phase_a_data.get("server_details", [])
        print(f"\nEnriching {len(servers_list)} Phase A servers with weekly downloads from npm API...")
        for s in servers_list:
            d_count = get_weekly_downloads(s["package"])
            s["weekly_downloads"] = d_count
            augmented_phase_a.append(s)
            time.sleep(0.02)

        # Download-weighted unannotated rate
        total_all_downloads = sum(s["weekly_downloads"] for s in augmented_phase_a)
        unann_downloads = sum(s["weekly_downloads"] for s in augmented_phase_a if not s["has_any_hint"])
        dw_unann_rate = unann_downloads / max(1, total_all_downloads)

        bootstrap_res = run_cluster_bootstrap(augmented_phase_a, n_boot=2000, alpha=0.05)
        print(f"Unweighted Unannotated Server Rate:     {sum(1 for s in augmented_phase_a if not s['has_any_hint']) / len(augmented_phase_a) * 100:.2f}%")
        print(f"Cluster Bootstrap 95% CI (Unweighted):  {bootstrap_res['server_unannotated_ci']}")
        print(f"Download-Weighted Unannotated Rate:     {dw_unann_rate * 100:.2f}%")
        print(f"Cluster Bootstrap 95% CI (Weighted):    {bootstrap_res['download_weighted_ci']}")
    else:
        bootstrap_res = {}
        dw_unann_rate = 0.0

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "validation_sample_size": total_evaluated,
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "specificity": round(specificity, 4),
            "accuracy": round(accuracy, 4),
            "f1_score": round(f1, 4),
        },
        "live_evaluations": validation_results,
        "cluster_bootstrap": bootstrap_res,
        "download_weighted_metrics": {
            "download_weighted_unannotated_rate": round(dw_unann_rate, 4),
            "download_weighted_unannotated_percent": round(dw_unann_rate * 100, 2),
        }
    }

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote full detector validation report to {REPORT_FILE}")


if __name__ == "__main__":
    main()
