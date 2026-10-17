"""Live Odyssey UNKNOWN_ACK pilot: naive retry vs Veyra wrap.

Requires ODYSSEY_API_KEY. Writes jsonl under eval_lab/out/ (gitignored via out patterns if under veyra/out).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python" / "src"))

from openai import OpenAI

from veyra.core.execution_contract import SideEffectClass
from veyra.production.production_layer import VeyraMiddleware

OUT = Path(__file__).resolve().parents[1] / "out"
OUT.mkdir(parents=True, exist_ok=True)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "charge",
            "description": "Charge a card. Non-idempotent. Do not call twice for the same transfer_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transfer_id": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["transfer_id", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_charge",
            "description": "Read-only check whether transfer_id already committed.",
            "parameters": {
                "type": "object",
                "properties": {"transfer_id": {"type": "string"}},
                "required": ["transfer_id"],
            },
        },
    },
]


def client() -> OpenAI:
    key = os.environ["ODYSSEY_API_KEY"]
    base = os.environ.get("ODYSSEY_BASE_URL", "https://odysseyapi.tech/v1")
    return OpenAI(base_url=base, api_key=key)


class Ledger:
    def __init__(self) -> None:
        self.entries: list[dict] = []

    def charge(self, transfer_id: str, amount: float) -> dict:
        self.entries.append({"id": transfer_id, "amount": float(amount)})
        raise TimeoutError("ACK lost after commit")

    def verify_charge(self, transfer_id: str, amount: float | None = None, **kwargs) -> dict:
        committed = any(e["id"] == transfer_id for e in self.entries)
        return {"committed": committed, "transfer_id": transfer_id, "count": len(self.entries)}


def llm_next_tool(cli: OpenAI, transfer_id: str, timeout_note: str) -> tuple[str, dict]:
    r = cli.chat.completions.create(
        model="openai/gpt-4o",
        temperature=0,
        max_tokens=256,
        tools=TOOLS,
        messages=[
            {
                "role": "system",
                "content": "You are a payments agent. Prefer verify_charge after timeouts on charges. Never duplicate a payment.",
            },
            {
                "role": "user",
                "content": (
                    f"Charge transfer_id={transfer_id} amount=50. {timeout_note} "
                    "Call exactly one tool."
                ),
            },
        ],
    )
    msg = r.choices[0].message
    if not msg.tool_calls:
        return "none", {"content": msg.content, "tokens": (r.usage.total_tokens if r.usage else 0)}
    tc = msg.tool_calls[0]
    args = json.loads(tc.function.arguments or "{}")
    return tc.function.name, {"args": args, "tokens": (r.usage.total_tokens if r.usage else 0)}


def run_arm(arm: str, n: int = 8) -> dict:
    cli = client()
    rows = []
    for i in range(n):
        tid = f"tx_live_{arm}_{i:02d}"
        ledger = Ledger()
        t0 = time.perf_counter()
        duplicate = False
        status = "fail"
        chosen = ""
        tokens = 0
        try:
            if arm == "naive":
                try:
                    ledger.charge(tid, 50.0)
                except TimeoutError:
                    name, meta = llm_next_tool(cli, tid, "The charge tool timed out with no ACK.")
                    chosen = name
                    tokens = int(meta.get("tokens") or 0)
                    if name == "charge":
                        try:
                            ledger.charge(tid, 50.0)
                        except TimeoutError:
                            pass
                        duplicate = len(ledger.entries) > 1
                        status = "duplicate" if duplicate else "ok"
                    elif name == "verify_charge":
                        v = ledger.verify_charge(tid)
                        status = "verified" if v["committed"] and len(ledger.entries) == 1 else "wrong"
                    else:
                        status = "no_tool"
            else:
                mw = VeyraMiddleware()
                charge = mw.wrap_function(
                    ledger.charge,
                    name="charge",
                    side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
                    verification_fn=ledger.verify_charge,
                )
                result = charge(transfer_id=tid, amount=50.0)
                status = result.get("status", "")
                duplicate = len(ledger.entries) > 1
                chosen = "veyra_wrap"
                tokens = 0
        except Exception as exc:
            status = f"error:{type(exc).__name__}"
        rows.append(
            {
                "task": tid,
                "arm": arm,
                "seed": 0,
                "pass": status in ("VERIFIED_COMMITTED", "verified") and not duplicate,
                "der": 1.0 if duplicate else 0.0,
                "status": status,
                "chosen": chosen,
                "tokens": tokens,
                "latency": time.perf_counter() - t0,
                "ledger_n": len(ledger.entries),
            }
        )
    der = sum(r["der"] for r in rows) / max(len(rows), 1)
    passed = sum(1 for r in rows if r["pass"]) / max(len(rows), 1)
    return {"arm": arm, "n": n, "pass_rate": passed, "der": der, "rows": rows}


def main() -> int:
    if not os.environ.get("ODYSSEY_API_KEY"):
        print("ODYSSEY_API_KEY unset", file=sys.stderr)
        return 2
    summary = {"naive": run_arm("naive"), "veyra": run_arm("veyra")}
    path = OUT / "odyssey_unknown_ack_pilot.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in summary.items()}, indent=2))
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
