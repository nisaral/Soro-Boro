"""E2E: Odyssey + Veyra wrap on filesystem rename (MCPMark largest_rename semantics)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python" / "src"))

from openai import OpenAI

from veyra.core.execution_contract import SideEffectClass
from veyra.production.production_layer import VeyraMiddleware

ROOT = Path(
    os.environ.get(
        "FILESYSTEM_TEST_ROOT",
        str(REPO.parent / "third_party" / "mcpmark" / "test_environments" / "file_property"),
    )
)


def client() -> OpenAI:
    return OpenAI(
        base_url=os.environ.get("ODYSSEY_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://odysseyapi.tech/v1",
        api_key=os.environ["ODYSSEY_API_KEY"] if os.environ.get("ODYSSEY_API_KEY") else os.environ["OPENAI_API_KEY"],
    )


def list_jpgs(root: Path) -> list[dict]:
    rows = []
    for p in root.glob("*.jpg"):
        rows.append({"name": p.name, "bytes": p.stat().st_size})
    return sorted(rows, key=lambda r: r["bytes"], reverse=True)


def rename_file(src: str, dst: str) -> dict:
    sp, dp = ROOT / src, ROOT / dst
    if not sp.exists():
        raise FileNotFoundError(src)
    sp.rename(dp)
    return {"ok": True, "src": src, "dst": dst}


def verify() -> dict:
    largest = ROOT / "largest.jpg"
    sg = ROOT / "sg.jpg"
    return {"largest_exists": largest.exists(), "sg_gone": not sg.exists(), "pass": largest.exists() and not sg.exists()}


def main() -> int:
    files = list_jpgs(ROOT)
    mw = VeyraMiddleware()
    wrapped = mw.wrap_function(
        rename_file,
        name="rename_file",
        side_effect_class=SideEffectClass.IDEMPOTENT_WRITE,
    )
    tools = [
        {
            "type": "function",
            "function": {
                "name": "rename_file",
                "description": "Rename a file in the test directory.",
                "parameters": {
                    "type": "object",
                    "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
                    "required": ["src", "dst"],
                },
            },
        }
    ]
    r = client().chat.completions.create(
        model=os.environ.get("ODYSSEY_MODEL", "openai/gpt-5.5"),
        temperature=0,
        max_tokens=256,
        tools=tools,
        messages=[
            {
                "role": "user",
                "content": (
                    "Rename the largest .jpg by file size to largest.jpg. "
                    "Pick the file with the maximum bytes. "
                    f"Files: {json.dumps(files)}"
                ),
            }
        ],
    )
    msg = r.choices[0].message
    if not msg.tool_calls:
        print(json.dumps({"error": "no_tool_call", "content": msg.content}))
        return 1
    args = json.loads(msg.tool_calls[0].function.arguments)
    wrapped(**args)
    v = verify()
    out = {"files_before": files, "tool_args": args, "verify": v, "tokens": r.usage.total_tokens if r.usage else None}
    dest = REPO / "eval_lab" / "out" / "mcp_fs_veyra_largest.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if v["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
