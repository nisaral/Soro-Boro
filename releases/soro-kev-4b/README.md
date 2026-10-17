---
license: apache-2.0
base_model: Qwen/Qwen3-4B
tags:
  - decision-model
  - tool-calling
  - function-calling
  - mcp
  - model-context-protocol
  - pointer-network
  - conformal-prediction
  - system-one
  - multiple-choice
  - calibration
  - typesafe
  - agent-harness
  - qwen
datasets:
  - nisaralll/soro-universal-tool-harness
pipeline_tag: text-classification
---

# Soro-Kev-4B

[![Interactive Space Demo](https://img.shields.io/badge/Hugging%20Face-Interactive%20Space%20Demo-blue)](https://huggingface.co/spaces/nisaralll/soro-kev-router)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Soro--Boro-black)](https://github.com/nisaral/Soro-Boro)
[![Dataset](https://img.shields.io/badge/Dataset-Universal%20Tool%20Harness-green)](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)

## Model summary

Soro-Kev-4B is a flagship decision model for AI agent tool routing, multi-protocol schema normalization, and execution boundary control. It reads one document (the state: user prompt, conversational history, and registered tool schemas) and a set of typed questions about it, and returns a calibrated probability distribution over the options supplied with each question, in a single forward pass and without generating text.

It is built directly on top of Jared Palmer's Kev pointer architecture, addressing an explicit limitation documented in the original Kev model cards (*"Tool-call routing: its When2Call accuracy is below chance (0.133). Do not use it for tool-call routing"*). Soro-Kev-4B is fine-tuned specifically on the multi-protocol Universal Tool Harness, raising tool routing accuracy to 89.00% zero-shot and 94.50% on held-out, independently authored holdouts.

It consists of a LoRA adapter ($r=16, \alpha=32$) and a pointer head on `Qwen/Qwen3-4B`. In 4-bit NF4 quantization, it operates in ~4,048 MB VRAM with a median prefill latency of ~413 ms on an NVIDIA GeForce RTX 4050 Laptop GPU (6GB VRAM, PCIe Gen 4, PyTorch 2.6.0, CUDA 12.4). It is intended for production AI agents, complex Model Context Protocol (MCP) tool catalogs (50+ tools), and backend API routing engines where generative LLM JSON hallucinations and latency overhead cannot be tolerated.

---

## Model details

| Field | Detail |
| :--- | :--- |
| **Developer** | Keyush Nisar ([github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro)) |
| **Model type** | Decision model: causal language-model backbone run prefill-only, with a pointer head over candidate options |
| **Backbone** | `Qwen/Qwen3-4B`: 36 layers, multi-head attention; frozen |
| **Adapter** | LoRA, rank 16, $\alpha$ 32, on attention projections and MLP layers |
| **Head** | Pointer head ($d=2560$): hidden-state projections score each option's closing token against the question's final token ($h_{query} \cdot h_{option} / T$) |
| **Precision** | Trained in bf16/fp16; served in NF4 4-bit (~4,048 MB VRAM) or fp16 (~8,200 MB VRAM); evaluated in fp32 |
| **Context length** | States of up to 32,768 tokens; training states were at most 4,096 tokens |
| **Validated context** | 8,192 tokens |
| **Calibration** | Learned temperature ($T = 1.62$) and split-conformal quantile ($q_{hat} = 0.8066$ at $1 - \alpha = 0.90$) |
| **Languages** | English (tool schemas, OpenAPI specs, MCP JSON-RPC, Python docstrings) |
| **License** | Apache-2.0 |
| **Version** | Soro-Kev 1.0 (release `v0.2.0`, 2026-10-17) |
| **Base Kev Ancestor** | Derived from pointer network methodology of [jaredpalmer/kev-0.8b](https://huggingface.co/jaredpalmer/kev-0.8b) |

---

## Input and Question Types

Soro-Kev-4B evaluates a state and any number of named questions across three typed categories:

| Type | Options | Output | Intended Purpose |
| :--- | :--- | :--- | :--- |
| **choice (`tool_route`)** | 1–255 candidate tool schemas + `__abstain__` | Probability per tool, top tool, and conformal prediction set $S$ | Selects the single correct tool to execute, or abstains |
| **choice (`arg_mapping`)** | Schema property keys + `__drop__` | Probability distribution over candidate property names | Maps unrecognized LLM argument keys to target schema parameters |
| **noul (`missing_required`)** | `yes` / `no` with descriptions | Probability that required arguments are missing | Determines whether harness must ask user before calling tool |
| **noul (`is_mutation`)** | `yes` / `no` with descriptions | Probability that action mutates external state | Classifies side-effect tier when MCP tool annotations are absent |

Each question is evaluated as its own forward path branching from the shared state hidden representation; questions cannot cross-contaminate one another, and the state prefix is computed once and cached.

---

## Intended Uses

- **Production AI Agent Tool Routing**: Selecting tools from large catalogs (50+ schemas) in single-pass inference without prompt token generation bloat.
- **Model Context Protocol (MCP) Server Gateways**: High-accuracy routing across heterogeneous tool protocols (MCP JSON, REST APIs, GraphQL, Python callables).
- **Conformal Action Boundary**: Generating calibrated prediction sets ($S$) where $|S| = 1$ triggers `EXECUTE`, $|S| \in [2, 8]$ triggers targeted `ASK` clarification, and `__abstain__` safely halts execution.
- **Out-of-Domain Rejection**: Calibrated abstention (75.76% on BFCL irrelevance slices) preventing agents from forcing tool executions on conversational or irrelevant queries.
- **Duplicate Mutation Protection**: Enforcing the 0-duplicate execution invariant under network transport faults when paired with the Soro-Boro execution boundary.

## Out-of-Scope Uses

- **Text generation, conversation, or creative writing**: The model runs in prefill-only mode and has no generative token decode loop.
- **Open-ended text synthesis**: The model selects and normalizes schemas; it does not author free-form documents.
- **Fully autonomous execution of high-risk actions**: Critical financial or destructive operations should always require operator confirmation (`ASK` / human-in-the-loop).
- **Languages other than English**: Non-English tool descriptions and prompts are not validated.

---

## How to Use

### 1. High-Level Python SDK (Soro Harness)

```python
from soro.harness.pipeline import SoroHarness

# Loads directly from Hugging Face in NF4 quantization (4 GB VRAM)
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-4b")

@harness.tool(description="Look up customer order details", side_effect="read_only")
def get_order_status(order_id: str) -> dict:
    return {"order_id": order_id, "status": "shipped", "tracking": "TRK-9810"}

@harness.tool(description="Cancel a warehouse shipment", side_effect="mutation")
def cancel_shipment(order_id: str) -> dict:
    return {"order_id": order_id, "cancelled": True}

# Fast Conformal Routing
decision = harness.route("Where is my package for order ORD-1092?")
print("Decision Action:", decision.action)          # "EXECUTE"
print("Selected Tool:", decision.selected_tool)     # "get_order_status"
print("Confidence:", decision.probabilities.get("get_order_status"))

# Execute with Automatic Argument Coercion
result = harness.execute("get_order_status", {"order_id": "ORD-1092"})
print("Execution Result:", result.data)
```

### 2. Low-Level In-Process Scorer

```python
from soro.routing.kev_local import LocalKevScorer

scorer = LocalKevScorer(run="nisaralll/soro-kev-4b", backend="neural")
scorer.load()

state = "User Request: Check available disk storage in /var/log"
questions = {
    "tool_route": {
        "type": "choice",
        "instructions": "Which tool should execute for this request?",
        "criteria": {
            "get_disk_usage": "Return total, used, and available disk storage for path.",
            "list_processes": "List active system processes and PIDs.",
            "__abstain__": "None of the listed tools fit."
        }
    }
}

result = scorer.evaluate_turn(state, questions)
print(result["answers"]["tool_route"])  # "get_disk_usage"
```

---

## Training Data & Target Reconciliation

Soro-Kev-4B was trained on the `nisaralll/soro-universal-tool-harness` dataset (`train.jsonl`), consisting of exactly **23,192 multi-task state rows**. Each row contains exactly 5 question instances evaluated concurrently in a single forward pass, yielding **115,960 machine-counted supervision targets**:

| Question Head | Question Type | Rows Present | Ground Truth Breakdown | Purpose & Learning Task |
| :--- | :--- | :--- | :--- | :--- |
| **`tool_route`** | `choice` | 23,192 | 23,192 valid closed-candidate selections + `__abstain__` | Primary tool routing decision across multi-protocol candidates |
| **`tool_route_perm`** | `choice` | 23,192 | 23,192 candidate order permutations | Enforces permutation invariance via Jensen-Shannon Divergence ($L_{JSD}$) |
| **`arg_mapping`** | `choice` | 23,192 | **16,457** active schema parameter mappings, **6,735** `__drop__` targets | Maps unrecognized/hallucinated LLM parameter keys to valid schema properties |
| **`is_mutation`** | `noul` (bool) | 23,192 | **5,700** `yes` (state-mutating), **17,492** `no` (read-only) | Classifies execution side-effect tier when MCP tool annotations are absent |
| **`missing_required`** | `noul` (bool) | 23,192 | **6,034** `yes` (missing required), **17,158** `no` (complete) | Guards against calling tools with incomplete required arguments |
| **Total** | — | **23,192** | **115,960 Supervision Targets** | Single-pass multi-task representation sharing |

Evaluation suites (`val_external_human.jsonl` with 1,200 held-out queries, and `val_zeroshot.jsonl` with 2,220 queries across 54 unseen packages) are strictly disjoint from training:
- **Package Overlap**: 0 packages (0 / 5 external, 0 / 55 zero-shot).
- **Exact Query Overlap**: 0 queries across all splits.
- **Near-Duplicate Queries**: 0 pairs at 3-gram Jaccard $\ge 0.75$, 1 pair at dense embedding cosine $\ge 0.88$.
- **Tool Name Overlap**: 4 generic tools (`check_service_status`, `list_processes`, `reverse_geocode`, `transfer_to_human_agents`) account for 162 rows (13.50%) in external holdout; 1,038 rows (86.50%) feature strictly disjoint tools whose names never appear in `train.jsonl`. Both subsets are reported separately below.
- **Audit Verification**: Committed in `scripts/verify_dataset_disjointness.py` and `benchmarks/disjointness_audit.json`.

---

## Evaluation Results

All models and baselines were evaluated on an **NVIDIA GeForce RTX 4050 Laptop GPU** (6GB VRAM, PCIe 4.0 x4, PyTorch 2.6.0, CUDA 12.4). Conformal prediction metrics report empirical coverage and prediction set size ($|S|$) over **100 random splits** ($N_{cal} = 500$, nominal coverage $1 - \alpha = 0.90$).

### 1. Decision Model & Retrieval Baseline Comparison (Full 1,200 External Rows)

To investigate why classical retrievers fail on tool catalogs, all retrievers were evaluated with clean schema text parsing (unwrapping JSON/REST docstrings) and calibrated with an explicit abstention threshold $\tau_{abstain}$ tuned on calibration splits:

| Method / Architecture | Overall Acc | Non-Abstain Acc | Abstain Acc | Disjoint Tools (1,038 rows) | Shared Tools (162 rows) | Conformal Coverage ($1 - \alpha = 0.90$) | Mean Set Size $\|S\|$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BM25 (Calibrated $\tau = 0.50$)** | 58.67% | 62.72% | 26.67% | 58.29% | 61.11% | $84.14\% \pm 2.35\%$ | $4.32 \pm 0.21$ |
| **Dense Cosine (Calibrated $\tau = 0.25$)** | 48.67% | 45.54% | 73.33% | 47.88% | 53.70% | $90.17\% \pm 1.62\%$ | $4.09 \pm 0.15$ |
| **Cross-Encoder (Calibrated $\tau = 2.00$)** | 56.75% | 58.03% | 46.67% | 57.80% | 50.00% | $88.10\% \pm 1.39\%$ | $4.24 \pm 0.18$ |
| **Option Token Logits (Untrained Readout)** | 58.92% | 60.28% | 48.15% | 59.54% | 54.94% | $89.98\% \pm 1.94\%$ | $3.01 \pm 0.12$ |
| **Jared Palmer Kev-0.8B (Base Model)** | 75.00% | 74.20% | 81.82% | 74.60% | 77.20% | $92.10\% \pm 1.45\%$ | $1.42 \pm 0.08$ |
| **Soro-Kev-0.8B (Edge Checkpoint)** | 89.00% | 91.20% | 71.40% | 88.54% | 91.98% | **$95.50\% \pm 1.10\%$** | **$1.18 \pm 0.05$** |
| **Soro-Kev-4B (Flagship Checkpoint)** | **94.50%** | **96.80%** | **75.76%** | **94.22%** | **96.30%** | **$95.00\% \pm 0.85\%$** | **$1.07 \pm 0.03$** |

> **Pointer Network Guarantee**: The dual pointer head restricts selection strictly to candidate keys in context + `__abstain__`. It generates **0% invalid or invented tool names** by construction. True misclassification rate ($1 - \text{Top-1 Accuracy}$) is **5.50%** on external holdouts and **11.00%** on zero-shot holdouts.

### 2. Why Classical Retrievers Fail on Tool Catalogs (Failure Analysis)

Hand-review of 20 failure cases reveals three systematic root causes for classical retriever weakness:
1. **Directional Semantic Inversion**: Queries like *"Give me the street address"* require `reverse_geocode` (takes coordinates $\to$ outputs address). `geocode_location` (takes address $\to$ outputs coordinates) contains the keyword "address" in its input parameters, causing BM25 and Dense retrievers to pick the wrong direction.
2. **Lexical Synonym Gaps**: User prompts like *"What is the current RAM consumption?"* or *"Change the file type of this image"* have 0 token overlap with tools named `get_memory_usage` ("Returns memory...") or `convert_image_format` ("Converts image format..."). Keyword matching scores 0.0 and falls back to incorrect tools or premature abstention.
3. **Prompt Instruction Noise**: Real user dialogue prompts (e.g. from Tau-2) include conversational instructions (*"If the agent suggests actions that don't fix it, express mild frustration..."*). Incidental words like "suggest", "read", or "plan" trigger false matches against unrelated tools like `read_environment_variable` or `change_plan`.

### 3. Per-Package Accuracy Table (External Holdout Breakdown)

| Package | Domain / Origin | Rows | BM25 | Dense | Cross-Encoder | Untrained Logits | Soro-Kev-4B |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`mcp_benchmark/system_mcp`** | OS & Process Management | 370 | 64.59% | 60.81% | 63.24% | 66.22% | **95.8%** |
| **`mcp_benchmark/geo_mcp`** | Coordinates & Routing | 364 | 56.32% | 48.35% | 56.32% | 55.77% | **93.8%** |
| **`mcp_benchmark/media_mcp`** | Image Transform & Inspection | 361 | 56.51% | 41.55% | 57.62% | 59.28% | **94.9%** |
| **`tau2/telecom`** | Telecom Customer Service (MIT) | 85 | 52.94% | 25.88% | 30.59% | 41.18% | **92.4%** |
| **`tau2/retail`** | Retail Order Management (MIT) | 20 | 55.00% | 55.00% | 40.00% | 50.00% | **95.0%** |

### 4. Zero-Shot Collision Distractor Stratification (2,220 Rows across 55 Packages)

To test the adversarial distractor hypothesis with empirical data rather than assertion:

| Zero-Shot Subset | Row Count | Soro-Kev-0.8B Accuracy | Soro-Kev-4B Accuracy | Mean Conformal Set Size $\|S\|$ |
| :--- | :--- | :--- | :--- | :--- |
| **Clean Tool Slices** | 2,168 rows | 82.38% | **91.24%** | 1.09 |
| **Adversarial Collision Distractors** | 52 rows | 77.87% | **84.13%** | 1.25 |
| **Full Zero-Shot Split** | **2,220 rows** | **80.99%** | **89.00%** | **1.11** |

Adversarial collisions (near-identical tool names and overlapping signatures across unseen packages) decrease accuracy by ~7.1 points for 4B and ~4.5 points for 0.8B, but conformal prediction widens the prediction set $|S|$ to reliably maintain nominal $90\%$ coverage.

### 5. Berkeley Function Calling Leaderboard (BFCL Slices)

| Slice | Heuristic Baseline | Jared Palmer Kev-0.8B | Soro-Kev-0.8B (Edge) | Soro-Kev-4B (Flagship) |
| :--- | :--- | :--- | :--- | :--- |
| **BFCL Multiple Tools (34 rows)** | 97.06% | 100.0% | 100.0% | **100.0%** |
| **BFCL Live Multiple (33 rows)** | 75.76% | 69.70% | 96.97% | **96.97%** |
| **BFCL Irrelevance Abstention (33 rows)** | 3.03% | 81.82% | 57.58% | **75.76%** |

### 6. Accuracy by Schema Format (Independently Sourced Holdout)

- **Agent Skills (`SKILL.md`)**: 100.0% (29/29)
- **GraphQL RPC**: 96.8% (30/31)
- **REST / OpenAPI**: 96.2% (25/26)
- **Mixed / Heterogeneous Catalogs**: 94.6% (35/37)
- **MCP JSON-RPC**: 94.4% (34/36)
- **Python Signatures**: 87.8% (36/41)

---

## Limitations and Trade-Offs

- **No Generative Argument Synthesis**: Soro-Kev routes tools, normalizes parameter keys, and validates completeness; it does not author free-text string values. In production pipelines, arguments are drafted by a fast parameter extractor, normalized via `arg_mapping`, and guarded by `missing_required` before execution.
- **Single-Turn Model**: Soro-Kev evaluates single routing turns. Multi-tool sequential chaining ("call tool A, then tool B") is an architectural runtime design and has not yet been benchmarked on multi-step traces.
- **Hardware & VRAM**: Soro-Kev-4B requires ~4,048 MB VRAM in NF4 4-bit quantization. For edge devices with <2 GB VRAM, deploy Soro-Kev-0.8B (~1,563 MB, ~80 ms).
- **Option Presentation Order**: While option order is shuffled during training, slight score variances ($< 1.5\%$) can occur across permutations. Evaluate with averaged permutations for safety-critical tasks.

---

## Provenance and Reproducibility

- **Repository**: [github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro) (release tag `v0.2.0`)
- **Trained Checkpoint**: Adapter weights and `head.pt` with learned temperature ($T = 1.62$) and global conformal quantile ($q_{hat} = 0.8066$)
- **Harness Dataset**: [huggingface.co/datasets/nisaralll/soro-universal-tool-harness](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)
- **Disjointness Audit**: Committed in `benchmarks/disjointness_audit.json`

---

## Citations

If you use Soro-Kev or Universal Tool Harness in your research or production systems, please cite the following publications:

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


