"""Universal Polymorphic API, Skill & MCP Dataset Engine for Soro-Kev (Research Grade).

Generates multi-turn, multi-question training and zero-shot benchmark splits
from 9,922 real MCP tools and developer product APIs with 4 Real-World Hardness Layers:
1. Cross-Server Action Name Collisions (Hard Distractors in >=40% of records).
2. Mixed-Format Candidate Pools (Heterogeneous Harnesses in 50% of records).
3. 4-Mode Argument Perturbations:
   - Mode A: Synonym/Alias Drift
   - Mode B: Nested Path Flattening
   - Mode C: Abbreviation/Acronym Drift
   - Mode D: Hallucinated Extra Parameter -> __drop__
4. High-Diversity Multi-Turn & Natural Intent Generation (60+ scenarios, error recovery).

Strict Zero-Shot Server/Package Partitioning ensures zero train/val domain leakage.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT_DIR / "data" / "mcp_catalog" / "tools.parquet"
OUTPUT_DIR = ROOT_DIR / "data" / "soro_kev_dataset"

MUTATION_VERBS = {
    "create", "update", "delete", "write", "drop", "post", "patch", "remove",
    "insert", "upsert", "modify", "cancel", "refund", "charge", "transfer",
    "send", "publish", "deploy", "kill", "terminate", "set", "reset", "execute",
    "run", "apply", "commit", "push", "save", "add", "close", "start", "stop",
    "destroy", "provision", "mint", "mint_token", "wipe", "flush", "truncate"
}

ACTION_VERB_MAP = {
    "read": [
        "look into the current status of", "check on", "pull up details regarding",
        "find information about", "search for", "retrieve current data on",
        "inspect the records for", "review the state of", "verify the details of",
        "give me an overview of", "examine the telemetry for", "scan the entries for",
        "fetch the active profile for", "query the registry regarding", "poll the latest info on"
    ],
    "create": [
        "set up a new", "register a fresh", "create a brand new",
        "open a new", "log a new entry for", "initialize", "spin up a new",
        "provision", "generate a fresh", "instantiate a new", "bootstrap"
    ],
    "update": [
        "make an adjustment to", "tweak the configuration for", "update the existing",
        "apply changes to", "revise the setup for", "modify the parameters of",
        "patch the settings for", "reconfigure the state of", "overwrite the details for"
    ],
    "delete": [
        "clean up and remove", "get rid of", "discard",
        "trash", "purge the obsolete", "take down", "delete", "tear down",
        "wipe out", "decommission"
    ],
    "cancel": [
        "call off", "halt the active", "void",
        "process a cancellation for", "issue a rollback on", "shut down",
        "abort the running", "terminate the pending", "reverse"
    ],
    "send": [
        "broadcast an update to", "dispatch a notification for", "send an alert across",
        "notify the team about", "ping", "forward a message to", "publish a memo to",
        "deliver an alert regarding", "transmit details to"
    ],
    "run": [
        "kick off", "trigger the workflow for", "run the operation on",
        "execute the routine for", "launch", "fire off the task for",
        "schedule the job for", "invoke the procedure on"
    ],
}

ENTITY_SYNONYMS = {
    "invoice": ["billing statement", "payment receipt", "charge record"],
    "invoices": ["billing statements", "payment receipts", "account charges"],
    "customer": ["client account", "buyer profile", "subscriber"],
    "customers": ["client accounts", "buyer profiles", "subscribers"],
    "order": ["checkout purchase", "client order", "sale transaction"],
    "orders": ["checkout purchases", "customer transactions", "sales records"],
    "user": ["member profile", "team account", "registered identity"],
    "users": ["member profiles", "team accounts", "registered identities"],
    "message": ["chat update", "team notice", "channel communication"],
    "messages": ["chat updates", "team communications", "thread posts"],
    "issue": ["incident report", "task ticket", "bug item"],
    "issues": ["incident reports", "task tickets", "tracked bugs"],
    "repo": ["codebase repository", "git project", "code repo"],
    "repository": ["codebase repository", "git project", "source project"],
    "file": ["storage document", "file asset", "saved record"],
    "files": ["storage documents", "file assets", "saved attachments"],
    "channel": ["discussion room", "chat workspace", "team channel"],
    "payment": ["financial settlement", "cleared charge", "funds transfer"],
    "metric": ["performance telemetry", "system counter", "health gauge"],
    "metrics": ["performance telemetry", "system counters", "health gauges"],
    "cluster": ["infrastructure cluster", "compute node group", "server pool"],
    "database": ["datastore table", "records collection", "backend store"],
    "table": ["datastore table", "data matrix", "storage collection"],
    "document": ["content draft", "written asset", "record file"],
    "session": ["login connection", "authenticated session", "user context"],
    "event": ["calendar appointment", "scheduled milestone", "timeline event"],
    "log": ["diagnostic trace", "execution log", "audit record"],
    "logs": ["diagnostic traces", "execution logs", "audit records"],
    "token": ["access credential", "auth key", "bearer secret"],
}

# Mode A: Synonyms / Aliases
PARAM_MODE_A = {
    "id": ["identifier", "ref", "uuid", "key", "number", "token", "code"],
    "order_id": ["orderId", "order_ref", "target_order", "invoice_no", "order_number"],
    "user_id": ["userId", "account_id", "user_uuid", "customer_ref", "client_id"],
    "account_id": ["accountId", "user_id", "acct_num", "account_ref"],
    "query": ["q", "search_term", "query_text", "search_keywords", "filter"],
    "amount": ["value", "total", "cost", "price", "sum", "refund_amount"],
    "email": ["user_email", "mail_address", "contact_email", "email_to"],
    "message": ["text", "body", "content", "msg", "payload_text"],
    "path": ["file_path", "target_path", "filepath", "dest", "location"],
    "limit": ["max_results", "page_size", "count", "batch_size"],
    "name": ["title", "label", "entity_name", "item_name"],
    "branch": ["target_branch", "git_branch", "ref_name"],
}

# Mode B: Nested Path Flattening
PARAM_MODE_B = {
    "email": ["user.email", "account.contact.email", "client.email_address"],
    "address": ["shipping.address.street", "billing.address.line1", "user.location.address"],
    "zip": ["shipping.address.zip", "postal_code", "address.zipcode"],
    "id": ["entity.meta.id", "payload.target.id", "data.identifier"],
    "amount": ["transaction.payment.amount", "billing.charge.amount", "pricing.total_amount"],
    "status": ["workflow.state.status", "meta.lifecycle.status"],
}

# Mode C: Abbreviations & Acronyms
PARAM_MODE_C = {
    "repository": ["repo", "proj_repo"],
    "maximum": ["max", "limit"],
    "minimum": ["min"],
    "document": ["doc", "doc_id"],
    "configuration": ["cfg", "conf"],
    "environment": ["env"],
    "destination": ["dest", "target"],
    "source": ["src"],
    "synchronize": ["sync"],
    "parameters": ["params"],
    "specification": ["spec"],
    "connection": ["conn"],
    "directory": ["dir"],
    "authentication": ["auth"],
}

# Mode D: Hallucinated unsupported parameters that must map to __drop__
HALLUCINATED_PARAMS = [
    "verbose_output", "bypass_cache", "retry_count", "dry_run",
    "force_override", "return_raw_response", "debug_trace_id",
    "timeout_ms", "experimental_flag", "include_metadata", "stream_tokens",
    "audit_comment", "idempotency_token", "compression_level", "page_token"
]

SINGLE_TURN_TEMPLATES = [
    "User: We received a task ticket from ops. Could you please {phrase}{args}?",
    "User: I'm currently auditing our environment. Please {phrase}{args}.",
    "User: Quick request from the on-call engineer: please {phrase}{args}.",
    "User: Could you assist with this? We need to {phrase}{args}.",
    "User: Please take care of this request: {phrase}{args}.",
    "User: Helping a team member with their workflow: go ahead and {phrase}{args}.",
    "User: While investigating a staging discrepancy, we noticed we must {phrase}{args}.",
    "User: As part of the morning infrastructure maintenance, please {phrase}{args}.",
    "User: Customer support requested urgent assistance: could you {phrase}{args}?",
    "User: In our automated pipeline gate, we need to {phrase}{args}.",
    "User: Reviewing recent system telemetry: go ahead and {phrase}{args}.",
    "User: Quick follow-up on yesterday's action item: please {phrase}{args}.",
    "User: Before finalizing the deployment rollout, let's {phrase}{args}.",
    "User: During our scheduled database sanity check, please {phrase}{args}.",
    "User: Our integration tests flagged an anomaly. Can you {phrase}{args}?",
    "User: We are preparing the quarterly compliance report: please {phrase}{args}.",
    "User: Can you {phrase}{args} as soon as possible?",
    "User: I need to {phrase}{args} right away.",
    "User: Let's {phrase}{args} to unblock the current task.",
    "User: Automated cron worker encountered an error. Please {phrase}{args}.",
    "User: Security incident response team flagged an issue. Please {phrase}{args}.",
    "User: We are synchronizing state across regions. Could you {phrase}{args}?",
    "User: The billing reconciliation job requires verification. Please {phrase}{args}.",
    "User: Before pushing this hotfix to production, please {phrase}{args}.",
    "User: Can you handle the following operation for our release pipeline: {phrase}{args}?",
    "User: A tenant reported a missing record. Let's {phrase}{args}.",
    "User: We need to resolve an unacknowledged webhook event. Please {phrase}{args}.",
    "User: To complete the daily data warehouse ingest, please {phrase}{args}.",
    "User: As requested in the architecture review meeting, please {phrase}{args}.",
    "User: Our observability dashboard triggered a high latency alert. Let's {phrase}{args}.",
    "User: Run the following administrative task for our cluster: {phrase}{args}.",
    "User: We are validating backward compatibility for the API. Please {phrase}{args}.",
    "User: Could you verify the data integrity by choosing to {phrase}{args}?",
    "User: Developer reported an unexpected return payload. Go ahead and {phrase}{args}.",
    "User: Performing routine health diagnostics: please {phrase}{args}.",
    "User: We need to provision initial fixtures for the staging cluster. Please {phrase}{args}.",
    "User: Ops playbook step 4 requires us to {phrase}{args}.",
    "User: Please execute the maintenance task to {phrase}{args}.",
    "User: Help us triage the error spike by having the system {phrase}{args}.",
    "User: To unblock the frontend CI build, please {phrase}{args}.",
    "User: Customer success escalations team asked us to {phrase}{args}.",
    "User: For the end-of-month financial audit, please {phrase}{args}."
]

MULTI_TURN_TEMPLATES = [
    (
        "User: Can you check the output from the staging pipeline?\n"
        "Agent: [Prior Tool Observation JSON: {obs}]\n"
        "User: Thanks. Now go ahead and {phrase}{args} using those results."
    ),
    (
        "User: What did the prior step report?\n"
        "Agent: [Prior Tool Observation JSON: {obs}]\n"
        "User: Got it. Based on that outcome, please {phrase}{args}."
    ),
    (
        "User: Let's inspect recent telemetry before proceeding.\n"
        "Agent: [Prior Tool Observation JSON: {obs}]\n"
        "User: Understood. Now please {phrase}{args}."
    ),
    (
        "User: Check the primary cache for any recent events.\n"
        "Agent: [Prior Tool Observation JSON: {{\"status\": \"empty\", \"results\": [], \"duration_ms\": 14}}]\n"
        "User: The primary cache returned empty. Let's fall back and {phrase}{args} instead."
    ),
    (
        "User: What happened during the last execution attempt?\n"
        "Agent: [Prior Tool Observation JSON: {{\"error\": \"RATE_LIMIT_EXCEEDED\", \"retry_after_sec\": 30}}]\n"
        "User: Understood. While that cools down, please {phrase}{args}."
    ),
    (
        "User: Please retrieve the status for customer account REC-4921.\n"
        "Agent: [Prior Tool Observation JSON: {{\"account_id\": \"REC-4921\", \"state\": \"pending_review\"}}]\n"
        "User: Got it. Based on that pending review state, please {phrase}{args}."
    ),
    (
        "User: Run an audit on the current worker node pool.\n"
        "Agent: [Prior Tool Observation JSON: {{\"healthy\": false, \"failing_node\": \"worker_pool_2\"}}]\n"
        "User: Thanks for diagnosing. Go ahead and {phrase}{args}."
    ),
    (
        "User: Verify whether the batch export completed successfully.\n"
        "Agent: [Prior Tool Observation JSON: {{\"job_id\": \"JOB-9920\", \"status\": \"completed\", \"exported_records\": 420}}]\n"
        "User: Perfect. Now that the export is ready, please {phrase}{args}."
    ),
    (
        "User: Look up the latest transaction record in the primary region.\n"
        "Agent: [Prior Tool Observation JSON: {{\"status\": \"not_found\", \"region\": \"us-east-1\"}}]\n"
        "User: Not found in us-east-1. Please switch over and {phrase}{args}."
    ),
    (
        "User: Did the automated migration succeed?\n"
        "Agent: [Prior Tool Observation JSON: {{\"applied_migrations\": 12, \"status\": \"success\"}}]\n"
        "User: Migration complete. To finalize the verification, please {phrase}{args}."
    ),
    (
        "User: Check if there are any unhandled dead-letter queue messages.\n"
        "Agent: [Prior Tool Observation JSON: {{\"dlq_size\": 3, \"oldest_age_sec\": 450}}]\n"
        "User: DLQ has pending items. Let's {phrase}{args} to inspect them."
    ),
    (
        "User: Query the authorization service for current session permissions.\n"
        "Agent: [Prior Tool Observation JSON: {{\"roles\": [\"developer\", \"operator\"], \"valid\": true}}]\n"
        "User: Permissions confirmed. Now proceed to {phrase}{args}."
    ),
    (
        "User: Did the webhook signature validation pass?\n"
        "Agent: [Prior Tool Observation JSON: {{\"signature_valid\": true, \"event_type\": \"charge.disputed\"}}]\n"
        "User: Charge dispute confirmed. Go ahead and {phrase}{args}."
    ),
    (
        "User: Attempted to fetch the latest draft with the default query.\n"
        "Agent: [Prior Tool Observation JSON: {{\"status\": \"empty\", \"items\": []}}]\n"
        "User: That previous query returned empty. Check the archived records instead and {phrase}{args}."
    ),
    (
        "User: Did the last build step output any build artifacts?\n"
        "Agent: [Prior Tool Observation JSON: {{\"artifact_uri\": \"s3://builds/dist.tar.gz\", \"sha256\": \"e3b0c442\"}}]\n"
        "User: Excellent. Now please {phrase}{args} with those build artifacts."
    ),
    (
        "User: Check whether the database replica lag is acceptable.\n"
        "Agent: [Prior Tool Observation JSON: {{\"replica_lag_ms\": 45, \"state\": \"in_sync\"}}]\n"
        "User: Replicas are caught up. Let's {phrase}{args}."
    ),
    (
        "User: Check the rate limit status for the third-party provider.\n"
        "Agent: [Prior Tool Observation JSON: {{\"remaining\": 4500, \"limit\": 5000, \"reset_sec\": 320}}]\n"
        "User: We have ample headroom. Go ahead and {phrase}{args}."
    ),
    (
        "User: What was the outcome of the canary deployment test?\n"
        "Agent: [Prior Tool Observation JSON: {{\"error_rate\": 0.001, \"latency_p99_ms\": 42, \"passed\": true}}]\n"
        "User: Canary looks healthy. Please {phrase}{args}."
    ),
    (
        "User: Did the security scan flag any vulnerable dependencies?\n"
        "Agent: [Prior Tool Observation JSON: {{\"cve_count\": 0, \"scanned_packages\": 84, \"status\": \"clean\"}}]\n"
        "User: Clean scan report. Now we can {phrase}{args}."
    ),
    (
        "User: Inspect the last checkpoint on the training run.\n"
        "Agent: [Prior Tool Observation JSON: {{\"step\": 15000, \"loss\": 0.412, \"eval_loss\": 0.435}}]\n"
        "User: Loss is converging nicely. Please {phrase}{args}."
    ),
    (
        "User: Verify whether the idempotency key IDEMP-990 was previously used.\n"
        "Agent: [Prior Tool Observation JSON: {{\"cached\": false, \"message\": \"new_operation\"}}]\n"
        "User: New operation confirmed. Proceed to {phrase}{args}."
    ),
    (
        "User: What is the current status of the payment gateway webhook?\n"
        "Agent: [Prior Tool Observation JSON: {{\"status\": \"PENDING_SETTLEMENT\", \"amount\": 150.0}}]\n"
        "User: It's still pending settlement. Please {phrase}{args}."
    ),
    (
        "User: Did the background garbage collection sweep finish?\n"
        "Agent: [Prior Tool Observation JSON: {{\"reclaimed_bytes\": 104857600, \"duration_sec\": 2.3}}]\n"
        "User: Cleanup completed. Let's now {phrase}{args}."
    ),
    (
        "User: Check the customer's subscription tier.\n"
        "Agent: [Prior Tool Observation JSON: {{\"tier\": \"enterprise\", \"features\": [\"sso\", \"audit_logs\", \"api\"]}}]\n"
        "User: Confirmed enterprise account. Please {phrase}{args}."
    ),
    (
        "User: Review the failed task log from worker node 4.\n"
        "Agent: [Prior Tool Observation JSON: {{\"exit_code\": 137, \"reason\": \"OOMKilled\"}}]\n"
        "User: It was killed by OOM. Before restarting it, let's {phrase}{args}."
    ),
    (
        "User: Can you check if the schema migration lock is still held?\n"
        "Agent: [Prior Tool Observation JSON: {{\"lock_held\": false, \"held_by\": null}}]\n"
        "User: Lock is free. Go ahead and {phrase}{args}."
    )
]

OBSERVATION_TEMPLATES = [
    '{{"id": "{val}", "status": "active", "timestamp": "2026-10-12T10:00:00Z", "meta": {{"ref": "REF-9920"}}}}',
    '{{"result": "found", "items": [{{"id": "{val}", "name": "Target Entity", "amount": 49.99}}]}}',
    '{{"entity_id": "{val}", "state": "pending_review", "last_updated_by": "service_bot"}}',
    '{{"lookup_key": "{val}", "details": {{"customer_code": "CUST-412", "balance": 150.00}}}}',
    '{{"batch_id": "{val}", "processed_count": 142, "status": "partial_success", "errors": 0}}',
]


def is_mutation_action(name: str, desc: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", f"{name} {desc}".lower()))
    return any(v in tokens for v in MUTATION_VERBS)


def normalize_action_name(name: str) -> str:
    clean = re.sub(r"^(slack|github|gitlab|jira|postgres|sqlite|google|aws|azure|discord|shopify|linear|notion|stripe)_", "", name.lower())
    clean = re.sub(r"_(v1|v2|tool|mcp)$", "", clean)
    return clean


def classify_action_category(tool_name: str, desc: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", f"{tool_name} {desc}".lower()))
    if any(t in tokens for t in ("cancel", "abort", "refund", "stop", "kill", "terminate", "halt", "void")):
        return "cancel"
    if any(t in tokens for t in ("delete", "remove", "drop", "purge", "clear", "discard", "trash", "destroy")):
        return "delete"
    if any(t in tokens for t in ("create", "add", "new", "insert", "register", "setup", "init", "provision", "mint", "bootstrap")):
        return "create"
    if any(t in tokens for t in ("update", "modify", "edit", "change", "patch", "set", "reset", "adjust", "revise", "reconfigure")):
        return "update"
    if any(t in tokens for t in ("send", "notify", "publish", "post", "dispatch", "broadcast", "ping", "transmit")):
        return "send"
    if any(t in tokens for t in ("run", "execute", "trigger", "launch", "apply", "commit", "push", "start", "schedule")):
        return "run"
    return "read"


def extract_paraphrased_entity(tool_name: str, desc: str, rng: random.Random) -> str:
    name_words = re.findall(r"[a-z0-9]+", tool_name.lower())
    ignore_words = {
        "get", "fetch", "read", "view", "show", "describe", "find", "search", "list",
        "lookup", "query", "check", "inspect", "audit", "scan", "pull",
        "create", "add", "new", "insert", "register", "setup", "init", "provision",
        "update", "modify", "edit", "change", "patch", "set", "reset", "adjust",
        "delete", "remove", "drop", "purge", "clear", "discard", "trash",
        "cancel", "abort", "refund", "stop", "kill", "terminate", "halt",
        "send", "notify", "publish", "post", "dispatch", "broadcast", "ping",
        "run", "execute", "trigger", "launch", "apply", "start",
        "tool", "mcp", "api", "v1", "v2", "service", "handler", "endpoint", "func"
    }
    entity_tokens = [w for w in name_words if w not in ignore_words and len(w) > 1]

    replaced_tokens = []
    for tok in entity_tokens:
        if tok in ENTITY_SYNONYMS:
            syn = rng.choice(ENTITY_SYNONYMS[tok])
            replaced_tokens.append(syn)
        else:
            replaced_tokens.append(tok)

    if replaced_tokens:
        return " ".join(replaced_tokens)

    desc_words = [w for w in re.findall(r"[a-z0-9]+", desc.lower()) if w not in ignore_words and len(w) > 3]
    if desc_words:
        chosen = desc_words[:2]
        return " ".join(chosen)

    return "target resource"


def synthesize_user_intent(tool_name: str, desc: str, server_name: str, rng: random.Random, mention_context: bool = False) -> str:
    cat = classify_action_category(tool_name, desc)
    action_phrase = rng.choice(ACTION_VERB_MAP[cat])
    entity_phrase = extract_paraphrased_entity(tool_name, desc, rng)
    
    intent = f"{action_phrase} {entity_phrase}"
    if mention_context and server_name:
        clean_ctx = re.sub(r"[^a-zA-Z0-9]+", " ", server_name).strip()
        ctx_phrases = [
            f"in our {clean_ctx} service",
            f"within the {clean_ctx} workspace",
            f"for the {clean_ctx} environment",
            f"on {clean_ctx}",
        ]
        intent = f"{intent} {rng.choice(ctx_phrases)}"
    return intent


def format_natural_args(args: dict[str, Any]) -> str:
    if not args:
        return ""
    phrases = []
    for k, v in list(args.items())[:3]:
        if "id" in k:
            phrases.append(f"referencing identifier '{v}'")
        elif "limit" in k or "count" in k:
            phrases.append(f"limiting to {v} entries")
        elif "amount" in k or "price" in k:
            phrases.append(f"with amount {v}")
        elif "query" in k or "search" in k:
            phrases.append(f"filtering for '{v}'")
        elif "email" in k:
            phrases.append(f"for account '{v}'")
        elif "branch" in k:
            phrases.append(f"on branch '{v}'")
        else:
            phrases.append(f"with {k} set to '{v}'")
    return " (" + ", ".join(phrases) + ")"


def render_action_spec(
    tool_name: str,
    server_name: str,
    desc: str,
    props: dict[str, Any],
    reqs: list[str],
    fmt: str,
    delexicalize: bool = False,
    delex_id: str = "",
) -> tuple[str, str]:
    """Render tool spec into one of 5 polymorphic developer formats."""
    display_name = delex_id if delexicalize and delex_id else tool_name

    if fmt == "agent_skill":
        trigs = ", ".join([f"run {display_name}", display_name.replace("_", " ")])
        args_str = " ".join([f"--{p} <val>" for p in props])
        text = f"[SKILL: {display_name}] triggers: {trigs} | command: /{display_name} {args_str} | {desc}"
        return display_name, text

    elif fmt == "rest_openapi":
        method = "POST" if is_mutation_action(tool_name, desc) else "GET"
        clean_srv = re.sub(r"[^a-zA-Z0-9]+", "_", server_name).strip("_")
        clean_tool = display_name if delexicalize else tool_name
        endpoint = f"/api/v1/{clean_srv}/{clean_tool}"
        query_params = [p for p in props if p in ("limit", "offset", "filter", "query", "q")]
        body_params = [p for p in props if p not in query_params]
        text = f"[REST: {method} {endpoint}] query: {query_params} | body: {body_params} | {desc}"
        return display_name, text

    elif fmt == "python_sig":
        params_list = []
        for p, info in props.items():
            t_name = info.get("type", "Any") if isinstance(info, dict) else "Any"
            py_t = "int" if t_name == "integer" else ("float" if t_name == "number" else ("str" if t_name == "string" else "Any"))
            if p not in reqs:
                params_list.append(f"{p}: {py_t} = None")
            else:
                params_list.append(f"{p}: {py_t}")
        sig = ", ".join(params_list)
        text = f"def {display_name}({sig}) -> dict:\n    \"\"\"{desc}\"\"\""
        return display_name, text

    elif fmt == "graphql_rpc":
        op_type = "mutation" if is_mutation_action(tool_name, desc) else "query"
        pascal_name = "".join(w.capitalize() for w in re.findall(r"[a-zA-Z0-9]+", display_name))
        vars_str = ", ".join([f"${p}: String" + ("!" if p in reqs else "") for p in list(props)[:4]])
        text = f"{op_type} {pascal_name}({vars_str}): ResponsePayload # {desc}"
        return display_name, text

    else:  # mcp_json (default)
        prop_defs = {p: (info.get("type", "string") if isinstance(info, dict) else "string") for p, info in props.items()}
        text = f"[MCP] {display_name}: {desc} | required: {reqs} | properties: {prop_defs}"
        return display_name, text


def build_synthetic_context(
    tool_name: str,
    desc: str,
    server_name: str,
    props: dict[str, Any],
    reqs: list[str],
    is_multi_turn: bool,
    omit_required: bool,
    has_collision_distractor: bool,
    rng: random.Random,
) -> tuple[str, dict[str, Any], str | None]:
    """Generate realistic user prompt or multi-turn conversational agent context."""
    provided_args: dict[str, Any] = {}
    omitted_param: str | None = None

    for p in props:
        val = f"{p}_val_819"
        if "id" in p:
            val = rng.choice(["TXN-8841", "REC-4921", "INV-2026-09", "USR-5521", "TASK-102"])
        elif "amount" in p or "price" in p:
            val = rng.choice([19.99, 49.50, 150.00, 2500.00])
        elif "count" in p or "limit" in p:
            val = rng.choice([10, 25, 50, 100])
        elif "query" in p or "search" in p:
            val = rng.choice(["production telemetry", "customer billing dispute", "active compute nodes", "unmerged pull requests"])
        elif "email" in p:
            val = rng.choice(["developer@corp.internal", "ops-lead@company.io", "auditor@sec.org"])
        elif "branch" in p:
            val = rng.choice(["main", "staging", "hotfix/patch-2026"])
        provided_args[p] = val

    if omit_required and reqs:
        omitted_param = rng.choice(reqs)
        provided_args.pop(omitted_param, None)

    # If cross-server collision distractor is present, include server context in query so it's disambiguated
    intent_phrase = synthesize_user_intent(tool_name, desc, server_name, rng, mention_context=has_collision_distractor)
    args_desc = format_natural_args(provided_args)

    if is_multi_turn:
        sample_val = provided_args.get("id") or provided_args.get("order_id") or "TXN-8841"
        obs_tmpl = rng.choice(OBSERVATION_TEMPLATES).format(val=sample_val)
        tmpl = rng.choice(MULTI_TURN_TEMPLATES)
        state_text = tmpl.format(obs=obs_tmpl, phrase=intent_phrase, args=args_desc, srv=server_name)
    else:
        tmpl = rng.choice(SINGLE_TURN_TEMPLATES)
        state_text = tmpl.format(phrase=intent_phrase, args=args_desc)

    return state_text, provided_args, omitted_param


def build_arg_mapping_question(
    gold_props: dict[str, Any],
    rng: random.Random,
) -> tuple[dict[str, str], str, str]:
    """Build 4-mode realistic parameter mapping perturbation."""
    if not gold_props:
        return {"__drop__": "No schema parameters available"}, "__drop__", "unrecognized_arg_key"

    target_prop = rng.choice(list(gold_props.keys()))
    mode = rng.choice(["A", "B", "C", "D"])
    perturbed_arg = target_prop
    arg_choice = target_prop

    if mode == "A":  # Synonym/Alias Drift
        syns = PARAM_MODE_A.get(target_prop, [f"{target_prop}_ref", f"{target_prop}Id", f"input_{target_prop}"])
        perturbed_arg = rng.choice(syns)
        arg_choice = target_prop
    elif mode == "B":  # Nested Path Flattening
        nested = PARAM_MODE_B.get(target_prop, [f"payload.{target_prop}", f"data.{target_prop}.val"])
        perturbed_arg = rng.choice(nested)
        arg_choice = target_prop
    elif mode == "C":  # Abbreviation/Acronym Drift
        abbrevs = PARAM_MODE_C.get(target_prop, [f"{target_prop[:3]}_val", f"{target_prop[:4]}"])
        perturbed_arg = rng.choice(abbrevs)
        arg_choice = target_prop
    else:  # Mode D: Hallucinated Extra Parameter -> __drop__
        perturbed_arg = rng.choice(HALLUCINATED_PARAMS)
        arg_choice = "__drop__"

    criteria: dict[str, str] = {}
    sample_props = list(gold_props.keys())
    if arg_choice in sample_props:
        sample_props.remove(arg_choice)
        rng.shuffle(sample_props)
        chosen_props = [arg_choice] + sample_props[:5]
        rng.shuffle(chosen_props)
    else:
        rng.shuffle(sample_props)
        chosen_props = sample_props[:6]

    for p_name in chosen_props:
        criteria[p_name] = f"Schema parameter: {p_name}"
    criteria["__drop__"] = "Ignore or drop unrecognized extra parameter"

    return criteria, arg_choice, perturbed_arg


def generate_dataset_records(
    tools_table,
    package_list: list[str],
    is_train: bool,
    target_count: int,
) -> list[dict[str, Any]]:
    """Build polymorphic multi-question dataset records with 4 hardness layers."""
    FORMATS = ["mcp_json", "agent_skill", "rest_openapi", "python_sig", "graphql_rpc"]

    package_set = set(package_list)
    pkg_col = tools_table["package"].to_pylist()
    srv_col = tools_table["server_name"].to_pylist()
    name_col = tools_table["tool_name"].to_pylist()
    desc_col = tools_table["tool_description"].to_pylist()
    schema_col = tools_table["input_schema"].to_pylist()

    records_by_pkg: dict[str, list[dict[str, Any]]] = {}
    tools_by_stem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tools_by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_tools: list[dict[str, Any]] = []

    for pkg, srv, name, desc, raw_sch in zip(pkg_col, srv_col, name_col, desc_col, schema_col):
        if pkg not in package_set:
            continue
        try:
            sch = json.loads(raw_sch) if isinstance(raw_sch, str) and raw_sch else {}
        except Exception:
            sch = {}

        props = sch.get("properties", {}) if isinstance(sch, dict) else {}
        reqs = sch.get("required", []) if isinstance(sch, dict) else []
        desc_str = (desc or name).strip()
        norm_stem = normalize_action_name(name)
        act_cat = classify_action_category(name, desc_str)

        t_data = {
            "package": pkg,
            "server": srv or pkg,
            "name": name,
            "description": desc_str,
            "properties": props,
            "required": reqs,
            "norm_action": norm_stem,
            "action_cat": act_cat,
        }
        records_by_pkg.setdefault(pkg, []).append(t_data)
        tools_by_stem[norm_stem].append(t_data)
        tools_by_cat[act_cat].append(t_data)
        all_tools.append(t_data)

    if not all_tools:
        return []

    dataset: list[dict[str, Any]] = []
    rng = random.Random(42 if is_train else 1337)
    delex_counter = 100

    while len(dataset) < target_count:
        gold = rng.choice(all_tools)
        pkg = gold["package"]
        srv = gold["server"]

        is_multi_turn = rng.random() < 0.50
        omit_required = rng.random() < 0.25
        is_abstain_twin = rng.random() < 0.15
        delexicalize = is_train and (rng.random() < 0.40)
        
        # Layer 2: Heterogeneous mixed-format candidate pool in 50% of records
        is_mixed_format = rng.random() < 0.50
        record_format = "mixed_heterogeneous" if is_mixed_format else rng.choice(FORMATS)

        # Layer 1: Cross-Server Action Name / Category Collision distractor in >= 40% of records
        has_collision_distractor = rng.random() < 0.45
        norm_action = gold["norm_action"]
        gold_cat = gold["action_cat"]
        exact_stem_cands = [
            t for t in tools_by_stem.get(norm_action, [])
            if t["package"] != pkg and t["name"] != gold["name"]
        ]
        cat_cands = [
            t for t in tools_by_cat.get(gold_cat, [])
            if t["package"] != pkg and t["name"] != gold["name"]
        ]
        collision_candidates = exact_stem_cands if exact_stem_cands else cat_cands

        delex_id = f"op_{delex_counter}" if delexicalize else ""
        if delexicalize:
            delex_counter += 1

        state_text, provided_args, omitted_param = build_synthetic_context(
            gold["name"], gold["description"], srv, gold["properties"], gold["required"],
            is_multi_turn=is_multi_turn, omit_required=omit_required,
            has_collision_distractor=has_collision_distractor and bool(collision_candidates), rng=rng
        )

        # Build candidate options (4 to 8 candidates)
        num_candidates = rng.randint(4, 8)
        chosen_candidates = []
        actual_has_collision = False

        # 1. Add collision distractor if available
        if has_collision_distractor and collision_candidates:
            chosen_candidates.append(rng.choice(collision_candidates))
            actual_has_collision = True

        # 2. Add 1-2 same-server hard negatives
        same_pkg = records_by_pkg.get(pkg, [])
        if len(same_pkg) > 1:
            same_pkg_cands = [t for t in same_pkg if t["name"] != gold["name"]]
            if same_pkg_cands:
                k = min(len(same_pkg_cands), rng.randint(1, 2))
                chosen_candidates.extend(rng.sample(same_pkg_cands, k))

        # 3. Fill remaining with cross-server distractors (O(1) sampling)
        needed = num_candidates - len(chosen_candidates) - (0 if is_abstain_twin else 1)
        attempts = 0
        while len(chosen_candidates) < (num_candidates - (0 if is_abstain_twin else 1)) and attempts < 40:
            attempts += 1
            cand = rng.choice(all_tools)
            if cand["package"] != pkg and cand["name"] != gold["name"] and cand not in chosen_candidates:
                chosen_candidates.append(cand)

        # Render criteria dictionary with mixed or uniform formats
        criteria: dict[str, str] = {}
        rendered_gold_key = None

        gold_fmt = rng.choice(FORMATS) if is_mixed_format else record_format
        if not is_abstain_twin:
            g_key, g_spec = render_action_spec(
                gold["name"], srv, gold["description"], gold["properties"],
                gold["required"], gold_fmt, delexicalize=delexicalize, delex_id=delex_id
            )
            criteria[g_key] = g_spec
            rendered_gold_key = g_key

        for cand in chosen_candidates:
            cand_fmt = rng.choice(FORMATS) if is_mixed_format else record_format
            c_key, c_spec = render_action_spec(
                cand["name"], cand["server"], cand["description"], cand["properties"],
                cand["required"], cand_fmt, delexicalize=False
            )
            if c_key not in criteria:
                criteria[c_key] = c_spec

        criteria["__abstain__"] = "None of the listed tools/skills fit the user request"

        # Shuffled keys for tool_route
        opt_keys = list(criteria.keys())
        rng.shuffle(opt_keys)
        shuffled_criteria = {k: criteria[k] for k in opt_keys}

        # Permuted (reversed) keys for tool_route_perm
        perm_keys = list(reversed(opt_keys))
        perm_criteria = {k: criteria[k] for k in perm_keys}

        gold_route_choice = "__abstain__" if is_abstain_twin else rendered_gold_key

        # Layer 3: 4-Mode Argument Mapping Question
        arg_criteria, arg_choice, perturbed_arg = build_arg_mapping_question(gold["properties"], rng)

        # Question 4: Missing Required
        missing_label = "yes" if omit_required and omitted_param else "no"

        # Question 5: Is Mutation
        is_mut = is_mutation_action(gold["name"], gold["description"])
        mutation_label = "yes" if is_mut else "no"

        record = {
            "id": f"{'train' if is_train else 'val'}_{len(dataset):06d}",
            "package": pkg,
            "server_name": srv,
            "format": record_format,
            "delexicalized": delexicalize,
            "is_multi_turn": is_multi_turn,
            "has_collision_distractor": actual_has_collision,
            "state": state_text,
            "questions": {
                "tool_route": {
                    "type": "choice",
                    "instructions": "Which single tool or skill should run for this request? Use only the listed candidates.",
                    "criteria": shuffled_criteria,
                    "label": gold_route_choice,
                },
                "tool_route_perm": {
                    "type": "choice",
                    "instructions": "Which single tool or skill should run for this request? Use only the listed candidates.",
                    "criteria": perm_criteria,
                    "label": gold_route_choice,
                },
                "arg_mapping": {
                    "type": "choice",
                    "instructions": f"Which target parameter in the tool schema does the argument '{perturbed_arg}' correspond to?",
                    "criteria": arg_criteria,
                    "label": arg_choice,
                },
                "missing_required": {
                    "type": "noul",
                    "instructions": "Is any required parameter missing from the context, requiring the harness to ask the user before calling the tool?",
                    "label": missing_label,
                },
                "is_mutation": {
                    "type": "noul",
                    "instructions": "Does this action execute a mutation (write, update, delete, payment) rather than a read-only query?",
                    "label": mutation_label,
                },
            },
        }
        dataset.append(record)

    return dataset


def main():
    parser = argparse.ArgumentParser(description="Build Soro-Kev Universal Multi-Question Dataset")
    parser.add_argument("--catalog", type=str, default=str(CATALOG_PATH))
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR))
    parser.add_argument("--train-ratio", type=float, default=0.85)
    parser.add_argument("--train-count", type=int, default=34000)
    parser.add_argument("--val-count", type=int, default=3000)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading tool catalog from {args.catalog}...")
    table = pq.read_table(args.catalog)
    total_tools = len(table)
    print(f"Total tools in catalog: {total_tools}")

    # Unique packages (servers)
    packages = sorted(list(set(table["package"].to_pylist())))
    print(f"Total unique server packages: {len(packages)}")

    # Deterministic zero-shot split by package
    rng = random.Random(2026)
    rng.shuffle(packages)
    n_train_pkgs = int(len(packages) * args.train_ratio)
    train_packages = packages[:n_train_pkgs]
    val_packages = packages[n_train_pkgs:]

    print(f"Partitioned: {len(train_packages)} train server packages / {len(val_packages)} held-out zero-shot val packages.")

    print(f"Synthesizing {args.train_count} train records (polymorphic + 4 hardness layers)...")
    train_data = generate_dataset_records(table, train_packages, is_train=True, target_count=args.train_count)

    print(f"Synthesizing {args.val_count} zero-shot held-out val records...")
    val_data = generate_dataset_records(table, val_packages, is_train=False, target_count=args.val_count)

    train_path = out_dir / "train.jsonl"
    val_path = out_dir / "val_zeroshot.jsonl"

    print(f"Writing {len(train_data)} records to {train_path}...")
    with train_path.open("w", encoding="utf-8") as f:
        for r in train_data:
            f.write(json.dumps(r) + "\n")

    print(f"Writing {len(val_data)} records to {val_path}...")
    with val_path.open("w", encoding="utf-8") as f:
        for r in val_data:
            f.write(json.dumps(r) + "\n")

    print("Upscaled universal dataset generation complete!")


if __name__ == "__main__":
    main()
