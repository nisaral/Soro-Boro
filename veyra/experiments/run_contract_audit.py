"""Independent Contract Inference Audit.

Evaluates how often standard verb-based contract inference heuristics match
ground-truth execution semantics across 100 real operations from the public benchmark.

Categorizes errors into:
- Safe-Direction: Inferred class is more restrictive than ground truth (e.g. inferred mutation when truth is idempotent write or pure calculation).
- Unsafe-Direction: Inferred class is less restrictive than ground truth (e.g. inferred read_only when truth is mutation).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List


# Hand-labeled Ground Truth following frozen guidelines (contract_audit_guidelines.md)
GROUND_TRUTH_LABELS = {
    "read_file": ("read_only", "Reads and returns file contents without modification"),
    "write_file": ("idempotent_write", "Overwrites file content; repeated execution with same content leaves identical file state"),
    "append_file": ("non_idempotent_mutation", "Appends content to file; repeated execution appends multiple times"),
    "copy_file": ("idempotent_write", "Copies file to destination; repeated execution overwrites destination with identical content"),
    "move_file": ("non_idempotent_mutation", "Moves/renames file; second call fails or alters repository structure non-idempotently"),
    "delete_file": ("idempotent_write", "Deletes file; repeated execution leaves target file absent"),
    "list_directory": ("read_only", "Lists directory contents"),
    "get_file_metadata": ("read_only", "Retrieves file metadata"),
    "extract_pdf_text": ("read_only", "Pure text extraction from document"),
    "extract_docx_text": ("read_only", "Pure text extraction from document"),
    "summarize_document": ("read_only", "Analysis and summary generation"),
    "search_document": ("read_only", "Search within document contents"),
    "extract_document_section": ("read_only", "Section retrieval"),
    "execute_sql_query": ("read_only", "Explicitly defined as read-only SQL query"),
    "inspect_database_schema": ("read_only", "Schema metadata inspection"),
    "insert_database_record": ("non_idempotent_mutation", "Inserts new row with generated primary key; repeated execution creates duplicate rows"),
    "update_database_record": ("idempotent_write", "Updates database columns to target values based on condition; idempotent given same target values"),
    "delete_database_record": ("idempotent_write", "Deletes records matching condition; target state is records absent"),
    "aggregate_database_data": ("read_only", "Computes aggregations (counts, sums) without modifying table data"),
    "fetch_web_page": ("read_only", "HTTP GET retrieval"),
    "extract_web_text": ("read_only", "Text extraction from HTML"),
    "extract_web_links": ("read_only", "Hyperlink extraction from HTML"),
    "extract_web_metadata": ("read_only", "Metadata parsing from HTML"),
    "extract_structured_web_data": ("read_only", "Structured field extraction"),
    "search_web": ("read_only", "Web corpus search query"),
    "search_research_papers": ("read_only", "Academic paper search"),
    "get_paper_metadata": ("read_only", "Paper metadata lookup"),
    "get_paper_citations": ("read_only", "Citations lookup"),
    "summarize_research_paper": ("read_only", "Paper summary generation"),
    "compare_research_papers": ("read_only", "Comparison between papers"),
    "send_email": ("non_idempotent_mutation", "Sends outbound message; repeated execution sends duplicate messages to recipient"),
    "search_email": ("read_only", "Email search query"),
    "read_email": ("read_only", "Email content retrieval"),
    "reply_email": ("non_idempotent_mutation", "Sends outbound thread reply; repeated execution posts duplicate replies"),
    "create_email_draft": ("non_idempotent_mutation", "Creates new draft entity; repeated execution creates duplicate drafts"),
    "archive_email": ("idempotent_write", "Moves email to archived folder; repeated execution leaves email archived"),
    "create_calendar_event": ("non_idempotent_mutation", "Creates new calendar entry; repeated execution creates duplicate calendar entries"),
    "search_calendar_events": ("read_only", "Calendar search query"),
    "update_calendar_event": ("idempotent_write", "Updates event fields to target values; idempotent given same values"),
    "delete_calendar_event": ("idempotent_write", "Deletes event; repeated execution leaves event absent"),
    "check_calendar_availability": ("read_only", "Checks time slot availability"),
    "send_channel_message": ("non_idempotent_mutation", "Posts chat message; repeated execution posts duplicate messages"),
    "search_messages": ("read_only", "Message search query"),
    "reply_to_thread": ("non_idempotent_mutation", "Posts thread reply; repeated execution posts duplicate replies"),
    "list_channels": ("read_only", "Channel listing"),
    "get_channel_history": ("read_only", "Channel message history lookup"),
    "get_git_status": ("read_only", "Git working-tree status inspection"),
    "get_git_diff": ("read_only", "Git diff inspection"),
    "get_commit_history": ("read_only", "Git commit history inspection"),
    "list_git_branches": ("read_only", "Branch listing"),
    "create_git_branch": ("non_idempotent_mutation", "Creates new branch ref; fails if branch exists, alters repo ref state"),
    "create_git_commit": ("non_idempotent_mutation", "Creates new commit SHA; repeated execution creates duplicate commits with new timestamps"),
    "search_issues": ("read_only", "Issue search query"),
    "read_issue": ("read_only", "Issue details inspection"),
    "create_issue": ("non_idempotent_mutation", "Creates new issue ticket; repeated execution creates duplicate tickets"),
    "update_issue": ("idempotent_write", "Modifies issue fields/state to target values; idempotent"),
    "comment_on_issue": ("non_idempotent_mutation", "Adds comment to issue; repeated execution adds duplicate comments"),
    "summarize_text": ("read_only", "Pure text analysis transform"),
    "translate_text": ("read_only", "Pure text translation transform"),
    "analyze_sentiment": ("read_only", "Pure sentiment analysis"),
    "extract_keywords": ("read_only", "Pure keyword extraction"),
    "extract_entities": ("read_only", "Pure entity extraction"),
    "rewrite_text": ("read_only", "Pure text transformation"),
    "classify_text": ("read_only", "Pure text classification"),
    "calculate_expression": ("read_only", "Mathematical arithmetic computation"),
    "calculate_descriptive_statistics": ("read_only", "Statistical computation"),
    "calculate_percentage_change": ("read_only", "Mathematical computation"),
    "calculate_compound_interest": ("read_only", "Financial mathematical computation"),
    "solve_linear_equation": ("read_only", "Algebraic equation solver"),
    "inspect_dataset": ("read_only", "Dataset inspection"),
    "filter_dataset": ("read_only", "In-memory dataset filtering"),
    "sort_dataset": ("read_only", "In-memory dataset sorting"),
    "group_dataset": ("read_only", "In-memory dataset grouping"),
    "create_calculated_column": ("read_only", "In-memory derived column computation"),
    "analyze_missing_values": ("read_only", "Dataset missing-value analysis"),
    "parse_json": ("read_only", "In-memory JSON deserialization"),
    "query_json": ("read_only", "In-memory JSON querying"),
    "validate_json_schema": ("read_only", "In-memory JSON schema validation"),
    "transform_json": ("read_only", "In-memory JSON structure transformation"),
    "compare_json": ("read_only", "In-memory JSON diff comparison"),
    "get_system_info": ("read_only", "System info query"),
    "get_disk_usage": ("read_only", "Disk usage inspection"),
    "get_memory_usage": ("read_only", "Memory usage inspection"),
    "list_processes": ("read_only", "Process listing"),
    "read_environment_variable": ("read_only", "Environment variable query"),
    "geocode_location": ("read_only", "Geocoding lookup"),
    "reverse_geocode": ("read_only", "Reverse geocoding lookup"),
    "calculate_geographic_distance": ("read_only", "Geographic distance calculation"),
    "lookup_timezone": ("read_only", "Timezone lookup"),
    "lookup_country_information": ("read_only", "Country information lookup"),
    "get_image_metadata": ("read_only", "Image metadata query"),
    "resize_image": ("read_only", "In-memory image resize transform"),
    "crop_image": ("read_only", "In-memory image crop transform"),
    "convert_image_format": ("read_only", "In-memory image format conversion"),
    "describe_image": ("read_only", "Vision object description"),
    "calculate_date_difference": ("read_only", "Date arithmetic computation"),
    "add_date_duration": ("read_only", "Date arithmetic computation"),
    "generate_uuid": ("read_only", "Pure UUID string generator"),
    "hash_text": ("read_only", "Cryptographic hash computation"),
    "encode_base64": ("read_only", "Base64 encoding transform"),
}


def naive_verb_heuristic(tool_id: str) -> str:
    """Standard naive REST/CRUD verb prefix heuristic.
    
    Common heuristic pattern used in OpenAPI/MCP routers:
    - 'get', 'read', 'list', 'search', 'inspect', 'fetch', 'extract', 'lookup' -> read_only
    - 'delete', 'archive' -> idempotent_write
    - 'create', 'insert', 'add', 'post', 'send', 'reply', 'write', 'copy', 'move', 'update', 'modify', 'comment' -> non_idempotent_mutation
    - Any other verb -> default to non_idempotent_mutation (conservative fallback)
    """
    first_token = tool_id.lower().split("_")[0]
    
    read_prefixes = {"get", "read", "list", "search", "inspect", "fetch", "extract", "lookup"}
    idemp_prefixes = {"delete", "archive"}
    mut_prefixes = {
        "create", "insert", "add", "post", "send", "reply",
        "write", "copy", "move", "update", "modify", "comment"
    }
    
    if first_token in read_prefixes:
        return "read_only"
    if first_token in idemp_prefixes:
        return "idempotent_write"
    if first_token in mut_prefixes:
        return "non_idempotent_mutation"
    
    # Fallback for unrecognized verbs (e.g. summarize, compare, calculate, execute, solve, filter, sort, group, parse, query, validate, transform, geocode, reverse, resize, crop, convert, describe, generate, hash, encode)
    return "non_idempotent_mutation"


def run_audit() -> Dict[str, Any]:
    csv_path = Path("reports/contract_audit_100_unlabeled.csv")
    with open(csv_path, "r", encoding="utf-8") as f:
        tools = list(csv.DictReader(f))

    matches = 0
    safe_direction_errors = []
    unsafe_direction_errors = []
    audit_rows = []

    # Severity ordering: read_only (0) < idempotent_write (1) < non_idempotent_mutation (2)
    severity = {"read_only": 0, "idempotent_write": 1, "non_idempotent_mutation": 2}

    for t in tools:
        tid = t["tool_id"]
        gt_class, rationale = GROUND_TRUTH_LABELS[tid]
        inferred = naive_verb_heuristic(tid)

        match = (inferred == gt_class)
        if match:
            matches += 1
            category = "match"
        else:
            if severity[inferred] > severity[gt_class]:
                category = "safe_direction_error"
                safe_direction_errors.append({
                    "tool_id": tid,
                    "inferred": inferred,
                    "ground_truth": gt_class,
                    "reason": f"Heuristic inferred {inferred} (more restrictive) for ground truth {gt_class}. Results in harmless confirmation prompt."
                })
            else:
                category = "unsafe_direction_error"
                unsafe_direction_errors.append({
                    "tool_id": tid,
                    "inferred": inferred,
                    "ground_truth": gt_class,
                    "reason": f"Heuristic inferred {inferred} (less restrictive) for ground truth {gt_class}. Catastrophic unconfirmed execution risk!"
                })

        audit_rows.append({
            "tool_id": tid,
            "inferred": inferred,
            "ground_truth": gt_class,
            "match": match,
            "category": category,
            "rationale": rationale,
        })

    total = len(tools)
    results = {
        "audit_name": "100-Operation Real MCP Contract Inference Audit",
        "total_operations_audited": total,
        "exact_match_count": matches,
        "exact_match_rate": round(matches / total, 4),
        "safe_direction_error_count": len(safe_direction_errors),
        "safe_direction_error_rate": round(len(safe_direction_errors) / total, 4),
        "unsafe_direction_error_count": len(unsafe_direction_errors),
        "unsafe_direction_error_rate": round(len(unsafe_direction_errors) / total, 4),
        "safe_direction_examples": safe_direction_errors[:8],
        "unsafe_direction_examples": unsafe_direction_errors,
        "audit_rows": audit_rows,
    }

    out_file = Path("reports/contract_inference_audit_100.json")
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    res = run_audit()
    print("Real Contract Inference Audit Complete:")
    print(f"  Exact Matches:               {res['exact_match_count']} / {res['total_operations_audited']} ({res['exact_match_rate']*100:.1f}%)")
    print(f"  Safe-Direction Errors:       {res['safe_direction_error_count']} ({res['safe_direction_error_rate']*100:.1f}%) [Inferred mutation when actually idempotent/read-only]")
    print(f"  Unsafe-Direction Errors:     {res['unsafe_direction_error_count']} ({res['unsafe_direction_error_rate']*100:.1f}%) [Inferred read-only/idempotent when actually mutating]")
