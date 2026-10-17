r"""Veyra Working Example: Strong Idempotency Key Semantics (Section 29).

Demonstrates:
- Logical idempotency identity computed from original intent (intent_id + tool + canonical_args).
- Key persistence across retries and process restarts.

Run from fresh checkout:
python examples/idempotency/demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from veyra.core.idempotency import IdempotencyIdentity, IdempotencyKeyStore


def run_demo():
    print("=" * 60)
    print("VEYRA DEMO: STRONG IDEMPOTENCY KEY SEMANTICS")
    print("=" * 60)

    store = IdempotencyKeyStore()

    print("\n1. Initial Mutation Attempt:")
    id1 = store.get_or_create(intent_id="order_intent_77", tool="create_order", arguments={"item_id": "item_9", "qty": 2})
    print(f"Generated Idempotency Key: {id1.key}")

    print("\n2. Network Timeout Fault / Retry Attempt:")
    id2 = store.get_or_create(intent_id="order_intent_77", tool="create_order", arguments={"item_id": "item_9", "qty": 2})
    print(f"Retried Idempotency Key:   {id2.key}")

    assert id1.key == id2.key
    print(f"\nInvariant Check: id1.key == id2.key is {id1.key == id2.key}")
    print("Same logical mutation -> Same idempotency identity across retries!")


if __name__ == "__main__":
    run_demo()
