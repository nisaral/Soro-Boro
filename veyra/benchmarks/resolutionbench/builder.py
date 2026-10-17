"""ResolutionBench v0: Ground-Truth Dataset Builder (Phase 1 Specification).

Generates exactly 100 hand-crafted, ground-truth resolution cases across 5 categories:
A. exact equivalent tools (20 cases)
B. parameter aliases (20 cases)
C. schema-compatible transformations (20 cases)
D. primary-to-declared-fallback execution (20 cases)
E. compound cases combining failure + alias/schema mapping (20 cases)

Every case defines:
- intended capability
- proposed tool
- available tools with JSON schemas
- allowed equivalence relation
- allowed argument mappings
- failure condition on primary path
- expected valid resolution
- forbidden resolutions
- success oracle specification
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ResolutionCase:
    case_id: str
    category: str  # A, B, C, D, E
    category_name: str
    intended_capability: str
    instruction: str
    proposed_tool: str
    proposed_arguments: dict[str, Any]
    available_tools: list[dict[str, Any]]
    allowed_equivalence_relation: dict[str, Any]  # {"canonical": ..., "equivalents": [...]}
    allowed_argument_mappings: dict[str, str]  # {proposed_arg: canonical_arg}
    failure_condition: str  # tool_not_found, primary_503, schema_mismatch, rate_limit
    expected_valid_resolution: dict[str, Any]  # {"tool": ..., "arguments": ...}
    forbidden_resolutions: list[dict[str, Any]]
    is_side_effecting: bool = False
    mock_response: dict[str, Any] = field(default_factory=lambda: {"status": "success", "data": "ok"})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_all_100_cases() -> list[ResolutionCase]:
    cases: list[ResolutionCase] = []

    # =========================================================================
    # CATEGORY A: Exact Equivalent Tools (20 cases: A01 to A20)
    # The agent proposes a known alias/synonym or legacy tool name; Veyra resolves
    # it to the canonical equivalent capability. Competent middleware fails because
    # it only handles argument coercion on the exact proposed tool.
    # =========================================================================
    cat_a_specs = [
        ("customer_lookup", "fetch_customer", "get_customer", "customer_id", 1001, "crm"),
        ("order_status", "query_order", "get_order", "order_id", 2001, "commerce"),
        ("file_reading", "read_file_content", "read_file", "path", "/var/log/sys.log", "fs"),
        ("inventory_check", "check_stock", "get_inventory", "sku", "SKU-991", "inventory"),
        ("telemetry_query", "fetch_metrics", "get_telemetry", "metric_id", 501, "observability"),
        ("document_search", "search_papers", "search", "query", "agent boundary", "search"),
        ("user_profile", "view_user", "get_user", "user_id", 301, "identity"),
        ("invoice_fetch", "download_invoice", "get_invoice", "invoice_num", 401, "billing"),
        ("node_health", "ping_node", "check_health", "node_id", "node-alpha", "infra"),
        ("schedule_lookup", "list_events", "get_schedule", "calendar_id", "cal-01", "calendar"),
        ("weather_report", "get_weather", "weather_data_retriever", "city", "London", "weather"),
        ("token_balance", "query_balance", "get_balance", "account_id", 801, "fintech"),
        ("article_reader", "fetch_article", "read_article", "slug", "intro-ai", "cms"),
        ("repo_commits", "list_commits", "get_commit_history", "repo", "veyra-core", "git"),
        ("cluster_status", "inspect_cluster", "get_cluster_status", "cluster_id", "us-east-1", "cloud"),
        ("package_info", "query_package", "get_package_metadata", "pkg_name", "pydantic", "registry"),
        ("audit_log", "fetch_audit_records", "get_audit_log", "session_id", "sess-77", "security"),
        ("device_state", "query_device", "get_device_state", "device_id", "dev-881", "iot"),
        ("shipping_rate", "lookup_shipping", "get_shipping_rate", "postal_code", "98101", "logistics"),
        ("ticket_details", "view_ticket", "get_support_ticket", "ticket_id", 1099, "support"),
    ]

    for idx, (cap, prop_tool, canon_tool, arg_name, arg_val, domain) in enumerate(cat_a_specs, start=1):
        case_id = f"res_a_{idx:02d}"
        schema = {
            "name": canon_tool,
            "description": f"Canonical tool for {cap}",
            "parameters": {
                "type": "object",
                "properties": {arg_name: {"type": "string" if isinstance(arg_val, str) else "integer"}},
                "required": [arg_name],
            },
            "is_idempotent": True,
        }
        cases.append(
            ResolutionCase(
                case_id=case_id,
                category="A",
                category_name="exact_equivalent_tools",
                intended_capability=cap,
                instruction=f"Execute {cap} for {arg_name}={arg_val}",
                proposed_tool=prop_tool,
                proposed_arguments={arg_name: arg_val},
                available_tools=[schema],
                allowed_equivalence_relation={"canonical": canon_tool, "equivalents": [prop_tool, canon_tool]},
                allowed_argument_mappings={},
                failure_condition="tool_not_found",
                expected_valid_resolution={"tool": canon_tool, "arguments": {arg_name: arg_val}},
                forbidden_resolutions=[{"tool": f"delete_{canon_tool}"}, {"tool": f"update_{canon_tool}"}],
                is_side_effecting=False,
            )
        )

    # =========================================================================
    # CATEGORY B: Parameter Aliases (20 cases: B01 to B20)
    # The agent proposes the right tool, but uses an alias for an argument key
    # (e.g. account_id instead of id, or filename instead of path).
    # Veyra resolves parameter aliases without burning an agent reasoning turn.
    # =========================================================================
    cat_b_specs = [
        ("get_account", "account_id", "id", 1001, "integer"),
        ("read_file", "file_path", "path", "/data/records.csv", "string"),
        ("search_docs", "search_query", "query", "vector database", "string"),
        ("get_event", "event_identifier", "id", "evt-404", "string"),
        ("get_invoice", "invoice_number", "id", 9921, "integer"),
        ("get_user", "username", "id", "alice_w", "string"),
        ("get_device", "hardware_id", "id", "hw-091", "string"),
        ("get_telemetry", "metric_name", "metric", "cpu_usage", "string"),
        ("get_order", "order_number", "id", 5501, "integer"),
        ("get_ticket", "issue_id", "id", 1234, "integer"),
        ("get_repository", "repo_name", "name", "veyra", "string"),
        ("get_package", "pkg_id", "id", "fastapi", "string"),
        ("get_cluster", "cluster_name", "id", "prod-eu", "string"),
        ("get_transaction", "txn_id", "id", "tx-8812", "string"),
        ("get_session", "auth_token", "token", "tok_live_123", "string"),
        ("get_contact", "email_address", "email", "support@company.com", "string"),
        ("get_job", "task_id", "id", "job-99", "string"),
        ("get_log", "log_file", "path", "/var/log/app.log", "string"),
        ("get_product", "product_sku", "sku", "PROD-A1", "string"),
        ("get_sensor", "sensor_name", "id", "temp_sensor_2", "string"),
    ]

    for idx, (tool_name, prop_arg, canon_arg, arg_val, expected_type) in enumerate(cat_b_specs, start=1):
        case_id = f"res_b_{idx:02d}"
        schema = {
            "name": tool_name,
            "description": f"Tool {tool_name}",
            "parameters": {
                "type": "object",
                "properties": {canon_arg: {"type": expected_type}},
                "required": [canon_arg],
                "additionalProperties": False,
            },
            "is_idempotent": True,
        }
        cases.append(
            ResolutionCase(
                case_id=case_id,
                category="B",
                category_name="parameter_aliases",
                intended_capability=f"execute_{tool_name}",
                instruction=f"Call {tool_name} with {prop_arg}={arg_val}",
                proposed_tool=tool_name,
                proposed_arguments={prop_arg: arg_val},
                available_tools=[schema],
                allowed_equivalence_relation={"canonical": tool_name, "equivalents": [tool_name]},
                allowed_argument_mappings={prop_arg: canon_arg},
                failure_condition="missing_required_arg",
                expected_valid_resolution={"tool": tool_name, "arguments": {canon_arg: arg_val}},
                forbidden_resolutions=[{"tool": f"drop_{tool_name}"}],
                is_side_effecting=False,
            )
        )

    # =========================================================================
    # CATEGORY C: Schema-Compatible Transformations (20 cases: C01 to C20)
    # The agent provides values in a convertible format (string for int, string
    # boolean, JSON string for object, comma-separated string for list).
    # =========================================================================
    cat_c_specs = [
        ("get_metrics", "limit", " 50 ", 50, "integer"),
        ("filter_logs", "verbose", "true", True, "boolean"),
        ("filter_alerts", "active_only", "1", True, "boolean"),
        ("query_db", "timeout_sec", "30.0", 30, "integer"),
        ("parse_manifest", "config", '{"env": "prod"}', {"env": "prod"}, "object"),
        ("get_records", "page", " 3 ", 3, "integer"),
        ("lookup_zip", "zip_code", "98101", 98101, "integer"),
        ("check_status", "dry_run", "false", False, "boolean"),
        ("set_preference", "options", '{"dark_mode": true}', {"dark_mode": True}, "object"),
        ("get_batch", "batch_size", "100", 100, "integer"),
        ("fetch_depth", "depth", "5", 5, "integer"),
        ("toggle_feature", "enabled", "yes", True, "boolean"),
        ("inspect_payload", "headers", '{"X-Trace": "1"}', {"X-Trace": "1"}, "object"),
        ("query_range", "start_year", "2024", 2024, "integer"),
        ("lookup_port", "port_number", "8080", 8080, "integer"),
        ("check_flag", "force", "0", False, "boolean"),
        ("get_threshold", "max_retries", "4", 4, "integer"),
        ("query_epoch", "timestamp_sec", "1700000000", 1700000000, "integer"),
        ("system_audit", "deep_scan", "True", True, "boolean"),
        ("lookup_sku_id", "numeric_id", "4096", 4096, "integer"),
    ]

    for idx, (tool_name, arg_name, raw_val, coerced_val, expected_type) in enumerate(cat_c_specs, start=1):
        case_id = f"res_c_{idx:02d}"
        schema = {
            "name": tool_name,
            "description": f"Tool {tool_name}",
            "parameters": {
                "type": "object",
                "properties": {arg_name: {"type": expected_type}},
                "required": [arg_name],
            },
            "is_idempotent": True,
        }
        cases.append(
            ResolutionCase(
                case_id=case_id,
                category="C",
                category_name="schema_compatible_transformations",
                intended_capability=f"normalize_{tool_name}",
                instruction=f"Call {tool_name} with {arg_name}={raw_val}",
                proposed_tool=tool_name,
                proposed_arguments={arg_name: raw_val},
                available_tools=[schema],
                allowed_equivalence_relation={"canonical": tool_name, "equivalents": [tool_name]},
                allowed_argument_mappings={},
                failure_condition="invalid_argument_type",
                expected_valid_resolution={"tool": tool_name, "arguments": {arg_name: coerced_val}},
                forbidden_resolutions=[],
                is_side_effecting=False,
            )
        )

    # =========================================================================
    # CATEGORY D: Primary-to-Declared-Fallback Execution (20 cases: D01 to D20)
    # The primary service is declared, but fails with a transient 503 or 429;
    # Veyra resolves execution by falling back to the declared secondary replica
    # or fallback tool without losing continuity or agent context.
    # =========================================================================
    cat_d_specs = [
        ("read_db", "query_primary_db", "query_replica_db", "sql", "SELECT 1"),
        ("weather", "live_weather_service", "cached_weather_service", "location", "London"),
        ("search", "web_search_primary", "web_search_backup", "q", "LLM tool boundary"),
        ("rates", "ecb_exchange_rates", "fed_exchange_rates", "pair", "EUR/USD"),
        ("geo", "google_geocoding", "osm_geocoding", "address", "1600 Amphitheatre"),
        ("translate", "deepl_translator", "google_translator", "text", "Bonjour"),
        ("dns", "primary_dns_lookup", "secondary_dns_lookup", "domain", "example.com"),
        ("telemetry", "prometheus_query", "victoriametrics_query", "expr", "up == 1"),
        ("market", "bloomberg_quote", "reuters_quote", "ticker", "AAPL"),
        ("ocr", "cloud_ocr_service", "tesseract_fallback", "image_id", "img_001"),
        ("sentiment", "frontier_sentiment", "distilbert_sentiment", "text", "Great product!"),
        ("routing", "here_route_calculator", "osrm_route_calculator", "destination", "Paris"),
        ("time", "ntp_primary_pool", "ntp_secondary_pool", "host", "time.nist.gov"),
        ("status", "aws_health_dashboard", "statuspage_backup", "service", "ec2"),
        ("inventory", "warehouse_db_primary", "warehouse_cache_replica", "item_id", "item-99"),
        ("papers", "arxiv_api_primary", "semanticscholar_backup", "arxiv_id", "2604.01508"),
        ("registry", "npm_registry_primary", "npm_mirror_backup", "package", "lodash"),
        ("ledger", "stripe_balance_check", "mock_balance_snapshot", "account", "acct_88"),
        ("doc", "confluence_api_primary", "offline_markdown_cache", "doc_id", "doc-11"),
        ("auth", "okta_verify_session", "local_jwt_validator", "session_token", "jwt.token.abc"),
    ]

    for idx, (cap, prim_tool, fb_tool, arg_name, arg_val) in enumerate(cat_d_specs, start=1):
        case_id = f"res_d_{idx:02d}"
        prim_schema = {
            "name": prim_tool,
            "parameters": {"type": "object", "properties": {arg_name: {"type": "string"}}, "required": [arg_name]},
            "is_idempotent": True,
        }
        fb_schema = {
            "name": fb_tool,
            "parameters": {"type": "object", "properties": {arg_name: {"type": "string"}}, "required": [arg_name]},
            "is_idempotent": True,
        }
        cases.append(
            ResolutionCase(
                case_id=case_id,
                category="D",
                category_name="primary_to_declared_fallback_execution",
                intended_capability=cap,
                instruction=f"Execute {cap} using {prim_tool} with {arg_name}={arg_val}",
                proposed_tool=prim_tool,
                proposed_arguments={arg_name: arg_val},
                available_tools=[prim_schema, fb_schema],
                allowed_equivalence_relation={"canonical": prim_tool, "equivalents": [prim_tool, fb_tool]},
                allowed_argument_mappings={},
                failure_condition="primary_503_transient",
                expected_valid_resolution={"tool": fb_tool, "arguments": {arg_name: arg_val}},
                forbidden_resolutions=[{"tool": "force_reboot_system"}],
                is_side_effecting=False,
            )
        )

    # =========================================================================
    # CATEGORY E: Compound Cases (Failure + Alias + Schema Mapping) (20 cases: E01 to E20)
    # The agent proposes an alias tool with a string integer or aliased argument;
    # the primary tool fails, requiring simultaneous alias resolution, schema repair,
    # and fallback execution.
    # =========================================================================
    cat_e_specs = [
        ("account_read", "query_acct", "get_account", "crm_account_read", "acct_id", "id", " 101 ", 101),
        ("file_fetch", "download_doc", "read_file", "fs_read_replica", "file_name", "path", "/tmp/report.pdf", "/tmp/report.pdf"),
        ("metric_poll", "poll_metric", "get_metric", "replica_metrics", "metric_code", "id", " 90 ", 90),
        ("order_view", "inspect_order", "get_order", "order_archive", "order_no", "id", "5500", 5500),
        ("stock_lookup", "check_inventory", "get_stock", "cached_inventory", "item_sku", "sku", "SKU-88", "SKU-88"),
        ("invoice_view", "fetch_invoice_data", "get_invoice", "billing_archive", "inv_id", "id", "404", 404),
        ("user_lookup", "find_user_record", "get_user", "replica_user_db", "user_num", "id", " 77 ", 77),
        ("calendar_event", "view_event", "get_event", "cached_calendar", "event_num", "id", "301", 301),
        ("device_poll", "read_device", "get_device", "device_cache", "dev_num", "id", " 12 ", 12),
        ("ticket_poll", "fetch_ticket", "get_ticket", "support_mirror", "issue_num", "id", "808", 808),
        ("shipping_quote", "calc_shipping", "get_shipping", "rate_fallback", "zip", "postal_code", "98101", "98101"),
        ("cluster_poll", "poll_cluster", "get_cluster", "cluster_monitor_backup", "cluster_num", "id", " 2 ", 2),
        ("paper_fetch", "query_arxiv", "get_paper", "semanticscholar_mirror", "paper_id", "id", "2604", 2604),
        ("session_check", "inspect_session", "get_session", "session_cache", "sess_id", "id", "990", 990),
        ("audit_fetch", "query_audit", "get_audit", "audit_replica", "record_id", "id", " 450 ", 450),
        ("job_status", "check_task", "get_job", "job_tracker_fallback", "job_num", "id", "1024", 1024),
        ("port_scan", "query_port", "get_port", "local_port_cache", "port_str", "port", " 80 ", 80),
        ("catalog_lookup", "search_catalog", "get_catalog", "catalog_replica", "catalog_no", "id", " 7 ", 7),
        ("profile_fetch", "query_profile", "get_profile", "profile_mirror", "profile_num", "id", "882", 882),
        ("sensor_read", "read_sensor", "get_sensor", "sensor_buffer", "sensor_no", "id", " 42 ", 42),
    ]

    for idx, (cap, prop_tool, canon_tool, fallback_tool, prop_arg, canon_arg, raw_val, final_val) in enumerate(cat_e_specs, start=1):
        case_id = f"res_e_{idx:02d}"
        val_type = "integer" if isinstance(final_val, int) else "string"
        canon_schema = {
            "name": canon_tool,
            "parameters": {"type": "object", "properties": {canon_arg: {"type": val_type}}, "required": [canon_arg]},
            "is_idempotent": True,
        }
        fb_schema = {
            "name": fallback_tool,
            "parameters": {"type": "object", "properties": {canon_arg: {"type": val_type}}, "required": [canon_arg]},
            "is_idempotent": True,
        }
        cases.append(
            ResolutionCase(
                case_id=case_id,
                category="E",
                category_name="compound_failure_plus_alias_and_schema",
                intended_capability=cap,
                instruction=f"Execute {cap} with {prop_tool}({prop_arg}={raw_val})",
                proposed_tool=prop_tool,
                proposed_arguments={prop_arg: raw_val},
                available_tools=[canon_schema, fb_schema],
                allowed_equivalence_relation={"canonical": canon_tool, "equivalents": [prop_tool, canon_tool, fallback_tool]},
                allowed_argument_mappings={prop_arg: canon_arg},
                failure_condition="primary_fails_requires_alias_and_schema_coercion",
                expected_valid_resolution={"tool": fallback_tool, "arguments": {canon_arg: final_val}},
                forbidden_resolutions=[{"tool": "emergency_shutdown"}],
                is_side_effecting=False,
            )
        )

    return cases


def main():
    cases = build_all_100_cases()
    out_dir = Path("benchmarks/resolutionbench")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "cases.json"

    data = {
        "benchmark": "ResolutionBench",
        "version": "v0.1-groundtruth",
        "total_cases": len(cases),
        "category_counts": {
            "A_exact_equivalent_tools": sum(1 for c in cases if c.category == "A"),
            "B_parameter_aliases": sum(1 for c in cases if c.category == "B"),
            "C_schema_compatible_transformations": sum(1 for c in cases if c.category == "C"),
            "D_primary_to_declared_fallback_execution": sum(1 for c in cases if c.category == "D"),
            "E_compound_failure_plus_alias_and_schema": sum(1 for c in cases if c.category == "E"),
        },
        "cases": [c.to_dict() for c in cases],
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Generated {len(cases)} ResolutionBench ground-truth cases.")
    print(f"Saved to: {out_file}")
    for cat, count in data["category_counts"].items():
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
