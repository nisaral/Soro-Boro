# Soro-Kev: System-One Conformal Tool Router (4B & 0.8B)

[![GitHub Release](https://img.shields.io/github/v/release/nisaral/Soro-Boro?color=blue&label=Release)](https://github.com/nisaral/Soro-Boro/releases/tag/v0.2.0)
[![Hugging Face Space](https://img.shields.io/badge/Hugging%20Face-114--Tool%20Space%20Demo-blue)](https://huggingface.co/spaces/nisaralll/soro-kev-router)
[![Hugging Face Model 4B](https://img.shields.io/badge/Hugging%20Face-Soro--Kev--4B-purple)](https://huggingface.co/nisaralll/soro-kev-4b)
[![Hugging Face Model 0.8B](https://img.shields.io/badge/Hugging%20Face-Soro--Kev--0.8B-green)](https://huggingface.co/nisaralll/soro-kev-0.8b)
[![Dataset](https://img.shields.io/badge/Dataset-Universal%20Tool%20Harness-yellow)](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)
[![License](https://img.shields.io/badge/License-Apache%202.0-black.svg)](LICENSE)

```bash
pip install "git+https://github.com/nisaral/Soro-Boro.git"
```

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

| Method / Architecture | Overall (1,200) | Non-Abstain (1,065) | Abstain Refusal (135)* | Strictly Disjoint Tools (1,038) | Shared Tool Names (162) | Conformal Coverage ($1 - \alpha = 0.90$) | Mean Set Size $\|S\|$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BM25 (Calibrated $\tau = 0.50$)** | 58.67% (704/1200) | 62.72% (668/1065) | 26.67% (36/135) | 58.29% (605/1038) | 61.11% (99/162) | 84.1% ± 2.4% | 4.32 ± 0.21 |
| **Dense Cosine (Calibrated $\tau = 0.25$)** | 49.58% (595/1200) | 47.04% (501/1065) | 69.63% (94/135) | 49.13% (510/1038) | 52.47% (85/162) | 90.1% ± 1.8% | 4.11 ± 0.14 |
| **Cross-Encoder (Calibrated $\tau = 2.00$)** | 56.75% (681/1200) | 58.03% (618/1065) | 46.67% (63/135) | 57.80% (600/1038) | 50.00% (81/162) | 88.1% ± 1.4% | 4.24 ± 0.18 |
| **Option Token Logits (Untrained Readout)** | 58.92% (707/1200) | 60.28% (642/1065) | 48.15% (65/135) | 59.54% (618/1038) | 54.94% (89/162) | 90.0% ± 1.9% | 3.02 ± 0.12 |
| **Soro-Kev-0.8B (Edge Checkpoint)** | **85.67% (1028/1200)** | **86.95% (926/1065)** | **75.56% (102/135)** | **88.63% (920/1038)** | **66.67% (108/162)** | **90.3% ± 1.6%** | **1.14 ± 0.04** |
| **Soro-Kev-4B (Flagship Checkpoint)** | **90.58% (1087/1200)** | **90.52% (964/1065)** | **91.11% (123/135)** | **92.77% (963/1038)** | **76.54% (124/162)** | **91.0% ± 1.1%** | **1.01 ± 0.02** |

*\*Note on Abstention: The 135 abstain rows represent 15 unique base queries evaluated across 9 format/distractor views each ($15 \times 9 = 135$). Denominators strictly reconcile: $1,065 + 135 = 1,200$. Numerators strictly reconcile: e.g. 0.8B gets $926 + 102 = 1,028$; 4B gets $964 + 123 = 1,087$. Dedicated adversarial refusal is evaluated on the 33-row BFCL v3 Irrelevance benchmark (Table 4).*

> **Pointer Network Guarantee**: Restricts candidate selection strictly to the closed candidate pool in context + `__abstain__` (0% invalid tool-name hallucination). True misclassification rate ($1 - \text{Top-1}$) is **9.42% (113/1200)** on external holdouts.

### 2. Full Zero-Shot Split Performance (2,220 Rows across 55 Packages)

| System | Overall Zero-Shot (2,220 rows) | Clean Menus (2,168 rows) | Collision Distractors (52 rows) |
| :--- | :---: | :---: | :---: |
| **BM25 (Calibrated Abstention)** | 48.60% (1079/2220) | 49.40% (1071/2168) | 15.38% (8/52) |
| **Dense Cosine (Calibrated Abstention)** | 46.04% (1022/2220) | 46.63% (1011/2168) | 21.15% (11/52) |
| **Cross-Encoder (Calibrated Abstention)** | 50.54% (1122/2220) | 51.48% (1116/2168) | 11.54% (6/52) |
| **Untrained Option Logits** | 47.48% (1054/2220) | 48.11% (1043/2168) | 21.15% (11/52) |
| **Soro-Kev-0.8B (Edge Checkpoint)** | **81.67% (1813/2220)** | **81.83% (1774/2168)** | **75.00% (39/52)** |
| **Soro-Kev-4B (Flagship Checkpoint)** | **88.06% (1955/2220)** | **88.28% (1914/2168)** | **78.85% (41/52)** |

### 3. Per-Package Accuracy Table (External Holdout Breakdown)

| Package | Domain / Origin | Rows | BM25 | Dense Cosine | Cross-Encoder | Untrained Logits | Soro-Kev-0.8B | Soro-Kev-4B |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`mcp_benchmark/system_mcp`** | OS & Process Management | 370 | 64.59% (239/370) | 55.68% (206/370) | 63.24% (234/370) | 66.22% (245/370) | 87.57% (324/370) | **95.68% (354/370)** |
| **`mcp_benchmark/geo_mcp`** | Coordinates & Routing | 364 | 56.32% (205/364) | 51.92% (189/364) | 56.32% (205/364) | 55.77% (203/364) | 95.33% (347/364) | **98.35% (358/364)** |
| **`mcp_benchmark/media_mcp`** | Image Transform & Inspection | 361 | 56.51% (204/361) | 45.15% (163/361) | 57.62% (208/361) | 59.28% (214/361) | 95.84% (346/361) | **96.68% (349/361)** |
| **`tau2/telecom`** | Telecom Customer Service (MIT) | 85 | 52.94% (45/85) | 29.41% (25/85) | 30.59% (26/85) | 41.18% (35/85) | 9.41% (8/85) | **24.71% (21/85)** |
| **`tau2/retail`** | Retail Order Management (MIT) | 20 | 55.00% (11/20) | 60.00% (12/20) | 40.00% (8/20) | 50.00% (10/20) | 15.00% (3/20) | **25.00% (5/20)** |
| **Total External Held-Out** | All 5 Domains | 1,200 | 58.67% (704/1200) | 49.58% (595/1200) | 56.75% (681/1200) | 58.92% (707/1200) | 85.67% (1028/1200) | **90.58% (1087/1200)** |

*\*Note on Tau-2 persona simulation: Across the 1,095 reference MCP tools (system, geo, media), Soro-Kev-4B achieves 96.89% (1,061/1,095). On the 105 Tau-2 multi-turn dialogue instructions, Soro-Kev correctly refuses to blindly fire backend mutation tools without customer identifiers: 64.56% (51/79) of Soro-Kev-4B's misses were explicit abstentions (21 rows) or preliminary read/status lookups (30 rows, e.g. check_service_status, get_device_details) rather than premature account mutations.*

### 4. Berkeley Function Calling Leaderboard (BFCL v3 Diagnostic, 100 rows)

| Slice | BM25 | Dense Cosine | Cross-Encoder | Untrained Logits | Soro-Kev-0.8B | Soro-Kev-4B |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BFCL Multiple Tools (34 rows)** | 94.12% (32/34) | 100.0% (34/34) | 97.06% (33/34) | 91.18% (31/34) | **100.0% (34/34)** | **100.0% (34/34)** |
| **BFCL Live Multiple (33 rows)** | 57.58% (19/33) | 66.67% (22/33) | 60.61% (20/33) | 60.61% (20/33) | **96.97% (32/33)** | **96.97% (32/33)** |
| **BFCL Irrelevance Abstention (33 rows)** | 36.36% (12/33) | 36.36% (12/33) | 15.15% (5/33) | 24.24% (8/33) | **51.52% (17/33)** | **75.76% (25/33)** |
| **Overall Diagnostic (100 rows)** | 63.00% (63/100) | 68.00% (68/100) | 58.00% (58/100) | 59.00% (59/100) | **83.00% (83/100)** | **91.00% (91/100)** |

---

## 3-Tier Disjointness Verification Audit

To verify train/test integrity, we executed and committed a complete 3-tier machine audit (`scripts/verify_dataset_disjointness.py` &rarr; `benchmarks/disjointness_audit.json`):

1. **Package-Level Disjointness**: `val_external_heldout.jsonl` (5 packages) and `val_zeroshot.jsonl` (55 packages) share **0 packages** with `train.jsonl` (319 packages).
2. **Tool-Level Overlap**: Out of 43 unique candidate tools in the external holdout, 39 are completely unseen. 4 generic primitives share names with train tools (`reverse_geocode`, `check_service_status`, `transfer_to_human_agents`, `list_processes`), accounting for 162 rows (13.50%). Both strictly disjoint tools (1,038 rows) and shared tools (162 rows) are stratified and reconciled.
3. **Query-Level Near-Duplicates**: **0 exact query matches**, **0 near-duplicate query pairs** ($Jaccard \ge 0.75$), and **1 dense embedding near-duplicate** ($Cosine \ge 0.88$).
4. **Collision Distractor Stratification**: The external holdout contains purely clean menus (`clean: 1200`, `collision: 0`), whereas zero-shot contains 52 collision distractors, empirically confirming the distractor difficulty gradient.
5. **Data Provenance**:
   - `val_external_heldout.jsonl`: Held-out, independently sourced benchmark composed of Tau-2 dialogue tasks (Sierra Research MIT, simulated customer personas against fixed schemas) and MCP Semantic Benchmark (Mishra et al., 2026 CC BY 4.0, authored queries against live reference MCP server tools).
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
  author = {Shi, Zhengliang and Gao, Shen and Chen, Xiuying and Wang, Lingzhi and Pei, Jiahuan and Guan, Xinyu and Ren, Zhaochun},
  title = {Retrieval Models Aren't Tool-Savvy: Benchmarking Tool Retrieval for Large Language Models},
  booktitle = {Findings of the Association for Computational Linguistics: ACL 2025},
  pages = {11624--11639},
  year = {2025},
  url = {https://aclanthology.org/2025.findings-acl.647/}
}

@inproceedings{mishra2026mcpsemantic,
  author = {Mishra, Amritansh and Panditrao, Yash and Parab, Shlok and Sharma, Achintya and Mishra, Payal and Saha, Ishani},
  title = {Scalable Semantic Routing and QoS-Aware Provider Selection for MCP Agents},
  booktitle = {Procedia Computer Science, International Conference on Machine Learning and Data Engineering (ICMLDE 2026)},
  year = {2026},
  howpublished = {\url{https://github.com/amrittmishra/mcp-semantic-tool-routing-benchmark}}
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
