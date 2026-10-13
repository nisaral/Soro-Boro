"""Verification Gate for Soro Claims Ledger.

Loads reports/CLAIMS_LEDGER.json and cross-verifies every single claimed value
against the underlying generated artifact JSON files.
Exits 0 if all claims match ground-truth machine artifacts exactly.
Exits 1 if any discrepancy or missing key is detected.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_nested(data: dict, path: str):
    if path == "annotations_rate":
        tools = data.get("result", {}).get("tools", [])
        if not tools:
            return 0.0
        ann_count = sum(1 for t in tools if "annotations" in t and any(v is not None for v in t["annotations"].values()))
        return ann_count / len(tools)

    parts = path.split(".")
    curr = data
    for p in parts:
        if p == "length" and isinstance(curr, (list, dict, str)):
            return len(curr)
        if "[" in p and p.endswith("]"):
            key, idx_str = p[:-1].split("[")
            idx = int(idx_str)
            curr = curr[key][idx]
        else:
            curr = curr[p]
    if isinstance(curr, list) and parts[-1] != "length":
        return len(curr)
    return curr


def verify_claims() -> bool:
    ledger_file = ROOT / "reports" / "CLAIMS_LEDGER.json"
    if not ledger_file.exists():
        print(f"[!] Claims ledger not found: {ledger_file}")
        return False

    ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
    claims = ledger.get("claims", [])
    commit = ledger.get("git_commit", "unknown")
    tree_status = ledger.get("tree_status", "unknown")
    print(f"Verifying {len(claims)} claims from Claims Ledger (Commit: {commit}, Tree: {tree_status})...\n")

    cache = {}
    passed = 0
    failed = 0

    for c in claims:
        cid = c["claim_id"]
        stmt = c["statement"]
        exp = c["expected_value"]
        rfile = c["report_file"]
        jpath = c["json_path"]
        raw_art = c.get("raw_artifact")
        ev_qual = c.get("evidence_quality")

        if not ev_qual:
            print(f"[FAIL] {cid}: Missing evidence_quality field")
            failed += 1
            continue

        if raw_art:
            raw_path = ROOT / raw_art
            if not raw_path.exists():
                print(f"[FAIL] {cid}: Raw artifact file missing: {raw_art}")
                failed += 1
                continue

        full_path = ROOT / rfile
        if not full_path.exists():
            print(f"[FAIL] {cid}: Report file missing: {rfile}")
            failed += 1
            continue

        if rfile not in cache:
            cache[rfile] = json.loads(full_path.read_text(encoding="utf-8"))

        data = cache[rfile]
        try:
            actual = get_nested(data, jpath)
        except Exception as e:
            print(f"[FAIL] {cid}: Key path '{jpath}' not found in {rfile}: {e}")
            failed += 1
            continue

        # Check equality (float or exact)
        match = False
        if isinstance(exp, float) and isinstance(actual, float):
            match = math.isclose(exp, actual, rel_tol=1e-3, abs_tol=1e-4)
        else:
            match = (exp == actual)

        if match:
            print(f"[PASS] {cid:<36} => {actual} (matches expected {exp})")
            passed += 1
        else:
            print(f"[FAIL] {cid:<36} => ACTUAL: {actual} != EXPECTED: {exp}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Claims Ledger Verification: {passed} passed, {failed} failed.")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = verify_claims()
    sys.exit(0 if success else 1)
