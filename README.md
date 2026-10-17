# Soro-Kev: System-One Conformal Tool Router (4B & 0.8B)

[![GitHub Release](https://img.shields.io/github/v/release/nisaral/Soro-Boro?color=blue&label=Release)](https://github.com/nisaral/Soro-Boro/releases/tag/v0.2.0)
[![Hugging Face Space](https://img.shields.io/badge/Hugging%20Face-114--Tool%20Space%20Demo-blue)](https://huggingface.co/spaces/nisaralll/soro-kev-router)
[![Hugging Face Model 4B](https://img.shields.io/badge/Hugging%20Face-Soro--Kev--4B-purple)](https://huggingface.co/nisaralll/soro-kev-4b)
[![Hugging Face Model 0.8B](https://img.shields.io/badge/Hugging%20Face-Soro--Kev--0.8B-green)](https://huggingface.co/nisaralll/soro-kev-0.8b)
[![Dataset](https://img.shields.io/badge/Dataset-Universal%20Tool%20Harness-yellow)](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)
[![License](https://img.shields.io/badge/License-Apache%202.0-black.svg)](LICENSE)

**Soro-Kev** is an open-weights decision model family (4B flagship & 0.8B edge) for ultra-fast AI agent tool routing, schema normalization, and execution boundary control.

Tool routing is fundamentally a **closed-set ranking and classification problem, not an open-ended text generation problem.** Asking a large autoregressive language model to emit tool selection JSON strings introduces 1,500–3,500 ms of latency, context bloat over 50+ tool schemas, and non-zero tool-name hallucination risk.

Soro-Kev builds directly on Jared Palmer's [Kev decision model architecture](https://huggingface.co/jaredpalmer/kev-0.8b), adapting pointer networks for heterogeneous tool routing:
- **Zero Invalid Tool Names**: Pointer scoring mathematically bounds outputs to registered tool schemas or `__abstain__`.
- **Sub-420ms Latency**: Evaluates catalogs in a single prefill forward pass on consumer hardware (NVIDIA RTX 4050 Laptop GPU).
- **Split-Conformal Action Boundaries**: Returns calibrated prediction sets ($S$) where $|S| = 1 \implies \text{EXECUTE}$, $|S| \in [2, 8] \implies \text{ASK}$, and `__abstain__` halts execution.

```text
User State + Tool Catalog
  [0] get_weather: {location: str}
  [1] search_database: {query: str}
  [2] __abstain__: none of these fit
        │
        h_query · h_candidate / Temperature
        │
        Split Conformal Set S (Nominal 90% Coverage)
          ├── |S| = 1 and tool != __abstain__  ──> EXECUTE (immediate dispatch)
          ├── |S| ∈ [2, 8]                     ──> ASK (targeted user clarification)
          └── Top = __abstain__ or |S| empty   ──> ABSTAIN (out-of-domain safe halt)
```

---

## Quickstart & Installation

Install directly from GitHub into your environment:

```bash
pip install git+https://github.com/nisaral/Soro-Boro.git
```

Or for local development:

```bash
git clone https://github.com/nisaral/Soro-Boro.git
cd Soro-Boro
pip install -e .
```

### 5-Line Python SDK

```python
from soro.harness.pipeline import SoroHarness

# Loads directly from Hugging Face in NF4 4-bit (4 GB VRAM)
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")

@harness.tool(description="Look up customer order status", side_effect="read_only")
def get_order_status(order_id: str) -> dict:
    return {"order_id": order_id, "status": "shipped", "tracking": "TRK-9810"}

@harness.tool(description="Cancel a warehouse shipment", side_effect="mutation")
def cancel_shipment(order_id: str) -> dict:
    return {"order_id": order_id, "cancelled": True}

# Fast Conformal Routing (<420ms)
decision = harness.route("Where is my package for order ORD-1092?")
print("Action:", decision.action)          # "EXECUTE"
print("Selected Tool:", decision.selected_tool)     # "get_order_status"
print("Confidence:", decision.probabilities.get("get_order_status"))

# Execute with boundary verification
result = harness.execute("get_order_status", {"order_id": "ORD-1092"})
print("Result:", result.data)
```

---

## End-to-End Execution Flow

A router selects tools and normalizes parameter keys; it does not author free-text string values. In an end-to-end agent architecture, Soro-Kev operates as a specialized System-One layer:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Router as Soro-Kev Decision Model
    participant Extractor as Fast Argument Extractor
    participant Boundary as Soro-Boro Execution Boundary
    participant MCP as MCP Tool Server

    User->>Router: "Send $50 to Alice with note 'rent'"
    Note over Router: Single Prefill Forward Pass (~413 ms)
    Router-->>Router: tool_route: "send_payment" (conf: 0.98, |S|=1 -> EXECUTE)
    Router-->>Router: is_mutation: "yes" (mutation tier)
    
    Router->>Extractor: Pass Selected Schema ("send_payment") & Query
    Note over Extractor: Drafts raw arguments: {amt: 50, recipient: "Alice", memo: "rent"}
    Extractor-->>Router: Raw Argument Dict
    
    Note over Router: Heads: arg_mapping & missing_required
    Router-->>Router: Map keys: amt->amount, recipient->payee_id, memo->note
    Router-->>Router: Validate completeness: missing_required == "no"
    
    Router->>Boundary: Dispatch (send_payment, {amount: 50, payee_id: "Alice", note: "rent"})
    Note over Boundary: Enforces Idempotency Key & Mutation Guard
    Boundary->>MCP: JSON-RPC Call (tools/call)
    MCP-->>Boundary: Result JSON
    Boundary-->---

## Empirical Benchmark Results

All evaluations were benchmarked on a dedicated single-GPU node: **NVIDIA GeForce RTX 4050 Laptop GPU (6GB VRAM, PCIe Gen 4, PyTorch 2.6.0, CUDA 12.4)**. Conformal prediction metrics report empirical coverage and prediction set size ($|S|$) over **100 random splits** ($N_{cal} = 500$, nominal coverage $1 - \alpha = 0.90$).

### 1. Decision Model & Retrieval Baseline Comparison (Full 1,200 External Rows)

All retrievers were evaluated with clean schema text parsing and calibrated with an explicit abstention threshold $\tau_{abstain}$ tuned on calibration splits:

| Method / Architecture | Overall Acc | Non-Abstain Acc | Abstain Acc | Disjoint Tools (1,038 rows) | Shared Tools (162 rows) | Conformal Coverage ($1 - \alpha = 0.90$) | Mean Set Size $\|S\|$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BM25 (Calibrated $\tau = 0.50$)** | 58.67% | 62.72% | 26.67% | 58.29% | 61.11% | $84.14\% \pm 2.35\%$ | $4.32 \pm 0.21$ |
| **Dense Cosine (Calibrated $\tau = 0.25$)** | 48.67% | 45.54% | 73.33% | 47.88% | 53.70% | $90.17\% \pm 1.62\%$ | $4.09 \pm 0.15$ |
| **Cross-Encoder (Calibrated $\tau = 2.00$)** | 56.75% | 58.03% | 46.67% | 57.80% | 50.00% | $88.10\% \pm 1.39\%$ | $4.24 \pm 0.18$ |
| **Option Token Logits (Untrained Readout)** | 58.92% | 60.28% | 48.15% | 59.54% | 54.94% | $89.98\% \pm 1.94\%$ | $3.01 \pm 0.12$ |
| **Jared Palmer Kev-0.8B (Base Checkpoint)** | 75.00% | 74.20% | 81.82% | 74.60% | 77.20% | $92.10\% \pm 1.45\%$ | $1.42 \pm 0.08$ |
| **Soro-Kev-0.8B (Edge Checkpoint)** | **89.00%** | **91.20%** | **71.40%** | **88.54%** | **91.98%** | **$95.50\% \pm 1.10\%$** | **$1.18 \pm 0.05$** |
| **Soro-Kev-4B (Flagship Checkpoint)** | **94.50%** | **96.80%** | **75.76%** | **94.22%** | **96.30%** | **$95.00\% \pm 0.85\%$** | **$1.07 \pm 0.03$** |

> **Pointer Network Guarantee**: Restricts candidate selection strictly to the closed candidate pool in context + `__abstain__` (0% invalid tool-name hallucination). True misclassification rate ($1 - \text{Top-1}$) is **5.50%** on external holdouts and **11.00%** on zero-shot holdouts.

### 2. Full Zero-Shot Split Performance (2,220 Rows across 55 Packages)

| Evaluation Metric | Full Zero-Shot Split (1,920 Test Rows) | 200-Row Random Slice |
| :--- | :--- | :--- |
| **Soro-Kev-4B Routing Accuracy** | — | **89.00%** (Clean: 91.24%, Collision: 84.13%) |
| **Soro-Kev-0.8B Routing Accuracy** | **80.99%** (Clean: 82.38%, Collision: 77.87%) | **84.50%** |
| **Conformal Coverage** ($1 - \alpha = 0.90$) | **85.89%** (Wilson 95% CI: [0.8426, 0.8737]) | **93.00%** (4B) / **89.00%** (0.8B) |
| **Mean Conformal Prediction Set Size $\|S\|$** | **1.16** | **1.11** (4B) / **1.17** (0.8B) |
| **Argument Mapping Accuracy** | **96.56%** | **100.0%** (4B) / **99.00%** (0.8B) |
| **Mutation Detection Accuracy** | **82.60%** | **92.50%** (4B) / **88.50%** (0.8B) |

### 3. Per-Package Accuracy Table (External Holdout Breakdown)

| Package | Domain / Origin | Rows | BM25 | Dense | Cross-Encoder | Untrained Logits | Soro-Kev-4B |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`mcp_benchmark/system_mcp`** | OS & Process Management | 370 | 64.59% | 60.81% | 63.24% | 66.22% | **95.8%** |
| **`mcp_benchmark/geo_mcp`** | Coordinates & Routing | 364 | 56.32% | 48.35% | 56.32% | 55.77% | **93.8%** |
| **`mcp_benchmark/media_mcp`** | Image Transform & Inspection | 361 | 56.51% | 41.55% | 57.62% | 59.28% | **94.9%** |
| **`tau2/telecom`** | Telecom Customer Service (MIT) | 85 | 52.94% | 25.88% | 30.59% | 41.18% | **92.4%** |
| **`tau2/retail`** | Retail Order Management (MIT) | 20 | 55.00% | 55.00% | 40.00% | 50.00% | **95.0%** |

### 4. Berkeley Function Calling Leaderboard (BFCL Slices)

| Slice | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-0.8B | Soro-Kev-4B (Flagship) |
| :--- | :--- | :--- | :--- | :--- |
| **BFCL Multiple Tools (34 rows)** | 97.06% | 100.0% | 100.0% | **100.0%** |
| **BFCL Live Multiple (33 rows)** | 75.76% | 69.70% | 96.97% | **96.97%** |
| **BFCL Irrelevance Abstention (33 rows)** | 3.03% | 81.82% | 57.58% | **75.76%** |

---

## 3-Tier Disjointness Verification Audit

To verify train/test integrity, we executed and committed a complete 3-tier machine audit (`scripts/verify_dataset_disjointness.py` &rarr; `benchmarks/disjointness_audit.json`):

1. **Package-Level Disjointness**: `val_external_human.jsonl` (5 packages) and `val_zeroshot.jsonl` (55 packages) share **0 packages** with `train.jsonl` (319 packages).
2. **Tool-Level Overlap**: Out of 43 unique candidate tools in the external holdout, 39 are completely unseen. 4 generic primitives share names with train tools (`reverse_geocode`, `check_service_status`, `transfer_to_human_agents`, `list_processes`), accounting for 162 rows (13.50%). Both strictly disjoint tools (1,038 rows, 94.22% acc) and shared tools (162 rows, 96.30% acc) are verified.
3. **Query-Level Near-Duplicates**: **0 exact query matches**, **0 near-duplicate query pairs** ($Jaccard \ge 0.75$), and **1 dense embedding near-duplicate** ($Cosine \ge 0.88$).
4. **Collision Distractor Stratification**: The external holdout contains purely clean queries (`clean: 1200`, `collision: 0`), whereas zero-shot contains 52 collision distractors (clean 91.24% vs collision 84.13% on 4B), empirically confirming the distractor difficulty gradient.
5. **Data Provenance**:
   - `val_external_human.jsonl`: Tau-2 dialogue tasks (Sierra Research MIT, simulated customer personas against fixed schemas) and MCP Semantic Benchmark (Mishra et al., 2026 CC BY 4.0, manually authored queries against live reference MCP server tools).
   - `val_zeroshot.jsonl`: Multi-domain tool execution scenarios across 54 unseen packages, validated for semantic collision distractors.

---

## Training Data Structure & Exact Target Counts

`train.jsonl` contains exactly **23,192 multi-task state rows**, totaling **115,960 question-level supervision targets** across 5 concurrent heads:

| Question Head | Target Count | Ground Truth Breakdown | Purpose |
| :--- | :--- | :--- | :--- |
| `tool_route` | 23,192 | 23,192 candidate selections + `__abstain__` | Closed-choice tool routing over candidates + `__abstain__` |
| `tool_route_perm` | 23,192 | 23,192 permuted candidate orders | Enforces position invariance via Jensen-Shannon Divergence ($L_{JSD}$) |
| `arg_mapping` | 23,192 | **16,457** real schema parameter mappings, **6,735** `__drop__` targets | Maps unrecognized/hallucinated LLM parameter keys to valid schema properties |
| `missing_required` | 23,192 | **6,034** `yes` (halt/clarify), **17,158** `no` | Guards against calling tools with incomplete required arguments |
| `is_mutation` | 23,192 | **5,700** `yes` (state-mutating), **17,492** `no` (read-only) | Classifies execution side-effect tier when MCP tool annotations are absent |
| **Total Targets** | **115,960** | **Machine-Counted Ground Truth** | Single-pass multi-task representation sharing |

---

## Citations

```bibtex
@software{nisar2026sorokev,
  author = {Nisar, Keyush},
  title = {Soro-Kev: System-One Conformal Tool Router and Execution Boundary},
  year = {2026},
  publisher = {GitHub},
  howpublished = {\url{https://github.com/nisaral/Soro-Boro}},
  note = {Release v0.2.0}
}

@misc{palmer2026kev08b,
  author = {Palmer, Jared},
  title = {Kev-0.8B: a calibrated decision model on Qwen3.5-0.8B},
  year = {2026},
  howpublished = {\url{https://huggingface.co/jaredpalmer/kev-0.8b}},
  note = {Kev 1.0}
}

@inproceedings{shi2025toolret,
  author = {Shi, Jiahao and others},
  title = {ToolRet: A Benchmark for Tool Retrieval in Large Language Models},
  booktitle = {Findings of the Association for Computational Linguistics: ACL 2025},
  year = {2025}
}

@article{mo2025livemcpbench,
  author = {Mo, Guozhao and others},
  title = {LiveMCPBench: Can Agents Navigate an Ocean of MCP Tools?},
  journal = {arXiv preprint arXiv:2508.01780},
  year = {2025}
}

@inproceedings{ross2025when2call,
  author = {Ross, Hayley and Mahabaleshwarkar, Ameya Sunil and Suhara, Yoshi},
  title = {When2Call: When (not) to Call Tools},
  booktitle = {Proceedings of the 2025 Conference of the North American Chapter of the Association for Computational Linguistics (NAACL)},
  year = {2025}
}
```

## License

Apache-2.0.
