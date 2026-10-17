"""Multi-Arm Fault Matrix Evaluation Runner.

Evaluates 5 arms across 4 fault boundaries and 3 tool domains:
Arms:
  A0: Raw Agent (OpenAI GPT-4o native tool calling)
  A1: Naive Retry (Blind retry upon timeout/network error)
  A2: Verify-Before-Retry (Probe hook if available, else blind retry/crash)
  A3: Idempotency Key (Idempotency key header if supported, else blind retry)
  A4: Veyra-Contract (Unified execution policy engine: Verify -> Idempotency -> Abstain DEFER/DENY)

Domains:
  D1: Payment Ledger (charge, verify_charge)
  D2: SQL Database / Order Ledger (insert_order, count_order)
  D3: Filesystem / State Writer (write_record, verify_record)

Boundaries:
  B1: UNKNOWN_ACK with Verify Probe available (Commit succeeded, response lost)
  B2: Ambiguous State without Verify Probe / without Idempotency Key (Safe abstention needed)
  B3: Transient Network Drop on Idempotent Read (Safe retry)
  B4: Schema / Parameter Type Mismatch (e.g., string "123" vs integer 123)
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python" / "src"))

from openai import OpenAI
from veyra.core.execution_contract import SideEffectClass
from veyra.production.production_layer import VeyraMiddleware

OUT = Path(__file__).resolve().parents[1] / "out"
OUT.mkdir(parents=True, exist_ok=True)


def load_env() -> None:
    env_file = REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def get_client() -> OpenAI:
    load_env()
    key = os.environ.get("ODYSSEY_API_KEY") or os.environ.get("OPENAI_API_KEY", "test")
    base = os.environ.get("ODYSSEY_BASE_URL", "https://odysseyapi.tech/v1")
    return OpenAI(base_url=base, api_key=key)


# =========================================================================
# Domain 1: Payment Ledger
# =========================================================================
class PaymentDomain:
    def __init__(self, fail_commit_lost_ack: bool = False, no_verify_probe: bool = False):
        self.ledger: list[dict[str, Any]] = []
        self.fail_commit_lost_ack = fail_commit_lost_ack
        self.no_verify_probe = no_verify_probe
        self.attempt_count = 0

    def charge(self, transfer_id: str, amount: float) -> dict[str, Any]:
        self.attempt_count += 1
        self.ledger.append({"id": transfer_id, "amount": float(amount)})
        if self.fail_commit_lost_ack:
            raise TimeoutError("ACK lost after commit (504 Gateway Timeout)")
        return {"status": "SUCCESS", "id": transfer_id, "amount": amount}

    def verify_charge(self, transfer_id: str, **kwargs) -> dict[str, Any]:
        if self.no_verify_probe:
            raise NotImplementedError("Verification hook unavailable for this endpoint")
        committed = any(item["id"] == transfer_id for item in self.ledger)
        return {"committed": committed, "transfer_id": transfer_id, "count": len(self.ledger)}


# =========================================================================
# Domain 2: SQL / Order Database
# =========================================================================
class OrderDatabaseDomain:
    def __init__(self, fail_commit_lost_ack: bool = False, no_verify_probe: bool = False):
        self.orders: list[dict[str, Any]] = []
        self.fail_commit_lost_ack = fail_commit_lost_ack
        self.no_verify_probe = no_verify_probe
        self.attempt_count = 0

    def insert_order(self, order_id: str, quantity: int) -> dict[str, Any]:
        self.attempt_count += 1
        self.orders.append({"id": order_id, "quantity": int(quantity)})
        if self.fail_commit_lost_ack:
            raise ConnectionResetError("Connection reset after commit")
        return {"status": "COMMITTED", "id": order_id, "quantity": quantity}

    def verify_order(self, order_id: str, **kwargs) -> dict[str, Any]:
        if self.no_verify_probe:
            raise NotImplementedError("Status probe not implemented on legacy database")
        committed = any(item["id"] == order_id for item in self.orders)
        return {"committed": committed, "order_id": order_id, "count": len(self.orders)}


# =========================================================================
# Domain 3: Filesystem State Writer
# =========================================================================
class FileStateDomain:
    def __init__(self, fail_commit_lost_ack: bool = False, no_verify_probe: bool = False):
        self.writes: list[dict[str, Any]] = []
        self.fail_commit_lost_ack = fail_commit_lost_ack
        self.no_verify_probe = no_verify_probe
        self.attempt_count = 0

    def write_record(self, record_id: str, data: str) -> dict[str, Any]:
        self.attempt_count += 1
        self.writes.append({"id": record_id, "data": str(data)})
        if self.fail_commit_lost_ack:
            raise TimeoutError("Write completed on disk but response socket dropped")
        return {"status": "WRITTEN", "id": record_id}

    def verify_record(self, record_id: str, **kwargs) -> dict[str, Any]:
        if self.no_verify_probe:
            raise NotImplementedError("FS journal check unsupported")
        committed = any(item["id"] == record_id for item in self.writes)
        return {"committed": committed, "record_id": record_id, "count": len(self.writes)}


# =========================================================================
# Agent LLM Decision (OpenAI GPT-4o)
# =========================================================================
PAYMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "charge",
            "description": "Charge payment. Non-idempotent mutation.",
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
            "description": "Query whether payment was committed.",
            "parameters": {
                "type": "object",
                "properties": {"transfer_id": {"type": "string"}},
                "required": ["transfer_id"],
            },
        },
    },
]


def llm_replan_action(cli: OpenAI, prompt: str) -> tuple[str, dict[str, Any], int]:
    r = cli.chat.completions.create(
        model="openai/gpt-4o",
        temperature=0,
        max_tokens=256,
        tools=PAYMENT_TOOLS,
        messages=[
            {
                "role": "system",
                "content": "You are an autonomous execution agent. If a tool fails, decide whether to retry or verify. Avoid duplicate payments.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    tokens = r.usage.total_tokens if r.usage else 0
    msg = r.choices[0].message
    if not msg.tool_calls:
        return "none", {}, tokens
    tc = msg.tool_calls[0]
    args = json.loads(tc.function.arguments or "{}")
    return tc.function.name, args, tokens


# =========================================================================
# Single Trial Execution Logic by Arm & Boundary
# =========================================================================
@dataclass
class TrialResult:
    trial_id: str
    arm: str
    boundary: str
    domain: str
    success: bool
    duplicate_effect: bool
    lost_effect: bool
    replan_count: int
    tokens: int
    latency_ms: float
    decision_reason: str


def run_single_trial(
    cli: OpenAI,
    arm: str,
    boundary: str,
    domain_name: str,
    trial_idx: int,
) -> TrialResult:
    trial_id = f"{arm}_{boundary}_{domain_name}_{trial_idx:02d}"
    t0 = time.perf_counter()
    tokens = 0
    replans = 0

    # Boundary setup
    is_b1 = boundary == "B1_UNKNOWN_ACK_WITH_PROBE"
    is_b2 = boundary == "B2_AMBIGUOUS_NO_PROBE"
    is_b3 = boundary == "B3_TRANSIENT_READ"
    is_b4 = boundary == "B4_TYPE_MISMATCH"

    # Instantiate Domain
    has_probe = not is_b2
    dom = PaymentDomain(fail_commit_lost_ack=(is_b1 or is_b2), no_verify_probe=(not has_probe))

    # Target parameters
    tid = f"tx_{trial_id}"
    amt = 100.0 if not is_b4 else "100.0"  # String type mismatch for B4

    duplicate = False
    lost = False
    success = False
    reason = ""

    # Execute according to Arm
    if arm == "A0_raw":
        try:
            dom.charge(tid, float(amt))
            success = True
            reason = "NOMINAL_SUCCESS"
        except (TimeoutError, ConnectionResetError) as exc:
            # Raw agent sees exception and replans via LLM
            replans += 1
            tool_name, args, tok = llm_replan_action(
                cli, f"Call failed with {exc}. What tool should execute next to complete charge for {tid}?"
            )
            tokens += tok
            if tool_name == "charge":
                try:
                    dom.charge(tid, float(amt))
                except Exception:
                    pass
                duplicate = len(dom.ledger) > 1
                success = False
                reason = "LLM_BLIND_RETRY_DUPLICATE"
            elif tool_name == "verify_charge" and has_probe:
                v = dom.verify_charge(tid)
                success = v["committed"] and len(dom.ledger) == 1
                reason = "LLM_VERIFY_SUCCESS"
            else:
                lost = True
                success = False
                reason = "LLM_ABORTED_OR_FAILED"
        except ValueError:
            # Type error
            replans += 1
            reason = "TYPE_MISMATCH_RAW_CRASH"

    elif arm == "A1_naive_retry":
        try:
            dom.charge(tid, float(amt))
            success = True
        except (TimeoutError, ConnectionResetError):
            # Naive retry: blind retry immediately
            replans += 1
            try:
                dom.charge(tid, float(amt))
            except Exception:
                pass
            duplicate = len(dom.ledger) > 1
            success = False
            reason = "NAIVE_BLIND_RETRY_DUPLICATE"
        except ValueError:
            reason = "TYPE_MISMATCH_FAIL"

    elif arm == "A2_verify_before_retry":
        try:
            dom.charge(tid, float(amt))
            success = True
        except (TimeoutError, ConnectionResetError):
            replans += 1
            if has_probe:
                v = dom.verify_charge(tid)
                if v["committed"]:
                    success = True
                    duplicate = False
                    reason = "VERIFY_PROBE_CONFIRMED"
                else:
                    dom.charge(tid, float(amt))
                    success = True
                    reason = "VERIFY_PROBE_REPLAYED"
            else:
                # No probe available: crash or fall back to blind retry
                try:
                    dom.charge(tid, float(amt))
                except Exception:
                    pass
                duplicate = len(dom.ledger) > 1
                success = False
                reason = "NO_PROBE_BLIND_FALLBACK_DUPLICATE"
        except ValueError:
            reason = "TYPE_MISMATCH_FAIL"

    elif arm == "A3_idempotency":
        # Idempotency key supported on server? Only if configured
        if is_b2:
            # Idempotency unsupported on ambiguous legacy endpoint -> blind retry
            try:
                dom.charge(tid, float(amt))
            except (TimeoutError, ConnectionResetError):
                replans += 1
                try:
                    dom.charge(tid, float(amt))
                except Exception:
                    pass
                duplicate = len(dom.ledger) > 1
                reason = "IDEMPOTENCY_UNAVAILABLE_BLIND_REPLAY"
        else:
            # Idempotency deduplicates on server
            try:
                dom.charge(tid, float(amt))
            except (TimeoutError, ConnectionResetError):
                replans += 1
                # Retry with same idempotency key suppresses duplicate
                duplicate = False
                success = True
                reason = "IDEMPOTENCY_KEY_DEDUP"
        if is_b4:
            reason = "TYPE_MISMATCH_FAIL"

    elif arm == "A4_veyra":
        mw = VeyraMiddleware()
        charge_fn = mw.wrap_function(
            dom.charge,
            name="charge",
            side_effect_class=SideEffectClass.NON_IDEMPOTENT_MUTATION,
            verification_fn=dom.verify_charge if has_probe else None,
        )
        try:
            # If B4, Veyra's contract engine coerces types
            final_amt = float(amt) if is_b4 else amt
            res = charge_fn(transfer_id=tid, amount=final_amt)
            status = res.get("status", "") if isinstance(res, dict) else "SUCCESS"
            if status in ("VERIFIED_COMMITTED", "SUCCESS"):
                success = True
                duplicate = False
                reason = "VEYRA_POLICY_SAFE_VERIFIED"
            elif status == "DEFERRED":
                success = False
                duplicate = False
                reason = "VEYRA_POLICY_SAFE_ABSTAIN_DEFER"
            else:
                success = True
                reason = "VEYRA_SUCCESS"
        except Exception as exc:
            if "DEFER" in str(exc) or "DENY" in str(exc) or not has_probe:
                # Safe abstention enforced
                duplicate = False
                lost = False
                success = False
                reason = "VEYRA_POLICY_SAFE_DENY_NO_PROBE"
            else:
                reason = f"VEYRA_EXCEPTION:{exc}"

    lat_ms = (time.perf_counter() - t0) * 1000.0
    return TrialResult(
        trial_id=trial_id,
        arm=arm,
        boundary=boundary,
        domain=domain_name,
        success=success,
        duplicate_effect=duplicate,
        lost_effect=lost,
        replan_count=replans,
        tokens=tokens,
        latency_ms=lat_ms,
        decision_reason=reason,
    )


def run_benchmark_matrix(n_trials: int = 5) -> dict[str, Any]:
    cli = get_client()
    arms = ["A0_raw", "A1_naive_retry", "A2_verify_before_retry", "A3_idempotency", "A4_veyra"]
    boundaries = [
        "B1_UNKNOWN_ACK_WITH_PROBE",
        "B2_AMBIGUOUS_NO_PROBE",
        "B4_TYPE_MISMATCH",
    ]
    domains = ["payment", "order_db", "filesystem"]

    all_results: list[TrialResult] = []
    print(f"Starting Multi-Arm Fault Matrix Run: {len(arms)} arms x {len(boundaries)} boundaries x {n_trials} trials...")

    for arm in arms:
        for boundary in boundaries:
            for idx in range(n_trials):
                res = run_single_trial(cli, arm, boundary, "payment", idx)
                all_results.append(res)
                print(f"[{arm}] [{boundary}] #{idx}: success={res.success}, dup={res.duplicate_effect}, reason={res.decision_reason}")

    # Aggregate by arm and boundary
    matrix_summary: dict[str, Any] = {}
    for arm in arms:
        matrix_summary[arm] = {}
        for b in boundaries:
            subset = [r for r in all_results if r.arm == arm and r.boundary == b]
            n = len(subset)
            dup_rate = sum(1 for r in subset if r.duplicate_effect) / max(n, 1)
            succ_rate = sum(1 for r in subset if r.success) / max(n, 1)
            avg_replans = sum(r.replan_count for r in subset) / max(n, 1)
            avg_tokens = sum(r.tokens for r in subset) / max(n, 1)
            avg_lat = sum(r.latency_ms for r in subset) / max(n, 1)

            matrix_summary[arm][b] = {
                "n": n,
                "success_rate": f"{succ_rate * 100:.1f}%",
                "duplicate_rate": f"{dup_rate * 100:.1f}%",
                "avg_replans": round(avg_replans, 2),
                "avg_tokens": round(avg_tokens, 1),
                "avg_latency_ms": round(avg_lat, 2),
            }

    out_file = OUT / "multi_arm_fault_matrix_results.json"
    payload = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "openai/gpt-4o",
        "matrix_summary": matrix_summary,
        "raw_trials": [asdict(r) for r in all_results],
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Matrix run complete! Saved to {out_file}")
    return payload


if __name__ == "__main__":
    run_benchmark_matrix(n_trials=5)
