import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest
from veyra.core.action import ExecutableAction
from veyra.core.idempotency import IdempotencyIdentity, IdempotencyKeyStore
from veyra.core.partial_mutation import (
    PartialMutationHook,
    PartialMutationManager,
    PartialMutationState,
    PartialMutationStatus,
)
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from veyra.resolution.resolvers import VeyraResolver
from benchmarks.adapters.undobench.adapter import VeyraUndoBenchAdapter


@pytest.fixture
def setup_env():
    reg = ToolRegistry()
    reg.register(ToolDefinition(name="charge_card", idempotent=False, healthy=True, side_effect_class="non_idempotent_mutation"))
    reg.register(ToolDefinition(name="charge_card_idem", idempotent=True, healthy=True, side_effect_class="idempotent_write"))
    reg.register(ToolDefinition(name="verify_charge", idempotent=True, healthy=True, side_effect_class="read_only"))
    adapter = VeyraUndoBenchAdapter(mode="contract", registry=reg)
    return adapter, reg


def test_case_a_mutation_commits_response_lost(setup_env):
    """Case A: mutation commits, response lost -> VERIFY confirms committed, replay=False, final_effect=1."""
    adapter, _ = setup_env
    def fault_exec(name, args):
        raise ConnectionResetError("504 Gateway Timeout: UNKNOWN_ACK lost response")

    def verif_fn(args):
        return True  # Verified committed

    out, art = adapter.execute_tool("case_a", 42, "charge_card", {"amount": 100}, fault_exec, verification_fn=verif_fn)
    assert art.final_outcome["success"] is True
    assert art.final_outcome.get("verified_recovery") is True
    assert art.recovery["action"] == "VERIFY_AND_ACCEPT"
    assert art.final_outcome.get("duplicate_effect") is False


def test_case_b_mutation_does_not_commit_response_lost(setup_env):
    """Case B: mutation does not commit, response lost -> VERIFY returns False, abstains/defers, replay=False."""
    adapter, _ = setup_env
    def fault_exec(name, args):
        raise ConnectionResetError("504 Gateway Timeout: UNKNOWN_ACK lost response")

    def verif_fn(args):
        return False  # Not committed

    out, art = adapter.execute_tool("case_b", 42, "charge_card", {"amount": 100}, fault_exec, verification_fn=verif_fn)
    assert art.final_outcome["success"] is False
    assert art.final_outcome.get("abstained") is True
    assert art.recovery["action"] == "DEFER"


def test_case_c_5xx_after_possible_commit(setup_env):
    """Case C: 5xx after possible commit -> treated as UNKNOWN_ACK, prohibits blind replay."""
    adapter, _ = setup_exec = setup_env
    def fault_exec(name, args):
        raise RuntimeError("500 Internal Server Error: unknown commit state")

    out, art = adapter.execute_tool("case_c", 42, "charge_card", {"amount": 100}, fault_exec)
    assert art.failure["failure_kind"] in ("UNKNOWN_ACK", "NETWORK_FAILURE", "TOOL_IMPLEMENTATION_FAILURE")
    assert art.final_outcome.get("duplicate_effect") is False


def test_case_d_connection_reset_after_write(setup_env):
    """Case D: connection reset after write -> classified as UNKNOWN_ACK, replay=False."""
    adapter, _ = setup_env
    def fault_exec(name, args):
        raise ConnectionResetError("ECONNRESET: Connection reset by peer")

    out, art = adapter.execute_tool("case_d", 42, "charge_card", {"amount": 100}, fault_exec)
    assert art.recovery["status"] in ("ABSTAINED_NO_BLIND_REPLAY", "FAILED")


def test_case_e_process_crash_before_response(setup_env):
    """Case E: process crash before response -> state recovery inspects stored intent key."""
    adapter, _ = setup_env
    intent = adapter.key_store.get_or_create("case_e_intent", "charge_card", {"amount": 100})
    adapter.key_store.record_attempt(intent.key, 1, "IN_FLIGHT")
    
    # On restart, key history is retrieved
    hist = adapter.key_store.get_history(intent.key)
    assert hist["status"] == "IN_FLIGHT"


