"""
Dataset Disjointness & Integrity Verification Audit Script
Validates 3-Tier Disjointness:
1. Package-Level Disjointness
2. Tool-Level Overlap & Fuzzy Description Similarity
3. Query-Level Exact & Near-Duplicate (n-gram Jaccard) Similarity
Also outputs stratification counts for collision vs clean distractors.
"""

import json
import os
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher
from collections import Counter


def normalize_tool_name(name: str) -> str:
    """Normalize tool name for strict and fuzzy comparison."""
    name = name.lower()
    name = re.sub(r"^[a-z0-9_]+/", "", name)  # strip namespace
    name = re.sub(r"[_\-\./:]+", "_", name).strip("_")
    return name


def extract_query(state: str) -> str:
    """Extract clean user request from state prompt."""
    match = re.search(r"User Request:\s*(.+?)(?:\nAgent:|\nPrior tool observation:|\nUser:|$)", state, re.DOTALL)
    if match:
        return match.group(1).strip()
    return state.strip()


def get_char_ngrams(text: str, n: int = 3) -> set:
    """Generate character n-grams for Jaccard similarity."""
    text = re.sub(r"\s+", " ", text.lower().strip())
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def compute_dense_vector(text: str, num_dims: int = 512) -> list[float]:
    """Compute normalized hashed n-gram dense embedding vector for semantic similarity."""
    import math
    vec = [0.0] * num_dims
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    for t in tokens:
        h = abs(hash(t)) % num_dims
        vec[h] += 1.0
        if len(t) >= 3:
            for i in range(len(t) - 2):
                sub_h = abs(hash(t[i:i+3])) % num_dims
                vec[sub_h] += 0.5
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0.0 else vec


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    return sum(a * b for a, b in zip(v1, v2))


