"""Test suite for Milestone M1 Gate.

Verifies:
1. Stdio MCP client connects to 5 real servers (including 2 non-MCPAgentBench servers: sqlite and vault).
2. Successfully discovers tools via JSON-RPC tools/list and calls tools via tools/call.
3. OpenAPI importer ingests 2 real OpenAPI specs (Petstore and Checkout) and correctly infers contracts.
4. Exact NumPy Vector Store indexes and retrieves candidates with pure NumPy cosine operations.
"""

from pathlib import Path
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "python" / "src"))

from soro.adapters.stdio_mcp_client import StdioMCPClient
from soro.adapters.openapi_importer import OpenAPIImporter
from soro.routing.numpy_store import NumpyVectorStore
from soro.routing.scale import text_to_vector


def test_m1_stdio_mcp_five_real_servers():
    servers = [
        ("sqlite", REPO_ROOT / "examples" / "mcp_servers" / "sqlite_server.py"),
        ("vault", REPO_ROOT / "examples" / "mcp_servers" / "vault_server.py"),
        ("weather", REPO_ROOT / "examples" / "mcp_servers" / "weather_server.py"),
        ("currency", REPO_ROOT / "examples" / "mcp_servers" / "currency_server.py"),
        ("notify", REPO_ROOT / "examples" / "mcp_servers" / "notify_server.py"),
    ]

    total_discovered_tools = 0

    for s_name, s_script in servers:
        assert s_script.exists()
        cmd = [sys.executable, str(s_script)]
        client = StdioMCPClient(cmd, server_id=s_name)
        with client:
            tools = client.list_tools()
            assert len(tools) > 0, f"Server {s_name} exposed 0 tools"
            total_discovered_tools += len(tools)

            # Test real invocation on each
            if s_name == "sqlite":
                res = client.call_tool("sqlite_query", {"sql": "SELECT name FROM users WHERE id=1"})
                assert "Alice" in str(res)
            elif s_name == "vault":
                res_w = client.call_tool("vault_write_record", {"key": "token_abc", "content": "secret_val"})
                assert "Stored" in str(res_w)
                res_r = client.call_tool("vault_read_record", {"key": "token_abc"})
                assert "secret_val" in str(res_r)
            elif s_name == "weather":
                res = client.call_tool("get_current_weather", {"city": "Chicago"})
                assert "Chicago" in str(res)
            elif s_name == "currency":
                res = client.call_tool("convert_currency", {"amount": 100, "from_currency": "USD", "to_currency": "EUR"})
                assert "EUR" in str(res)
            elif s_name == "notify":
                res = client.call_tool("send_alert", {"channel": "alerts", "message": "disk_full"})
                assert "dispatched" in str(res)

    assert total_discovered_tools >= 7


def test_m1_openapi_importer_two_specs():
    petstore_path = REPO_ROOT / "examples" / "openapi" / "petstore.yaml"
    checkout_path = REPO_ROOT / "examples" / "openapi" / "checkout.yaml"

    spec_pet = OpenAPIImporter.load_spec(petstore_path)
    ops_pet = OpenAPIImporter.import_operations(spec_pet)
    assert len(ops_pet) == 4  # listPets (GET), createPet (POST), showPetById (GET), deletePet (DELETE)

    pet_get = next(op for op in ops_pet if op.operation_id == "listPets")
    assert pet_get.side_effect_class.value == "read_only"
    assert pet_get.is_idempotent is True

    pet_post = next(op for op in ops_pet if op.operation_id == "createPet")
    assert pet_post.side_effect_class.value == "non_idempotent_mutation"
    assert pet_post.is_idempotent is False
    assert "name" in pet_post.required_slots

    pet_del = next(op for op in ops_pet if op.operation_id == "deletePet")
    assert pet_del.side_effect_class.value == "idempotent_write"
    assert pet_del.is_idempotent is True

    spec_chk = OpenAPIImporter.load_spec(checkout_path)
    ops_chk = OpenAPIImporter.import_operations(spec_chk)
    assert len(ops_chk) == 3

    chk_charge = next(op for op in ops_chk if op.operation_id == "createCharge")
    assert chk_charge.has_idempotency_key_param is True
    assert chk_charge.is_idempotent is True  # Post with idempotency key recognized as idempotent mutation!


def test_m1_numpy_exact_vector_store():
    store = NumpyVectorStore()
    tools = [
        ("t_search", "Search public web and news articles for current events"),
        ("t_calc", "Calculate mathematical expression and arithmetic sum"),
        ("t_mail", "Send email message notification to user mailbox"),
    ]
    for tid, desc in tools:
        vec = text_to_vector(desc, num_dims=128)
        store.add(tid, vec, meta={"desc": desc})

    q_vec = text_to_vector("Do math addition and calculate sum", num_dims=128)
    hits = store.search(q_vec, top_k=2)

    assert len(hits) == 2
    assert hits[0].item_id == "t_calc"
    assert hits[0].score > hits[1].score
