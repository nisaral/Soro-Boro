"""Real MCP Benchmark Scenarios.

Defines realistic agent tool calling tasks across the 3 real MCP environments:
1. Filesystem
2. Database
3. API Services

Categorized by real developer failure modes:
- clean executions
- schema argument coercions (int string, string trimming)
- unrecoverable schema errors (missing required args, empty values)
- precondition errors (missing DB, unknown endpoint, city not in DB)
- transient 503 network timeouts (idempotent read vs non-idempotent write)
- rate limits (429 with backoff)
- authorization errors (unauthorized, missing secret creds)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RealMCPTask:
    task_id: str
    catalog: str
    tool_name: str
    instruction: str
    arguments: dict[str, Any]
    is_idempotent: bool
    is_retryable: bool
    injected_transient: bool = False  # If true, tool fails once with transient 503 then succeeds
    injected_rate_limit: bool = False  # If true, tool fails once with 429 then succeeds
    injected_network_timeout: bool = False  # Non-idempotent timeout (fails repeatedly)
    eligible_for_boundary_recovery: bool = False
    expected_failure_kind: str | None = None


def get_real_mcp_scenarios() -> list[RealMCPTask]:
    """Return a comprehensive suite of 40 real MCP operational tasks."""
    scenarios: list[RealMCPTask] = []

    # -------------------------------------------------------------
    # Category 1: Clean Tasks (10 tasks - succeed on first call)
    # -------------------------------------------------------------
    scenarios.extend([
        RealMCPTask(
            task_id="clean_fs_search",
            catalog="filesystem",
            tool_name="search_and_read_files",
            instruction="Search research docs for topic",
            arguments={"path": "/research/document"},
            is_idempotent=True,
            is_retryable=True,
        ),
        RealMCPTask(
            task_id="clean_fs_patch",
            catalog="filesystem",
            tool_name="patch_file",
            instruction="Apply code patch to target file",
            arguments={"path": "/src/main.py", "changes_path": "/patches/diff.patch"},
            is_idempotent=False,
            is_retryable=False,
        ),
        RealMCPTask(
            task_id="clean_db_reviews",
            catalog="database",
            tool_name="connect_database",
            instruction="Connect to movie reviews database",
            arguments={"database_name": "movie_reviews_db"},
            is_idempotent=True,
            is_retryable=True,
        ),
        RealMCPTask(
            task_id="clean_db_learning",
            catalog="database",
            tool_name="connect_database",
            instruction="Connect to online learning database",
            arguments={"database_name": "online_learning_db"},
            is_idempotent=True,
            is_retryable=True,
        ),
        RealMCPTask(
            task_id="clean_db_sql_dev",
            catalog="database",
            tool_name="Connect_SQL_Server",
            instruction="Connect to local development SQL Server",
            arguments={"connectionString": 1},
            is_idempotent=True,
            is_retryable=True,
        ),
        RealMCPTask(
            task_id="clean_db_sql_prod",
            catalog="database",
            tool_name="Connect_SQL_Server",
            instruction="Connect to Amazon RDS Production SQL Server",
            arguments={"connectionString": 2},
            is_idempotent=True,
            is_retryable=True,
        ),
        RealMCPTask(
            task_id="clean_api_earthquake",
            catalog="api",
            tool_name="make_api_request",
            instruction="Query earthquake data in San Francisco",
            arguments={
                "apiName": "city_earthquake_data_api",
                "url": "https://api.earthquake.example.com/earthquakes",
                "endpoint": "/earthquakes",
            },
            is_idempotent=True,
            is_retryable=True,
        ),
        RealMCPTask(
            task_id="clean_api_ecommerce",
            catalog="api",
            tool_name="make_api_request",
            instruction="Query store products from e-commerce API",
            arguments={
                "apiName": "ecommerce_api",
                "url": "https://api.ecommerce.example.com/products",
                "endpoint": "/products",
            },
            is_idempotent=True,
            is_retryable=True,
        ),
        RealMCPTask(
            task_id="clean_weather_london",
            catalog="api",
            tool_name="weather_data_retriever",
            instruction="Retrieve March 2020 weather in London",
            arguments={
                "start_date": "03/01",
                "end_date": "03/10",
                "range": "2020-2020",
                "location": "London",
            },
            is_idempotent=True,
            is_retryable=True,
        ),
        RealMCPTask(
            task_id="clean_weather_range",
            catalog="api",
            tool_name="weather_data_retriever",
            instruction="Retrieve multi-year London weather trends",
            arguments={
                "start_date": "03/05",
                "end_date": "03/12",
                "range": "2019-2022",
                "location": "London",
            },
            is_idempotent=True,
            is_retryable=True,
        ),
    ])

    # -------------------------------------------------------------
    # Category 2: Safe Schema Normalization (8 tasks - eligible for boundary recovery)
    # -------------------------------------------------------------
    # Connect_SQL_Server integer parameter passed as string "1" or "2" or "3"
    for i, profile_id in enumerate([1, 2, 3]):
        scenarios.append(
            RealMCPTask(
                task_id=f"schema_sql_int_str_{i}",
                catalog="database",
                tool_name="Connect_SQL_Server",
                instruction="Connect to SQL server passing string ID due to connectionString param name",
                arguments={"connectionString": str(profile_id)},  # String instead of int
                is_idempotent=True,
                is_retryable=True,
                eligible_for_boundary_recovery=True,
            )
        )

    # Whitespace padding in directory and DB parameters (e.g. from template formatting)
    scenarios.extend([
        RealMCPTask(
            task_id="schema_fs_whitespace_path",
            catalog="filesystem",
            tool_name="search_and_read_files",
            instruction="Search directory with extra spaces around path",
            arguments={"path": "  /research/document  "},
            is_idempotent=True,
            is_retryable=True,
            eligible_for_boundary_recovery=True,
        ),
        RealMCPTask(
            task_id="schema_db_whitespace_name",
            catalog="database",
            tool_name="connect_database",
            instruction="Connect to database with leading spaces in database_name",
            arguments={"database_name": "  movie_reviews_db  "},
            is_idempotent=True,
            is_retryable=True,
            eligible_for_boundary_recovery=True,
        ),
        RealMCPTask(
            task_id="schema_api_name_uppercase",
            catalog="api",
            tool_name="make_api_request",
            instruction="Query earthquake API with uppercase name",
            arguments={
                "apiName": "CITY_EARTHQUAKE_DATA_API",
                "url": "https://api.earthquake.example.com/earthquakes",
                "endpoint": "/earthquakes",
            },
            is_idempotent=True,
            is_retryable=True,
            eligible_for_boundary_recovery=True,
        ),
        RealMCPTask(
            task_id="schema_sql_str_3",
            catalog="database",
            tool_name="Connect_SQL_Server",
            instruction="Connect to staging SQL Server with string ID '3'",
            arguments={"connectionString": "3"},
            is_idempotent=True,
            is_retryable=True,
            eligible_for_boundary_recovery=True,
        ),
        RealMCPTask(
            task_id="schema_fs_whitespace_patch",
            catalog="filesystem",
            tool_name="patch_file",
            instruction="Patch file with surrounding whitespace in paths",
            arguments={"path": "  /src/main.py  ", "changes_path": "  /patches/diff.patch  "},
            is_idempotent=False,
            is_retryable=False,
            eligible_for_boundary_recovery=True,
        ),
    ])

    # -------------------------------------------------------------
    # Category 3: Idempotent Transient Timeouts & Rate Limits (8 tasks - eligible for boundary recovery)
    # -------------------------------------------------------------
    for i in range(4):
        scenarios.append(
            RealMCPTask(
                task_id=f"transient_weather_timeout_{i}",
                catalog="api",
                tool_name="weather_data_retriever",
                instruction="Weather service encounters transient upstream 503",
                arguments={
                    "start_date": "03/01",
                    "end_date": "03/05",
                    "range": "2021-2021",
                    "location": "London",
                },
                is_idempotent=True,
                is_retryable=True,
                injected_transient=True,
                eligible_for_boundary_recovery=True,
            )
        )

    for i in range(4):
        scenarios.append(
            RealMCPTask(
                task_id=f"rate_limit_earthquake_{i}",
                catalog="api",
                tool_name="make_api_request",
                instruction="Earthquake API returns 429 Too Many Requests once before succeeding",
                arguments={
                    "apiName": "city_earthquake_data_api",
                    "url": "https://api.earthquake.example.com/earthquakes",
                    "endpoint": "/earthquakes",
                },
                is_idempotent=True,
                is_retryable=True,
                injected_rate_limit=True,
                eligible_for_boundary_recovery=True,
            )
        )

    # -------------------------------------------------------------
    # Category 4: Unsafe Non-Idempotent Timeouts (4 tasks - NON-RECOVERABLE, unsafe to retry!)
    # -------------------------------------------------------------
    for i in range(4):
        scenarios.append(
            RealMCPTask(
                task_id=f"unsafe_patch_timeout_{i}",
                catalog="filesystem",
                tool_name="patch_file",
                instruction="File patch write operation times out with unconfirmed write state",
                arguments={"path": f"/src/app_{i}.py", "changes_path": "/patches/critical.patch"},
                is_idempotent=False,
                is_retryable=False,
                injected_network_timeout=True,
                eligible_for_boundary_recovery=False,
                expected_failure_kind="unknown_state",
            )
        )

    # -------------------------------------------------------------
    # Category 5: Precondition Failures (6 tasks - NON-RECOVERABLE, requires agent re-plan)
    # -------------------------------------------------------------
    scenarios.extend([
        RealMCPTask(
            task_id="precondition_db_not_found_1",
            catalog="database",
            tool_name="connect_database",
            instruction="Connect to non-existent customer database",
            arguments={"database_name": "non_existent_customers_db"},
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="precondition_error",
        ),
        RealMCPTask(
            task_id="precondition_db_not_found_2",
            catalog="database",
            tool_name="connect_database",
            instruction="Connect to legacy analytics DB not in provider registry",
            arguments={"database_name": "legacy_analytics_db"},
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="precondition_error",
        ),
        RealMCPTask(
            task_id="precondition_sql_profile_missing",
            catalog="database",
            tool_name="Connect_SQL_Server",
            instruction="Connect to SQL server with non-existent profile ID 99",
            arguments={"connectionString": 99},
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="precondition_error",
        ),
        RealMCPTask(
            task_id="precondition_api_endpoint_invalid",
            catalog="api",
            tool_name="make_api_request",
            instruction="Query non-existent endpoint on e-commerce API",
            arguments={
                "apiName": "ecommerce_api",
                "url": "https://api.ecommerce.example.com/v2/analytics",
                "endpoint": "/v2/analytics",
            },
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="precondition_error",
        ),
        RealMCPTask(
            task_id="precondition_weather_city_missing",
            catalog="api",
            tool_name="weather_data_retriever",
            instruction="Query weather for city not in database (Atlantis)",
            arguments={
                "start_date": "03/01",
                "end_date": "03/10",
                "range": "2020-2020",
                "location": "Atlantis",
            },
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="precondition_error",
        ),
        RealMCPTask(
            task_id="precondition_weather_year_order",
            catalog="api",
            tool_name="weather_data_retriever",
            instruction="Query weather with inverted year range 2025-2020",
            arguments={
                "start_date": "03/01",
                "end_date": "03/10",
                "range": "2025-2020",
                "location": "London",
            },
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="precondition_error",
        ),
    ])

    # -------------------------------------------------------------
    # Category 6: Unrecoverable Schema Errors (4 tasks - NON-RECOVERABLE, requires agent re-plan)
    # -------------------------------------------------------------
    scenarios.extend([
        RealMCPTask(
            task_id="schema_fs_empty_path",
            catalog="filesystem",
            tool_name="search_and_read_files",
            instruction="Call search with empty directory path string",
            arguments={"path": ""},
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="schema_error",
        ),
        RealMCPTask(
            task_id="schema_fs_missing_changes_path",
            catalog="filesystem",
            tool_name="patch_file",
            instruction="Call patch_file missing changes_path argument",
            arguments={"path": "/src/main.py"},
            is_idempotent=False,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="schema_error",
        ),
        RealMCPTask(
            task_id="schema_api_empty_url",
            catalog="api",
            tool_name="make_api_request",
            instruction="Call make_api_request with empty url",
            arguments={"apiName": "ecommerce_api", "url": "", "endpoint": "/products"},
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="schema_error",
        ),
        RealMCPTask(
            task_id="schema_weather_bad_date_format",
            catalog="api",
            tool_name="weather_data_retriever",
            instruction="Call weather with invalid date format YYYY-MM-DD instead of MM/DD",
            arguments={
                "start_date": "2020-03-01",
                "end_date": "2020-03-10",
                "range": "2020-2020",
                "location": "London",
            },
            is_idempotent=True,
            is_retryable=False,
            eligible_for_boundary_recovery=False,
            expected_failure_kind="schema_error",
        ),
    ])

    return scenarios
