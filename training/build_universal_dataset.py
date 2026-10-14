"""Universal Polymorphic API, Skill & MCP Dataset Engine for Soro-Kev.

Generates multi-turn, multi-question training and zero-shot benchmark splits
from 9,922 real MCP tools and developer product APIs.

Features:
- Strict Zero-Shot Server/Domain Partitioning (85% train / 15% val by server_name).
- 5 Polymorphic Formats: mcp_json, agent_skill, rest_openapi, python_sig, graphql_rpc.
- Anti-Lexical Leakage: Natural user intent paraphrasing, domain synonyms, realistic scenarios.
  Strips verbatim docstring sentences so simple word-overlap baselines cannot cheat.
- Multi-Turn Agent Conversations (User -> Tool Observation JSON -> Follow-up).
- 5 Parallel Question Branches per record:
  1. tool_route (choice over 4-10 candidates + __abstain__)
  2. tool_route_perm (exact same candidates shuffled/reversed for permutation invariance)
  3. arg_mapping (choice mapping perturbed LLM aliases to target schema parameters or __drop__)
  4. missing_required (noul yes/no detecting when required parameters are omitted)
  5. is_mutation (noul yes/no predicting mutating vs read-only actions)
- De-Lexicalized Schema Randomization (40% of train) & Abstain Twins (15% of samples).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
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
    "run", "apply", "commit", "push", "save", "add", "close", "start", "stop"
}

ACTION_VERB_MAP = {
    "read": [
        "look into the current status of", "check on", "pull up details regarding",
        "find information about", "search for", "retrieve current data on",
        "inspect the records for", "review the state of", "verify the details of",
        "give me an overview of", "examine"
    ],
    "create": [
        "set up a new", "register a fresh", "create a brand new",
        "open a new", "log a new entry for", "initialize", "spin up a new", "provision"
    ],
    "update": [
        "make an adjustment to", "tweak the configuration for", "update the existing",
        "apply changes to", "revise the setup for", "modify"
    ],
    "delete": [
        "clean up and remove", "get rid of", "discard",
        "trash", "purge the obsolete", "take down", "delete"
    ],
    "cancel": [
        "call off", "halt the active", "void",
        "process a cancellation for", "issue a rollback on", "shut down"
    ],
    "send": [
        "broadcast an update to", "dispatch a notification for", "send an alert across",
        "notify the team about", "ping", "forward a message to"
    ],
    "run": [
        "kick off", "trigger the workflow for", "run the operation on",
        "execute", "launch the routine for"
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
}

PARAM_SYNONYMS = {
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

OBSERVATION_TEMPLATES = [
    '{{"id": "{val}", "status": "active", "timestamp": "2026-10-12T10:00:00Z", "meta": {{"ref": "REF-9920"}}}}',
    '{{"result": "found", "items": [{{"id": "{val}", "name": "Target Entity", "amount": 49.99}}]}}',
    '{{"entity_id": "{val}", "state": "pending_review", "last_updated_by": "service_bot"}}',
    '{{"lookup_key": "{val}", "details": {{"customer_code": "CUST-412", "balance": 150.00}}}}',
]

SINGLE_TURN_TEMPLATES = [
    "User: We received a task ticket from ops. Could you please {phrase}{args}?",
    "User: I'm currently auditing our environment. Please {phrase}{args}.",
    "User: Quick request from the on-call engineer: please {phrase}{args}.",
    "User: Could you assist with this? We need to {phrase}{args}.",
    "User: Please take care of this request: {phrase}{args}.",
    "User: Helping a team member with their workflow: go ahead and {phrase}{args}.",
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
]


def is_mutation_action(name: str, desc: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", f"{name} {desc}".lower()))
    return any(v in tokens for v in MUTATION_VERBS)


def classify_action_category(tool_name: str, desc: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", f"{tool_name} {desc}".lower()))
    if any(t in tokens for t in ("cancel", "abort", "refund", "stop", "kill", "terminate", "halt", "void")):
        return "cancel"
    if any(t in tokens for t in ("delete", "remove", "drop", "purge", "clear", "discard", "trash")):
        return "delete"
    if any(t in tokens for t in ("create", "add", "new", "insert", "register", "setup", "init", "provision", "mint")):
        return "create"
    if any(t in tokens for t in ("update", "modify", "edit", "change", "patch", "set", "reset", "adjust", "revise")):
        return "update"
    if any(t in tokens for t in ("send", "notify", "publish", "post", "dispatch", "broadcast", "ping")):
        return "send"
    if any(t in tokens for t in ("run", "execute", "trigger", "launch", "apply", "commit", "push", "start")):
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

    # If no distinct tokens in name, pick 1-2 salient concepts from description without verbatim sentences
    desc_words = [w for w in re.findall(r"[a-z0-9]+", desc.lower()) if w not in ignore_words and len(w) > 3]
    if desc_words:
        chosen = desc_words[:2]
        return " ".join(chosen)

    return "target resource"


def synthesize_user_intent(tool_name: str, desc: str, rng: random.Random) -> str:
    cat = classify_action_category(tool_name, desc)
    action_phrase = rng.choice(ACTION_VERB_MAP[cat])
    entity_phrase = extract_paraphrased_entity(tool_name, desc, rng)
    return f"{action_phrase} {entity_phrase}"


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
    props: dict[str, Any],
    reqs: list[str],
    is_multi_turn: bool,
    omit_required: bool,
    rng: random.Random,
) -> tuple[str, dict[str, Any], str | None]:
    """Generate realistic user prompt or multi-turn conversational agent context with no verbatim docstring copying."""
    provided_args: dict[str, Any] = {}
    omitted_param: str | None = None

    for p in props:
        val = f"{p}_val_819"
        if "id" in p:
            val = "REC-4921"
        elif "amount" in p or "price" in p:
            val = 49.99
        elif "count" in p or "limit" in p:
            val = 10
        elif "query" in p or "search" in p:
            val = "production telemetry"
        elif "email" in p:
            val = "operator@corp.internal"
        provided_args[p] = val

    if omit_required and reqs:
        omitted_param = rng.choice(reqs)
        provided_args.pop(omitted_param, None)

    # Paraphrased user intent without copying docstrings
    intent_phrase = synthesize_user_intent(tool_name, desc, rng)
    args_desc = format_natural_args(provided_args)

    if is_multi_turn:
        sample_val = provided_args.get("id") or provided_args.get("order_id") or "TXN-8841"
        obs_tmpl = rng.choice(OBSERVATION_TEMPLATES).format(val=sample_val)
        tmpl = rng.choice(MULTI_TURN_TEMPLATES)
        state_text = tmpl.format(obs=obs_tmpl, phrase=intent_phrase, args=args_desc)
    else:
        tmpl = rng.choice(SINGLE_TURN_TEMPLATES)
        state_text = tmpl.format(phrase=intent_phrase, args=args_desc)

    return state_text, provided_args, omitted_param


def generate_dataset_records(
    tools_table,
    server_list: list[str],
    is_train: bool,
    target_count: int,
) -> list[dict[str, Any]]:
    """Build polymorphic multi-question dataset records."""
    FORMATS = ["mcp_json", "agent_skill", "rest_openapi", "python_sig", "graphql_rpc"]

    # Filter tools for these servers
    server_set = set(server_list)
    srv_col = tools_table["server_name"].to_pylist()
    pkg_col = tools_table["package"].to_pylist()
    name_col = tools_table["tool_name"].to_pylist()
    desc_col = tools_table["tool_description"].to_pylist()
    schema_col = tools_table["input_schema"].to_pylist()

    records_by_server: dict[str, list[dict[str, Any]]] = {}
    all_tools: list[dict[str, Any]] = []

    for srv, pkg, name, desc, raw_sch in zip(srv_col, pkg_col, name_col, desc_col, schema_col):
        if srv not in server_set:
            continue
        try:
            sch = json.loads(raw_sch) if isinstance(raw_sch, str) and raw_sch else {}
        except Exception:
            sch = {}

        props = sch.get("properties", {}) if isinstance(sch, dict) else {}
        reqs = sch.get("required", []) if isinstance(sch, dict) else []

        t_data = {
            "server": srv,
            "package": pkg,
            "name": name,
            "description": (desc or name).strip(),
            "properties": props,
            "required": reqs,
        }
        records_by_server.setdefault(srv, []).append(t_data)
        all_tools.append(t_data)

    if not all_tools:
        return []

    dataset: list[dict[str, Any]] = []
    rng = random.Random(42 if is_train else 1337)

    delex_counter = 100

    while len(dataset) < target_count:
        gold = rng.choice(all_tools)
        srv = gold["server"]

        is_multi_turn = rng.random() < 0.50
        omit_required = rng.random() < 0.25
        is_abstain_twin = rng.random() < 0.15
        delexicalize = is_train and (rng.random() < 0.40)
        fmt = rng.choice(FORMATS)

        delex_id = f"op_{delex_counter}" if delexicalize else ""
        if delexicalize:
            delex_counter += 1

        state_text, provided_args, omitted_param = build_synthetic_context(
            gold["name"], gold["description"], gold["properties"], gold["required"],
            is_multi_turn=is_multi_turn, omit_required=omit_required, rng=rng
        )

        # Build candidate options (4 to 8 candidates)
        num_candidates = rng.randint(4, 8)
        same_server_cands = [t for t in records_by_server.get(srv, []) if t["name"] != gold["name"]]
        cross_server_cands = [t for t in all_tools if t["server"] != srv]

        chosen_candidates = []
        # Add 1-2 same server hard negatives
        rng.shuffle(same_server_cands)
        chosen_candidates.extend(same_server_cands[: rng.randint(1, 2)])

        # Fill remaining with cross-server distractors
        rng.shuffle(cross_server_cands)
        needed = num_candidates - len(chosen_candidates) - (0 if is_abstain_twin else 1)
        chosen_candidates.extend(cross_server_cands[: max(1, needed)])

        # Render criteria dictionary
        criteria: dict[str, str] = {}
        rendered_gold_key = None

        if not is_abstain_twin:
            g_key, g_spec = render_action_spec(
                gold["name"], srv, gold["description"], gold["properties"],
                gold["required"], fmt, delexicalize=delexicalize, delex_id=delex_id
            )
            criteria[g_key] = g_spec
            rendered_gold_key = g_key

        for cand in chosen_candidates:
            c_fmt = rng.choice(FORMATS)
            c_key, c_spec = render_action_spec(
                cand["name"], cand["server"], cand["description"], cand["properties"],
                cand["required"], c_fmt, delexicalize=False
            )
            if c_key not in criteria:
                criteria[c_key] = c_spec

        criteria["__abstain__"] = "None of the listed tools/skills fit the user request"

        # Shuffled keys for tool_route
        opt_keys = list(criteria.keys())
        rng.shuffle(opt_keys)
        shuffled_criteria = {k: criteria[k] for k in opt_keys}

        # Permuted (reversed or cyclic) keys for tool_route_perm
        perm_keys = list(reversed(opt_keys))
        perm_criteria = {k: criteria[k] for k in perm_keys}

        gold_route_choice = "__abstain__" if is_abstain_twin else rendered_gold_key

        # Question 3: Argument Mapping
        arg_criteria: dict[str, str] = {}
        arg_choice = "__drop__"
        perturbed_arg = "unrecognized_arg_key"

        if gold["properties"]:
            target_p = rng.choice(list(gold["properties"].keys()))
            # 85% real perturbed key, 15% hallucinated extra key
            if rng.random() < 0.85:
                synonyms = PARAM_SYNONYMS.get(target_p, [f"{target_p}_ref", f"{target_p}Id", f"input_{target_p}"])
                perturbed_arg = rng.choice(synonyms)
                arg_choice = target_p
            else:
                perturbed_arg = rng.choice(["debug_trace_id", "frobnicate_token", "experimental_flag"])
                arg_choice = "__drop__"

            for p_name in list(gold["properties"].keys())[:5]:
                arg_criteria[p_name] = f"Schema parameter: {p_name}"
            arg_criteria["__drop__"] = "Ignore or drop unrecognized extra parameter"
        else:
            arg_criteria["__drop__"] = "No schema parameters available"

        # Question 4: Missing Required
        missing_label = "yes" if omit_required and omitted_param else "no"

        # Question 5: Is Mutation
        is_mut = is_mutation_action(gold["name"], gold["description"])
        mutation_label = "yes" if is_mut else "no"

        record = {
            "id": f"{'train' if is_train else 'val'}_{len(dataset):06d}",
            "server_name": srv,
            "format": fmt,
            "delexicalized": delexicalize,
            "is_multi_turn": is_multi_turn,
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
    parser.add_argument("--max-samples", type=int, default=8000)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading tool catalog from {args.catalog}...")
    table = pq.read_table(args.catalog)
    total_tools = len(table)
    print(f"Total tools in catalog: {total_tools}")

    # Unique servers
    servers = sorted(list(set(table["server_name"].to_pylist())))
    print(f"Total unique servers: {len(servers)}")

    # Deterministic split by server_name
    rng = random.Random(2026)
    rng.shuffle(servers)
    n_train_srv = int(len(servers) * args.train_ratio)
    train_servers = servers[:n_train_srv]
    val_servers = servers[n_train_srv:]

    print(f"Partitioned: {len(train_servers)} train servers / {len(val_servers)} held-out zero-shot val servers.")

    target_train = min(int(args.max_samples * args.train_ratio), 6800)
    target_val = min(args.max_samples - target_train, 1200)

    print(f"Synthesizing {target_train} train records (polymorphic + multi-turn + anti-lexical leakage)...")
    train_data = generate_dataset_records(table, train_servers, is_train=True, target_count=target_train)

    print(f"Synthesizing {target_val} zero-shot held-out val records...")
    val_data = generate_dataset_records(table, val_servers, is_train=False, target_count=target_val)

    # Write splits
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

    print("Dataset generation complete!")


if __name__ == "__main__":
    main()
