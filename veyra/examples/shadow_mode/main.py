"""Example 5: Shadow Mode Observability and Dry Run Evaluation.

Runnable from fresh checkout.
Demonstrates:
- SHADOW mode: runs un-altered while recording Veyra evaluation in background
- DRY_RUN mode: returns decision explanation without executing tool
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from veyra.production.production_layer import Mode, ProductionConfig, VeyraMiddleware


def production_action(x: int):
    return {"status": "LIVE_EXECUTION", "computed": x * 10}


def main():
    print("=== Veyra Drop-In Middleware: Shadow & Dry-Run Modes ===\n")

    # 1. Shadow Mode
    mw_shadow = VeyraMiddleware(ProductionConfig(mode=Mode.SHADOW))
    shadow_tool = mw_shadow.wrap_function(production_action, name="production_action")

    print("1. Running in SHADOW mode (transparent live execution + audit):")
    res_live = shadow_tool(x=7)
    print(f"  Live result: {res_live}")
    print(f"  Audit entries recorded: {len(mw_shadow.audit_trail)}")
    print(f"  Shadow decision: {mw_shadow.audit_trail[-1]['explanation']['decision']}\n")

    # 2. Dry Run Mode
    mw_dry = VeyraMiddleware(ProductionConfig(mode=Mode.DRY_RUN))
    dry_tool = mw_dry.wrap_function(production_action, name="production_action")

    print("2. Running in DRY_RUN mode (evaluates invariants without executing):")
    res_dry = dry_tool(x=7)
    print(f"  Dry run payload: {res_dry}")
    print(f"  Selected: {res_dry['selected_tool']}")
    print(f"  Checks: {res_dry['explanation']['checks']}")

    print("\n=== Shadow & Dry Run Example Completed Successfully ===")


if __name__ == "__main__":
    main()