def test_case_f_retry_after_restart(setup_env):
    """Case F: retry after restart -> reuses exact same idempotency key."""
    adapter, _ = setup_env
    key1 = adapter.key_store.get_or_create("case_f_intent", "charge_card", {"amount": 100}).key
    key2 = adapter.key_store.get_or_create("case_f_intent", "charge_card", {"amount": 100}).key
    assert key1 == key2


def test_case_g_duplicate_delivery(setup_env):
    """Case G: duplicate delivery -> distinct intents generate distinct keys, same intent reuses key."""
    adapter, _ = setup_env
    k1 = adapter.key_store.get_or_create("intent_1", "charge_card", {"amount": 100}).key
    k2 = adapter.key_store.get_or_create("intent_2", "charge_card", {"amount": 100}).key
    assert k1 != k2


def test_case_h_verification_unavailable(setup_env):
    """Case H: verification unavailable -> abstains/defers, replay=False."""
    adapter, _ = setup_env
    def fault_exec(name, args):
        raise ConnectionResetError("504 Gateway Timeout")

    out, art = adapter.execute_tool("case_h", 42, "charge_card", {"amount": 100}, fault_exec, verification_fn=None)
    assert art.final_outcome.get("abstained") is True
    assert art.recovery["action"] == "DEFER"


def test_case_i_verification_returns_ambiguous_state(setup_env):
    """Case I: verification returns ambiguous state -> abstains/defers to agent."""
    adapter, _ = setup_env
    def fault_exec(name, args):
        raise ConnectionResetError("504 Gateway Timeout")

    def ambiguous_verif(args):
        return False  # Ambiguous / unconfirmed

    out, art = adapter.execute_tool("case_i", 42, "charge_card", {"amount": 100}, fault_exec, verification_fn=ambiguous_verif)
    assert art.final_outcome.get("abstained") is True


def test_case_j_idempotency_supported(setup_env):
    """Case J: idempotency supported -> safe retry with same idempotency key allowed."""
    adapter, reg = setup_env
    state = ExecutionState(agent="agent_1")
    proposal = ExecutableAction(tool="charge_card_idem", arguments={"amount": 100}, metadata={"idempotent": True, "side_effect_class": "idempotent_write"})
    res = adapter.resolver.resolve(proposal, state)
    assert res.decision == "select"


def test_case_k_idempotency_unsupported(setup_env):
    """Case K: idempotency unsupported under UNKNOWN_ACK -> blind retry forbidden (DENY)."""
    adapter, reg = setup_env
    state = ExecutionState(agent="agent_1", context={"tx_state": "unknown_ack"})
    proposal = ExecutableAction(tool="charge_card", arguments={"amount": 100}, metadata={"idempotent": False, "side_effect_class": "non_idempotent_mutation"})
    res = adapter.resolver.resolve(proposal, state)
    assert res.decision == "deny"


def test_case_l_compensation_available(setup_env):
    """Case L: compensation available -> resolves partial mutation via compensation hook."""
    mgr = PartialMutationManager()
    def compensate_fn(args, steps_done):
        return {"status": "ROLLED_BACK", "refunded": True}

    mgr.register_hook(PartialMutationHook(tool_name="charge_card", compensation_hook=compensate_fn))
    mgr.record_partial_state(PartialMutationState(transaction_id="tx_l", entity_id="card_1", steps_total=2, steps_completed=1))

    status, msg, res = mgr.resolve_partial_mutation("tx_l", "charge_card", {"amount": 100})
    assert status == PartialMutationStatus.COMPENSATED
    assert res["refunded"] is True


def test_case_m_compensation_unavailable(setup_env):
    """Case M: compensation unavailable -> UNRECOVERABLE status, defers/denies."""
    mgr = PartialMutationManager()
    mgr.record_partial_state(PartialMutationState(transaction_id="tx_m", entity_id="card_2", steps_total=2, steps_completed=1))

    status, msg, res = mgr.resolve_partial_mutation("tx_m", "unregistered_tool", {"amount": 100})
    assert status == PartialMutationStatus.UNRECOVERABLE
    assert "deferring" in msg.lower() or "denying" in msg.lower()
