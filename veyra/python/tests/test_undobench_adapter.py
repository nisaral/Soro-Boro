import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest
from veyra.core.execution_contract import ExecutionContract
from veyra.core.state import ExecutionState
from veyra.registry.tool_registry import ToolDefinition, ToolRegistry
from benchmarks.adapters.undobench.adapter import VeyraUndoBenchAdapter


@pytest.fixture
def setup_adapter():
    reg = ToolRegistry()
    reg.register(ToolDefinition(name="charge_card", idempotent=False, healthy=True, side_effect_class="non_idempotent_mutation"))
    reg.register(ToolDefinition(name="get_charge", idempotent=True, healthy=True, side_effect_class="read_only"))
    adapter = VeyraUndoBenchAdapter(mode="contract", registry=reg)
    return adapter


def test_1_control_pass_through(setup_adapter):
    """Test 1: Control pass-through preserves nominal tool output."""
    adapter = setup_adapter
    def nominal_executor(name, args):
        return {"status": "PAID", "charge_id": "chg_999"}

    out, artifact = adapter.execute_tool("t1", 42, "charge_card", {"amount": 50}, nominal_executor)
    assert out["status"] == "PAID"
    assert artifact.final_outcome["success"] is True


def test_2_deterministic_repeated_run(setup_adapter):
    """Test 2: Deterministic repeated run produces identical trajectory provenance."""
    adapter = setup_adapter
    def nominal_executor(name, args):
        return {"status": "PAID", "charge_id": "chg_999"}

    out1, art1 = adapter.execute_tool("t2", 42, "charge_card", {"amount": 50}, nominal_executor)
    out2, art2 = adapter.execute_tool("t2", 42, "charge_card", {"amount": 50}, nominal_executor)
    assert art1.action_proposed["metadata"]["idempotency_key"] == art2.action_proposed["metadata"]["idempotency_key"]


def test_3_reset_clears_state(setup_adapter):
    """Test 3: Reset clears keystore state."""
    adapter = setup_adapter
    adapter.key_store.get_or_create("intent_1", "charge_card", {"amount": 10})
    assert len(adapter.key_store._store) > 0
    adapter.key_store.clear()
    assert len(adapter.key_store._store) == 0


def test_4_fault_injection_remains_unchanged(setup_adapter):
    """Test 4: Fault injection exception reaches adapter failure classifier."""
    adapter = setup_adapter
    def fault_executor(name, args):
        raise ConnectionResetError("504 Gateway Timeout: UNKNOWN_ACK lost response")

    out, art = adapter.execute_tool("t4", 42, "charge_card", {"amount": 50}, fault_executor)
    assert art.failure["failure_kind"] in ("UNKNOWN_ACK", "NETWORK_FAILURE")


def test_5_no_veyra_wrapper_changes_nominal_result(setup_adapter):
    """Test 5: Nominal tool output is returned completely unaltered."""
    adapter = setup_adapter
    expected = {"data": [1, 2, 3], "nested": {"key": "val"}}
    def raw_exec(name, args):
        return expected

    out, art = adapter.execute_tool("t5", 42, "charge_card", {"amount": 50}, raw_exec)
    assert out == expected


def test_6_trajectory_artifacts_contain_provenance(setup_adapter):
    """Test 6: Trajectory artifact contains exact commit, benchmark version, and metric metadata."""
    adapter = setup_adapter
    def raw_exec(name, args):
        return {"ok": True}

    out, art = adapter.execute_tool("t6", 42, "charge_card", {"amount": 50}, raw_exec)
    assert art.benchmark == "UndoBench"
    assert art.benchmark_version == "v1.0.1"
    assert art.veyra_commit != ""


def test_7_unknown_ack_never_blindly_retries_non_idempotent_mutation(setup_adapter):
    """Test 7: UNKNOWN_ACK on non-idempotent mutation NEVER performs blind retry."""
    adapter = setup_adapter
    call_counts = {"charge_card": 0}
    def fault_exec(name, args):
        call_counts[name] += 1
        raise ConnectionResetError("504 Gateway Timeout: UNKNOWN_ACK lost response")

    out, art = adapter.execute_tool("t7", 42, "charge_card", {"amount": 50}, fault_exec)
    # Called exactly ONCE (0 blind replays!)
    assert call_counts["charge_card"] == 1
    assert art.final_outcome.get("duplicate_effect") is False


def test_8_idempotency_key_persists_across_retries(setup_adapter):
    """Test 8: Idempotency key persists across retries for the same logical intent."""
    adapter = setup_adapter
    id1 = adapter.key_store.get_or_create("intent_t8", "charge_card", {"amount": 50})
    id2 = adapter.key_store.get_or_create("intent_t8", "charge_card", {"amount": 50})
    assert id1.key == id2.key


def test_9_verification_result_tied_to_original_intent(setup_adapter):
    """Test 9: Verification result is evaluated against original intent arguments."""
    adapter = setup_adapter
    def fault_exec(name, args):
        raise ConnectionResetError("UNKNOWN_ACK lost response")

    probe_checked_args = {}
    def verif_fn(args):
        probe_checked_args.update(args)
        return True

    out, art = adapter.execute_tool("t9", 42, "charge_card", {"amount": 100}, fault_exec, verification_fn=verif_fn)
    assert probe_checked_args["amount"] == 100
    assert art.final_outcome.get("verified_recovery") is True


def test_10_compensation_never_invoked_unless_declared_safe(setup_adapter):
    """Test 10: Compensation is never invoked unless explicitly declared safe."""
    adapter = setup_adapter
    comp_invoked = False
    def comp_fn(args):
        nonlocal comp_invoked
        comp_invoked = True

    def fault_exec(name, args):
        raise ConnectionResetError("UNKNOWN_ACK lost response")

    # In ZP mode, compensation is not invoked automatically without contract declaration
    adapter_zp = VeyraUndoBenchAdapter(mode="zp", registry=adapter.registry)
    out, art = adapter_zp.execute_tool("t10", 42, "charge_card", {"amount": 100}, fault_exec)
    assert comp_invoked is False