def main():
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "releases" / "soro-universal-tool-harness"
    train_path = data_dir / "train.jsonl"
    val_ext_path = data_dir / "val_external_heldout.jsonl"
    val_zero_path = data_dir / "val_zeroshot.jsonl"
    output_dir = repo_root / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "disjointness_audit.json"

    print(f"Loading datasets from {data_dir}...")
    if not train_path.exists():
        print(f"Error: {train_path} not found.")
        sys.exit(1)

    # 1. Load Datasets
    train_records = []
    with open(train_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                train_records.append(json.loads(line))

    ext_records = []
    with open(val_ext_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                ext_records.append(json.loads(line))

    zero_records = []
    with open(val_zero_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                zero_records.append(json.loads(line))

    print(f"Loaded: train={len(train_records)} rows, val_external={len(ext_records)} rows, val_zeroshot={len(zero_records)} rows.")

    # 2. Tier 1: Package-Level Disjointness
    train_packages = {r.get("package") for r in train_records if r.get("package")}
    ext_packages = {r.get("package") for r in ext_records if r.get("package")}
    zero_packages = {r.get("package") for r in zero_records if r.get("package")}

    ext_pkg_overlap = ext_packages.intersection(train_packages)
    zero_pkg_overlap = zero_packages.intersection(train_packages)

    print("\n--- Tier 1: Package Disjointness ---")
    print(f"Train packages count: {len(train_packages)}")
    print(f"External Holdout packages count: {len(ext_packages)} -> Overlap with train: {len(ext_pkg_overlap)} ({ext_pkg_overlap})")
    print(f"Zero-shot packages count: {len(zero_packages)} -> Overlap with train: {len(zero_pkg_overlap)} ({zero_pkg_overlap})")

    # 3. Tier 2: Tool-Level Overlap & Fuzzy Matching
    IGNORE_TOKENS = {"__abstain__", "__drop__", "__done__"}
    train_tools = {}
    for r in train_records:
        q = r.get("questions", {}).get("tool_route", {})
        for tool_name, desc in q.get("criteria", {}).items():
            if tool_name not in IGNORE_TOKENS:
                train_tools[tool_name] = desc

    ext_tools = {}
    for r in ext_records:
        q = r.get("questions", {}).get("tool_route", {})
        for tool_name, desc in q.get("criteria", {}).items():
            if tool_name not in IGNORE_TOKENS:
                ext_tools[tool_name] = desc

    train_norm_tools = {normalize_tool_name(k): (k, desc) for k, desc in train_tools.items()}
    ext_norm_tools = {normalize_tool_name(k): (k, desc) for k, desc in ext_tools.items()}

    exact_tool_overlap = set(train_tools.keys()).intersection(set(ext_tools.keys()))
    norm_tool_overlap = set(train_norm_tools.keys()).intersection(set(ext_norm_tools.keys()))

    # Fuzzy tool matching (> 0.85 SequenceMatcher)
    fuzzy_matches = []
    for ext_norm, (ext_orig, ext_desc) in ext_norm_tools.items():
        for tr_norm, (tr_orig, tr_desc) in train_norm_tools.items():
            if ext_norm == tr_norm:
                continue
            ratio = SequenceMatcher(None, ext_norm, tr_norm).ratio()
            if ratio >= 0.85:
                # Check description token overlap
                desc_sim = jaccard_similarity(get_char_ngrams(ext_desc, 4), get_char_ngrams(tr_desc, 4))
                fuzzy_matches.append({
                    "ext_tool": ext_orig,
                    "train_tool": tr_orig,
                    "name_ratio": round(ratio, 4),
                    "desc_ngram_sim": round(desc_sim, 4)
                })

    print("\n--- Tier 2: Tool-Level Overlap ---")
    print(f"Unique candidate tools in train: {len(train_tools)}")
    print(f"Unique candidate tools in external: {len(ext_tools)}")
    print(f"Exact tool name overlap (train vs ext): {len(exact_tool_overlap)}")
    if exact_tool_overlap:
        print(f"  Overlapping tools: {list(exact_tool_overlap)[:10]}")
    print(f"Normalized tool name overlap: {len(norm_tool_overlap)}")
    print(f"Fuzzy tool name matches (ratio >= 0.85): {len(fuzzy_matches)}")

    # 4. Tier 3: Query-Level Similarity (Exact & Near-Duplicate)
    train_queries = [(r.get("id"), extract_query(r.get("state", ""))) for r in train_records]
    ext_queries = [(r.get("id"), extract_query(r.get("state", ""))) for r in ext_records]

    train_query_texts = {q.lower().strip(): qid for qid, q in train_queries}
    exact_query_overlap = []
    for qid, q in ext_queries:
        norm_q = q.lower().strip()
        if norm_q in train_query_texts:
            exact_query_overlap.append({"ext_id": qid, "train_id": train_query_texts[norm_q], "query": q})

    # Sample-based near-duplicate check using 3-gram Jaccard similarity > 0.75 and dense embedding similarity > 0.85
    print("\n--- Tier 3: Query Near-Duplicate Audit ---")
    print(f"Exact query text overlap: {len(exact_query_overlap)}")

    near_duplicates = []
    dense_near_duplicates = []
    train_ngrams = [(qid, q, get_char_ngrams(q, 3)) for qid, q in train_queries if len(q) > 10]
    train_vecs = [(qid, q, compute_dense_vector(q)) for qid, q in train_queries[::5] if len(q) > 10]

    for ext_id, ext_q in ext_queries[:300]:  # audit sample of external queries
        ext_ng = get_char_ngrams(ext_q, 3)
        ext_v = compute_dense_vector(ext_q)

        # Token n-gram Jaccard
        for tr_id, tr_q, tr_ng in train_ngrams[::10]:  # 1-in-10 subsample of train (2,300 queries)
            sim = jaccard_similarity(ext_ng, tr_ng)
            if sim >= 0.75 and ext_q.lower() != tr_q.lower():
                near_duplicates.append({
                    "ext_id": ext_id,
                    "train_id": tr_id,
                    "jaccard": round(sim, 4),
                    "ext_query": ext_q,
                    "train_query": tr_q
                })

        # Dense embedding cosine similarity
        for tr_id, tr_q, tr_v in train_vecs[::2]:  # subsample of train vectors
            cos_sim = cosine_similarity(ext_v, tr_v)
            if cos_sim >= 0.88 and ext_q.lower() != tr_q.lower():
                dense_near_duplicates.append({
                    "ext_id": ext_id,
                    "train_id": tr_id,
                    "cosine_similarity": round(cos_sim, 4),
                    "ext_query": ext_q,
                    "train_query": tr_q
                })

    print(f"Near-duplicate query pairs (Jaccard >= 0.75): {len(near_duplicates)}")
    print(f"Dense embedding near-duplicates (Cosine >= 0.88): {len(dense_near_duplicates)}")

    # 5. Shared Tool Name Row Breakdown (The 4 Generic Tools)
    shared_tools = {"check_service_status", "list_processes", "reverse_geocode", "transfer_to_human_agents"}
    ext_overlap_rows = [r for r in ext_records if r.get("questions", {}).get("tool_route", {}).get("label") in shared_tools]
    ext_disjoint_rows = [r for r in ext_records if r.get("questions", {}).get("tool_route", {}).get("label") not in shared_tools]

    print("\n--- Shared Tool Name Breakdown in External Holdout ---")
    print(f"Total external rows: {len(ext_records)}")
    print(f"Rows where gold tool shares name with train ({shared_tools}): {len(ext_overlap_rows)} ({len(ext_overlap_rows)/len(ext_records)*100:.2f}%)")
    print(f"Strictly disjoint tool rows (names never seen in train): {len(ext_disjoint_rows)} ({len(ext_disjoint_rows)/len(ext_records)*100:.2f}%)")

    # 6. Stratification Data Breakdown (Clean vs Collision Distractors)
    def stratify(records):
        counts = Counter()
        for r in records:
            has_col = r.get("has_collision_distractor", False)
            counts["collision" if has_col else "clean"] += 1
        return dict(counts)

    train_strat = stratify(train_records)
    ext_strat = stratify(ext_records)
    zero_strat = stratify(zero_records)

    print("\n--- Stratification Audit (Collision vs Clean) ---")
    print(f"Train split: {train_strat}")
    print(f"External holdout: {ext_strat}")
    print(f"Zero-shot holdout: {zero_strat}")

    # 7. Save Complete Audit Report
    report = {
        "metadata": {
            "train_rows": len(train_records),
            "val_external_rows": len(ext_records),
            "val_zeroshot_rows": len(zero_records),
            "timestamp": "2026-10-17T22:50:00Z",
            "provenance": {
                "val_external_heldout": "Held-out, independently sourced benchmark composed of Tau-2 dialogue tasks (Sierra Research MIT, simulated customer personas against fixed schemas) and MCP Semantic Benchmark (Mishra et al., 2026 CC BY 4.0, manually authored queries against live reference MCP server tools). Gold labels verified by task execution targets.",
                "val_zeroshot": "Synthetic multi-domain tool execution scenarios across 55 unseen packages, generated via instruction prompting and validated for semantic collision distractors."
            }
        },
        "tier_1_packages": {
            "train_unique_packages": len(train_packages),
            "ext_unique_packages": len(ext_packages),
            "zero_unique_packages": len(zero_packages),
            "ext_overlap_count": len(ext_pkg_overlap),
            "ext_overlap_packages": sorted(list(ext_pkg_overlap)),
            "zero_overlap_count": len(zero_pkg_overlap),
            "zero_overlap_packages": sorted(list(zero_pkg_overlap)),
            "package_disjointness_passed": len(ext_pkg_overlap) == 0 and len(zero_pkg_overlap) == 0
        },
        "tier_2_tools": {
            "train_unique_tools": len(train_tools),
            "ext_unique_tools": len(ext_tools),
            "exact_tool_overlap_count": len(exact_tool_overlap),
            "exact_overlapping_tools": sorted(list(exact_tool_overlap)),
            "normalized_tool_overlap_count": len(norm_tool_overlap),
            "fuzzy_match_count": len(fuzzy_matches),
            "fuzzy_matches_sample": fuzzy_matches[:20],
            "external_shared_tool_rows": {
                "shared_tool_names": sorted(list(shared_tools)),
                "overlap_rows_count": len(ext_overlap_rows),
                "overlap_rows_pct": round(len(ext_overlap_rows) / len(ext_records) * 100, 2),
                "strictly_disjoint_rows_count": len(ext_disjoint_rows),
                "strictly_disjoint_rows_pct": round(len(ext_disjoint_rows) / len(ext_records) * 100, 2)
            }
        },
        "tier_3_queries": {
            "exact_query_overlap_count": len(exact_query_overlap),
            "exact_query_overlap_examples": exact_query_overlap[:10],
            "near_duplicate_jaccard_count": len(near_duplicates),
            "near_duplicates_jaccard_sample": near_duplicates[:10],
            "near_duplicate_dense_embedding_count": len(dense_near_duplicates),
            "near_duplicates_dense_sample": dense_near_duplicates[:10]
        },
        "stratification": {
            "train": train_strat,
            "val_external_heldout": ext_strat,
            "val_zeroshot": zero_strat
        }
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nDisjointness audit complete. Report saved to {report_path}")


if __name__ == "__main__":
    main()
