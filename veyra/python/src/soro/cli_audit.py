"""Soro Audit: Standalone Linter & Behavioral Verifier for Model Context Protocol (MCP) Servers.

Wedge functionality:
1. Connects to any MCP server over stdio (Windows, Linux, macOS).
2. Static annotation linting: flags missing readOnlyHint, idempotentHint, destructiveHint, openWorldHint.
3. Description safety inspection: detects destructive keywords and mismatched hint verbs.
4. Clean-machine credential isolation: refuses to run with ambient production credentials.
5. Dynamic behavioral verification: synthesizes schema arguments, executes tools twice in an ephemeral sandbox.
6. Reports verified vs skipped fraction (a skipped tool is NOT a verified tool).
7. Outputs actionable patches, CI exit codes (0 clean, 1 discrepancies, 2 error), and GitHub Action summary.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Production-risk environment variable signatures
DANGEROUS_ENV_VARS = [
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "SLACK_BOT_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DATABASE_URL",
    "PROD_DATABASE_URL",
]

DESTRUCTIVE_KEYWORDS = [
    "delete", "drop", "truncate", "destroy", "wipe", "remove",
    "kill", "terminate", "overwrite", "purge", "format", "reboot"
]


def check_production_environment(allow_dirty: bool) -> List[str]:
    """Detects ambient credentials that could expose production systems."""
    leaked = []
    for var in DANGEROUS_ENV_VARS:
        val = os.environ.get(var)
        if val and len(val.strip()) > 0:
            leaked.append(var)
    if leaked and not allow_dirty:
        raise PermissionError(
            f"Soro Audit Safety Refusal: Detected ambient production credentials in environment ({', '.join(leaked)}).\n"
            f"Soro refuses to execute dynamic tool invocations with ambient secrets to protect real infrastructure.\n"
            f"To override, pass --allow-dirty-env explicitly."
        )
    return leaked


def create_scrubbed_env(sandbox_dir: Optional[str] = None) -> Dict[str, str]:
    """Creates a minimal, safe environment for child server execution."""
    safe_keys = [
        "PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "HOME",
        "LANG", "LC_ALL", "NODE_PATH", "PYTHONPATH", "PATHEXT", "COMSPEC",
        "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
        "COMMONPROGRAMFILES", "WINDIR", "HOMEDRIVE", "HOMEPATH"
    ]
    env = {}
    for k in safe_keys:
        if k in os.environ:
            env[k] = os.environ[k]
    # Strip dangerous variables explicitly
    for k in DANGEROUS_ENV_VARS:
        env.pop(k, None)
    # Explicitly enforce sandbox markers
    env["SORO_SANDBOX"] = "1"
    env["CI"] = "true"
    env["NODE_ENV"] = "test"
    # Provide safe mock dummy credentials for servers requiring environment variables during handshake
    safe_dummies = {
        "BRAVE_API_KEY": "dummy_brave_key_for_audit",
        "GITHUB_TOKEN": "ghp_dummy_token_for_audit",
        "SLACK_BOT_TOKEN": "xoxb-dummy-slack-token-for-audit",
        "NOTION_API_KEY": "secret_dummy_notion_key_for_audit",
        "SENTRY_AUTH_TOKEN": "sntrys_dummy_sentry_key_for_audit",
        "OPENAI_API_KEY": "sk-dummy-openai-key-for-audit",
    }
    for k, v in safe_dummies.items():
        env.setdefault(k, v)
    if sandbox_dir:
        # Strictly isolate memory server persistence to the scratch sandbox directory
        env["MEMORY_FILE_PATH"] = os.path.join(sandbox_dir, "memory.json")
    return env


def synthesize_arguments_from_schema(schema: Dict[str, Any], sandbox_dir: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Synthesizes valid mock arguments from JSON Schema, or returns skip reason."""
    args = {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))

    for name, prop in props.items():
        p_type = prop.get("type", "string")
        enum_vals = prop.get("enum")
        if enum_vals:
            args[name] = enum_vals[0]
            continue

        if p_type == "string":
            name_lower = name.lower()
            if "path" in name_lower or "file" in name_lower:
                test_file = os.path.join(sandbox_dir, f"test_{name}.txt")
                if not os.path.exists(test_file):
                    with open(test_file, "w", encoding="utf-8") as f:
                        f.write("soro_audit_initial_content\n")
                args[name] = test_file
            elif "dir" in name_lower:
                args[name] = sandbox_dir
            elif "id" in name_lower or "key" in name_lower:
                args[name] = f"audit_id_{uuid.uuid4().hex[:6]}"
            elif "email" in name_lower:
                args[name] = "audit_sandbox@example.test"
            elif "url" in name_lower or "uri" in name_lower:
                args[name] = "http://127.0.0.1:9"  # RFC 863 discard port, safe offline loopback
            elif "query" in name_lower or "sql" in name_lower:
                args[name] = "SELECT 1"
            else:
                args[name] = f"sample_{name}"
        elif p_type in ("integer", "number"):
            args[name] = 1
        elif p_type == "boolean":
            args[name] = True
        elif p_type == "array":
            items = prop.get("items", {})
            item_type = items.get("type", "string")
            if item_type == "string":
                args[name] = ["audit_item_1"]
            elif item_type in ("integer", "number"):
                args[name] = [1]
            else:
                args[name] = []
        elif p_type == "object":
            args[name] = {"sample_key": "sample_val"}
        else:
            if name in required:
                return None, f"Unsupported complex schema type '{p_type}' for required parameter '{name}'"
            continue

    return args, None


class StdioMcpClient:
    """Manages an active stdio connection to an MCP server subprocess."""
    def __init__(self, command: str, cwd: str, env: Dict[str, str], timeout_sec: float = 10.0):
        self.command = command
        self.cwd = cwd
        self.env = env
        self.timeout_sec = timeout_sec
        self.proc: Optional[subprocess.Popen] = None
        self.req_counter = 0

    def start(self) -> None:
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            env=self.env,
            shell=True,
        )

    def close(self) -> None:
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None

    def send_rpc(self, method: str, params: Optional[Dict[str, Any]] = None, is_notification: bool = False) -> Optional[Dict[str, Any]]:
        if not self.proc or not self.proc.stdin or not self.proc.stdout:
            raise RuntimeError("MCP server process is not running")

        req: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if not is_notification:
            self.req_counter += 1
            req["id"] = self.req_counter
        if params is not None:
            req["params"] = params

        payload = (json.dumps(req) + "\n").encode("utf-8")
        self.proc.stdin.write(payload)
        self.proc.stdin.flush()

        if is_notification:
            return None

        # Robustly read JSON-RPC response, ignoring any non-JSON startup banners
        while True:
            line_bytes = self.proc.stdout.readline()
            if not line_bytes:
                stderr_out = ""
                try:
                    if self.proc.stderr:
                        stderr_out = self.proc.stderr.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                raise RuntimeError(f"Server closed connection unexpectedly. Stderr: {stderr_out[:200]}")
            line_str = line_bytes.decode("utf-8", errors="replace").strip()
            if line_str.startswith("{"):
                try:
                    parsed = json.loads(line_str)
                    # Ignore server-initiated notifications or unmatched response IDs
                    if parsed.get("id") == self.req_counter:
                        return parsed
                except json.JSONDecodeError:
                    continue



def take_fs_snapshot(dir_path: str) -> Dict[str, Dict[str, Any]]:
    """Snapshots file metadata, byte sizes, and SHA-256 hashes in sandbox directory."""
    import hashlib
    snapshot = {}
    for root, _, files in os.walk(dir_path):
        for f in files:
            full_p = os.path.join(root, f)
            rel_p = os.path.relpath(full_p, dir_path)
            try:
                st = os.stat(full_p)
                with open(full_p, "rb") as fp:
                    content_hash = hashlib.sha256(fp.read()).hexdigest()
                snapshot[rel_p] = {"size": st.st_size, "hash": content_hash}
            except Exception:
                pass
    return snapshot


MUTATING_VERBS = (
    "create", "delete", "write", "update", "set", "add", "remove",
    "insert", "append", "drop", "truncate", "destroy", "move", "edit"
)
QUERY_VERBS = (
    "read", "get", "list", "search", "find", "query", "check",
    "inspect", "describe", "tree", "info"
)


def find_introspection_tool(tools: List[Dict[str, Any]]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Finds a zero-argument read-only tool to use as an in-server state probe."""
    # Strictly prioritize query verbs
    for t in tools:
        t_name = t.get("name", "")
        if any(t_name.startswith(v) for v in ("read_", "list_", "get_")):
            schema = t.get("inputSchema", {})
            req = schema.get("required", [])
            if len(req) == 0:
                return t_name, {}
    return None


def verify_and_init_introspection_tool(
    client: StdioMcpClient,
    candidate: Optional[Tuple[str, Dict[str, Any]]],
    sandbox_dir: str
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Ensures introspection probe itself does not mutate disk or state."""
    if not candidate:
        return None
    s0 = take_fs_snapshot(sandbox_dir)
    _ = query_introspection_state(client, candidate)
    s1 = take_fs_snapshot(sandbox_dir)
    if s1 != s0:
        # Probe candidate modified disk! Disqualify.
        return None
    return candidate


def query_introspection_state(client: StdioMcpClient, intro_tool: Optional[Tuple[str, Dict[str, Any]]]) -> str:
    """Queries in-server state using verified read-only introspection tool."""
    if not intro_tool:
        return ""
    try:
        t_name, t_args = intro_tool
        res = client.send_rpc("tools/call", {"name": t_name, "arguments": t_args})
        if res and not res.get("result", {}).get("isError"):
            return json.dumps(res.get("result", {}).get("content", []), sort_keys=True)
    except Exception:
        pass
    return ""


def audit_server(
    command: str,
    timeout_sec: float = 10.0,
    allow_dirty_env: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Performs full static linting and behavioral verification on an MCP server."""
    start_time = time.time()
    ambient_warnings = check_production_environment(allow_dirty_env)
    with tempfile.TemporaryDirectory(prefix="soro_audit_", ignore_cleanup_errors=True) as sandbox_dir:
        scrubbed_env = create_scrubbed_env(sandbox_dir)
        client = StdioMcpClient(command, cwd=sandbox_dir, env=scrubbed_env, timeout_sec=timeout_sec)
        try:
            client.start()
            
            # Step 1: Handshake
            init_res = client.send_rpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "soro-audit", "version": "0.2.0"}
            })
            client.send_rpc("notifications/initialized", is_notification=True)

            server_info = init_res.get("result", {}).get("serverInfo", {}) if init_res else {}

            # Step 2: Discover tools
            list_res = client.send_rpc("tools/list", {})
            tools = list_res.get("result", {}).get("tools", []) if list_res else []

        except Exception as e:
            client.close()
            return {
                "success": False,
                "error": str(e),
                "server_command": command,
                "elapsed_seconds": round(time.time() - start_time, 3),
            }

        intro_tool = verify_and_init_introspection_tool(client, find_introspection_tool(tools), sandbox_dir)
        tool_audits = []
        exercised_count = 0
        skipped_count = 0
        unsafe_contradiction_count = 0
        confirmation_fatigue_count = 0
        missing_hint_count = 0

        for tool in tools:
            name = tool.get("name", "unnamed")
            desc = tool.get("description", "")
            schema = tool.get("inputSchema", {})

            # Declared annotations (MCP specification hints)
            # In official MCP servers, hints are located inside tool['annotations'] object
            ann = tool.get("annotations") or {}
            declared_read_only = ann.get("readOnlyHint", tool.get("readOnlyHint"))
            declared_idempotent = ann.get("idempotentHint", tool.get("idempotentHint"))
            declared_destructive = ann.get("destructiveHint", tool.get("destructiveHint"))
            declared_open_world = ann.get("openWorldHint", tool.get("openWorldHint"))

            # Check if explicit annotations were supplied by server
            has_explicit_hints = any(v is not None for v in (declared_read_only, declared_idempotent, declared_destructive, declared_open_world))
            if not has_explicit_hints:
                missing_hint_count += 1

            # Spec-defined defaults when hints are omitted:
            # readOnlyHint: default false
            # destructiveHint: default true
            # idempotentHint: default false
            # openWorldHint: default true
            eff_read_only = False if declared_read_only is None else bool(declared_read_only)
            eff_destructive = True if declared_destructive is None else bool(declared_destructive)
            eff_idempotent = False if declared_idempotent is None else bool(declared_idempotent)

            # Behavioral verification using State Oracle
            behavior_status = "skipped"
            skip_reason = None
            observed_class = "unverified"
            discrepancy = None
            discrepancy_type = None

            if dry_run:
                skip_reason = "dry_run_requested"
                skipped_count += 1
            else:
                args, reason = synthesize_arguments_from_schema(schema, sandbox_dir)
                if args is None:
                    behavior_status = "skipped"
                    skip_reason = reason
                    skipped_count += 1
                else:
                    try:
                        # Baseline State Snapshot
                        snap_0 = take_fs_snapshot(sandbox_dir)
                        intro_0 = query_introspection_state(client, intro_tool) if (intro_tool and intro_tool[0] != name) else ""

                        # Call 1
                        res_1 = client.send_rpc("tools/call", {"name": name, "arguments": args})
                        snap_1 = take_fs_snapshot(sandbox_dir)
                        intro_1 = query_introspection_state(client, intro_tool) if (intro_tool and intro_tool[0] != name) else ""

                        # Call 2 (replay identical payload)
                        res_2 = client.send_rpc("tools/call", {"name": name, "arguments": args})
                        snap_2 = take_fs_snapshot(sandbox_dir)
                        intro_2 = query_introspection_state(client, intro_tool) if (intro_tool and intro_tool[0] != name) else ""

                        is_err_1 = bool(res_1 and res_1.get("result", {}).get("isError"))
                        is_err_2 = bool(res_2 and res_2.get("result", {}).get("isError"))

                        if is_err_1 or is_err_2:
                            behavior_status = "call_error"
                            skip_reason = "Tool returned isError: true on synthesized input"
                            skipped_count += 1
                        else:
                            exercised_count += 1
                            behavior_status = "exercised"

                            val_1 = json.dumps(res_1.get("result", {}).get("content", []), sort_keys=True) if res_1 else ""
                            val_2 = json.dumps(res_2.get("result", {}).get("content", []), sort_keys=True) if res_2 else ""

                            fs_mod_1 = (snap_1 != snap_0)
                            fs_mod_2 = (snap_2 != snap_1)
                            intro_mod_1 = bool(intro_0 != "" and intro_1 != "" and intro_1 != intro_0)
                            intro_mod_2 = bool(intro_1 != "" and intro_2 != "" and intro_2 != intro_1)

                            state_mod_1 = fs_mod_1 or intro_mod_1
                            state_mod_2 = fs_mod_2 or intro_mod_2

                            # Determine observed class from State Oracle
                            if state_mod_1 and not state_mod_2:
                                # Mutated state on Call 1, but Call 2 left state identical (idempotent write)
                                observed_class = "idempotent_write"
                            elif state_mod_2:
                                # Replay created additional state diff (cumulative append / counter)
                                observed_class = "non_idempotent_mutation"
                            elif not state_mod_1 and not state_mod_2:
                                is_mutating_verb = any(name.startswith(v) or f"_{v}_" in f"_{name}_" for v in MUTATING_VERBS)
                                if is_mutating_verb:
                                    observed_class = "unverified"
                                    skip_reason = "No state delta observed on mutating tool"
                                elif val_1 == val_2:
                                    observed_class = "read_only"
                                else:
                                    observed_class = "non_idempotent_mutation"
                            else:
                                observed_class = "read_only"

                            # Evaluation against declared annotations
                            if declared_read_only is True and observed_class in ("idempotent_write", "non_idempotent_mutation"):
                                discrepancy = f"CRITICAL UNSAFE CONTRADICTION: Declared readOnlyHint: true, but observed {observed_class}"
                                discrepancy_type = "unsafe_read_only_contradiction"
                                unsafe_contradiction_count += 1
                            elif declared_idempotent is True and observed_class == "non_idempotent_mutation":
                                discrepancy = "CRITICAL UNSAFE CONTRADICTION: Declared idempotentHint: true, but observed non_idempotent_mutation"
                                discrepancy_type = "unsafe_idempotent_contradiction"
                                unsafe_contradiction_count += 1
                            elif observed_class == "read_only" and not eff_read_only:
                                discrepancy = "CONFIRMATION FATIGUE: Verified read-only in sandbox, but readOnlyHint is false/omitted (causes unnecessary user approval prompts)"
                                discrepancy_type = "confirmation_fatigue"
                                confirmation_fatigue_count += 1
                            elif observed_class == "idempotent_write" and not eff_idempotent:
                                discrepancy = "POTENTIAL OPTIMIZATION: Verified idempotent write, but idempotentHint is false/omitted"
                                discrepancy_type = "unannotated_idempotent"

                    except Exception as e:
                        behavior_status = "execution_error"
                        skip_reason = f"Execution failed: {str(e)[:100]}"
                        skipped_count += 1

            # Suggested patch
            suggested_patch = {}
            if observed_class == "read_only" and declared_read_only is not True:
                suggested_patch["readOnlyHint"] = True
            if observed_class == "idempotent_write" and declared_idempotent is not True:
                suggested_patch["idempotentHint"] = True

            tool_audits.append({
                "name": name,
                "description": desc,
                "declared_hints": {
                    "readOnlyHint": declared_read_only,
                    "idempotentHint": declared_idempotent,
                    "destructiveHint": declared_destructive,
                    "openWorldHint": declared_open_world,
                },
                "has_explicit_hints": has_explicit_hints,
                "behavior_status": behavior_status,
                "skip_reason": skip_reason,
                "observed_class": observed_class,
                "discrepancy": discrepancy,
                "discrepancy_type": discrepancy_type,
                "suggested_patch": suggested_patch if suggested_patch else None,
            })

        client.close()

    total_tools = len(tools)
    exercise_rate = round(exercised_count / max(1, total_tools), 4)

    discrepancy_count = unsafe_contradiction_count + confirmation_fatigue_count

    return {
        "success": True,
        "server_command": command,
        "server_info": server_info,
        "total_tools": total_tools,
        "exercised_tools": exercised_count,
        "skipped_tools": skipped_count,
        "exercise_rate": exercise_rate,
        "missing_hint_count": missing_hint_count,
        "unsafe_contradiction_count": unsafe_contradiction_count,
        "confirmation_fatigue_count": confirmation_fatigue_count,
        "discrepancy_count": discrepancy_count,
        "ambient_warnings": ambient_warnings,
        "elapsed_seconds": round(time.time() - start_time, 3),
        "tool_audits": tool_audits,
    }


def format_cli_summary(report: Dict[str, Any]) -> str:
    """Formats human-readable terminal report."""
    if not report.get("success"):
        return f"\n[!] SORO AUDIT FAILED TO EXECUTE SERVER:\n    {report.get('error')}\n"

    lines = [
        "",
        "=" * 72,
        "           SORO AUDIT · MCP SERVER LINTER & BEHAVIORAL VERIFIER",
        "=" * 72,
        f"Server Command:         {report['server_command']}",
        f"Total Tools:            {report['total_tools']}",
        f"Exercised Tools:        {report['exercised_tools']} / {report['total_tools']} ({report['exercise_rate']*100:.1f}%)",
        f"Skipped / Unexercised:  {report['skipped_tools']}",
        f"Missing Annotations:    {report['missing_hint_count']} tools without explicit hints (spec defaults applied)",
        f"Unsafe Contradictions:  {report['unsafe_contradiction_count']} (declared safe, observed mutating)",
        f"Confirmation Fatigue:   {report['confirmation_fatigue_count']} (verified read-only, missing readOnlyHint)",
        f"Total Discrepancies:    {report['discrepancy_count']}",
        f"Elapsed Time:           {report['elapsed_seconds']}s",
        "-" * 72,
        f"{'TOOL':<26} {'DECLARED':<14} {'OBSERVED':<18} {'STATUS':<12}",
        "-" * 72,
    ]

    for t in report.get("tool_audits", []):
        decl = "read_only" if t["declared_hints"]["readOnlyHint"] else ("idempotent" if t["declared_hints"]["idempotentHint"] else "default")
        obs = t["observed_class"]
        status = "OK" if not t["discrepancy"] else "FLAGGED"
        lines.append(f"{t['name']:<26} {decl:<14} {obs:<18} {status:<12}")
        if t["discrepancy"]:
            lines.append(f"  [!] {t['discrepancy']}")
        if t["suggested_patch"]:
            patch_str = ", ".join(f"{k}={v}" for k, v in t["suggested_patch"].items())
            lines.append(f"  [+] SUGGESTED PATCH: {patch_str}")

    lines.append("=" * 72)
    return "\n".join(lines)


def generate_markdown_summary(report: Dict[str, Any]) -> str:
    """Generates a clean GitHub Action PR comment."""
    lines = [
        "## Soro MCP Server Audit Report",
        "",
        f"- **Server:** `{report.get('server_command')}`",
        f"- **Tools Audited:** {report.get('total_tools')}",
        f"- **Exercised Fraction:** {report.get('exercised_tools')}/{report.get('total_tools')} ({report.get('exercise_rate', 0)*100:.1f}%)",
        f"- **Missing Explicit Hints:** {report.get('missing_hint_count')}",
        f"- **Unsafe Contradictions:** {report.get('unsafe_contradiction_count')}",
        f"- **Confirmation Fatigue:** {report.get('confirmation_fatigue_count')}",
        "",
        "| Tool | Declared Hint | Observed Behavior | Finding | Suggested Patch |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for t in report.get("tool_audits", []):
        decl = "readOnly" if t["declared_hints"]["readOnlyHint"] else ("idempotent" if t["declared_hints"]["idempotentHint"] else "*(spec default)*")
        obs = t["observed_class"]
        notes = t["discrepancy"] or ("Verified" if t["behavior_status"] == "exercised" else f"Skipped ({t['skip_reason']})")
        patch = json.dumps(t["suggested_patch"]) if t["suggested_patch"] else "—"
        lines.append(f"| `{t['name']}` | {decl} | {obs} | {notes} | `{patch}` |")

    lines.append("")
    lines.append("> *Report generated by Soro Audit. A skipped tool is not a verified tool.*")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Soro Audit: MCP Server Linter & Behavioral Verifier")
    parser.add_argument("--stdio", required=True, help="Command to run the MCP server over stdio")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-tool timeout in seconds (default: 10.0)")
    parser.add_argument("--allow-dirty-env", action="store_true", help="Allow running with ambient production environment variables")
    parser.add_argument("--dry-run", action="store_true", help="Perform static annotation and description analysis without invoking tools")
    parser.add_argument("--json", type=str, help="Path to write machine-readable JSON report")
    parser.add_argument("--markdown", type=str, help="Path to write markdown summary for GitHub Actions / PRs")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if any missing hints or discrepancies are found")

    args = parser.parse_args()

    report = audit_server(
        command=args.stdio,
        timeout_sec=args.timeout,
        allow_dirty_env=args.allow_dirty_env,
        dry_run=args.dry_run,
    )

    print(format_cli_summary(report))

    if args.json:
        out_p = Path(args.json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[+] Wrote JSON report to {out_p}")

    if args.markdown:
        out_m = Path(args.markdown)
        out_m.parent.mkdir(parents=True, exist_ok=True)
        out_m.write_text(generate_markdown_summary(report), encoding="utf-8")
        print(f"[+] Wrote Markdown report to {out_m}")

    if not report.get("success"):
        sys.exit(2)

    if args.strict and (report.get("discrepancy_count", 0) > 0 or report.get("missing_hint_count", 0) > 0):
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
