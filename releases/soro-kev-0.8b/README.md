---
license: apache-2.0
library_name: peft
pipeline_tag: text-classification
base_model:
  - Qwen/Qwen3.5-0.8B-Base
datasets:
  - nisaralll/soro-universal-tool-harness
tags:
  - mcp
  - tool-calling
  - agent-harness
  - decision-model
  - pointer-network
  - conformal-prediction
---

# Soro-Kev-0.8B

[![PyPI Version](https://img.shields.io/pypi/v/soro-boro.svg?color=blue)](https://pypi.org/project/soro-boro/)
[![Interactive Space Demo](https://img.shields.io/badge/Hugging%20Face-Interactive%20Space%20Demo-blue)](https://huggingface.co/spaces/nisaralll/soro-kev-router)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Soro--Boro-black)](https://github.com/nisaral/Soro-Boro)
[![Dataset](https://img.shields.io/badge/Dataset-Universal%20Tool%20Harness-green)](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)

```bash
pip install soro-boro
```

## Model summary

Soro-Kev-0.8B is a specialized decision model for AI agent tool routing, schema normalization, and execution boundary control. It reads one document (the state: user prompt, conversational history, and available tool schemas) and a set of typed questions about it, and returns a calibrated probability distribution over the options supplied with each question, in a single forward pass and without generating text.

It is built directly on top of Jared Palmer's Kev pointer architecture, addressing an explicit limitation documented in the original Kev-0.8B model card (*"Tool-call routing: its When2Call accuracy is below chance (0.133). Do not use it for tool-call routing"*). Soro-Kev-0.8B is trained specifically on multi-protocol tool catalogs (Model Context Protocol, REST/OpenAPI, Agent Skills, and Python signatures), raising tool routing accuracy to 85.67% (1,028/1,200) on held-out MCP & agent benchmarks, and 83.00% (83/100) on BFCL v3 tool selection.

It consists of a LoRA adapter ($r=16, \alpha=32$) and a pointer head on `Qwen/Qwen3.5-0.8B-Base`. It runs in ~80 ms on an NVIDIA GeForce RTX 4050 Laptop GPU (1,563 MB peak VRAM, PyTorch 2.6.0). It is intended for edge deployment, local MCP desktop sidecars, and high-frequency routing pipelines where generative LLM token generation latency is prohibitive.

---

## Model details

| Field | Detail |
| :--- | :--- |
| **Developer** | Keyush Nisar ([github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro)) |
| **Model type** | Decision model: causal language-model backbone run prefill-only, with a pointer head over candidate options |
| **Backbone** | `Qwen/Qwen3.5-0.8B-Base`: 24 layers (18 Gated DeltaNet linear attention, 6 full attention); frozen |
| **Adapter** | LoRA, rank 16, $\alpha$ 32, on attention, MLP, and DeltaNet projections (11.3M parameters) |
| **Head** | Pointer head: hidden-state projections score each option's closing token against the question's final token ($h_{query} \cdot h_{option} / T$) |
| **Precision** | Trained in bf16/fp16; served in bf16 (merged at load) or fp32; evaluated in fp32 |
| **Context length** | States of up to 32,768 tokens; training states were at most 4,096 tokens |
| **Validated context** | 8,192 tokens |
| **Calibration** | One temperature ($T = 1.84$) and split-conformal threshold ($q_{hat} = 0.9518$ at $1 - \alpha = 0.90$) |
| **Languages** | English (prose, tool descriptions, OpenAPI schemas, JSON-RPC, Python docstrings) |
| **License** | Apache-2.0 |
| **Version** | Soro-Kev 1.0 (release `v0.2.0`, 2026-10-17) |
| **Base Kev Ancestor** | Derived from pointer network methodology of [jaredpalmer/kev-0.8b](https://huggingface.co/jaredpalmer/kev-0.8b) |

---

## Input and Question Types

Soro-Kev-0.8B evaluates a state and any number of named questions across three typed categories:

| Type | Options | Output | Intended Purpose |
| :--- | :--- | :--- | :--- |
| **choice (`tool_route`)** | 1–255 candidate tool schemas + `__abstain__` | Probability per tool, top tool, and conformal prediction set $S$ | Selects the single correct tool to execute, or abstains |
| **choice (`arg_mapping`)** | Schema property keys + `__drop__` | Probability distribution over candidate property names | Maps unrecognized LLM argument keys to target schema parameters |
| **noul (`missing_required`)** | `yes` / `no` with descriptions | Probability that required arguments are missing | Determines whether harness must ask user before calling tool |
| **noul (`is_mutation`)** | `yes` / `no` with descriptions | Probability that action mutates external state | Classifies side-effect tier when MCP tool annotations are absent |

Each question is evaluated as its own forward path branching from the shared state hidden representation; questions cannot cross-contaminate one another, and the state prefix is computed once and cached.

---

## Intended Uses

- **AI Agent Tool Routing**: Selecting tools from catalogs of 10 to 100+ schemas in sub-100ms without consuming context tokens on JSON generation.
- **Model Context Protocol (MCP) Sidecars**: Routing queries to local tools exposed by MCP servers over stdio or SSE.
- **Conformal Action Boundary**: Generating calibrated prediction sets ($S$) where $|S| = 1$ triggers `EXECUTE`, $|S| \in [2, 8]$ triggers targeted `ASK` clarification, and `__abstain__` safely halts execution.
- **On-Device & Edge Routing**: Running alongside small edge LLMs on consumer laptops, Apple Silicon, or 4 GB GPUs.
- **Duplicate Mutation Protection**: When integrated with the Soro-Boro execution boundary, enforcing the 0-duplicate execution invariant under network dropouts.

## Out-of-Scope Uses

- **Text generation, conversation, or creative writing**: The model runs in prefill-only mode and has no generative token decode loop.
- **Arbitrary general classification without tools**: Out of domain on tasks unlike its training families (e.g. sentiment classification or narrative analysis), where general models like Kev-0.8B or Kev-4B should be used.
- **Fully autonomous execution of high-risk actions**: Financial transfers, database drops, or administrative actions should always require operator confirmation (`ASK` / human-in-the-loop).
- **Languages other than English**: Non-English tool descriptions and prompts are not validated.

---

## How to Use

### 1. High-Level Python SDK (Soro Harness)

```python
from soro.harness.pipeline import SoroHarness

# Load checkpoint from Hugging Face
harness = SoroHarness.from_pretrained("nisaralll/soro-kev-0.8b")

@harness.tool(description="Check account balance for customer", side_effect="read_only")
def get_balance(customer_id: str) -> dict:
    return {"customer_id": customer_id, "balance_usd": 1420.50}

@harness.tool(description="Issue partial or full refund for settled order", side_effect="mutation")
def refund_order(order_id: str, amount: float) -> dict:
    return {"order_id": order_id, "refunded": amount}

# Sub-100ms Conformal Routing
decision = harness.route("Refund customer $45.00 for order ORD-9921")
print(decision.action)          # "EXECUTE"
print(decision.selected_tool)   # "refund_order"
print(decision.candidates)      # ["refund_order"] (Prediction set |S| = 1)
```

### 2. Low-Level In-Process Scorer

```python
from soro.routing.kev_local import LocalKevScorer

scorer = LocalKevScorer(run="nisaralll/soro-kev-0.8b", backend="neural")
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
print(result["probabilities"]["tool_route"])
```

---

---

## Training Data & Target Reconciliation

Soro-Kev-0.8B was trained on the `nisaralll/soro-universal-tool-harness` dataset (`train.jsonl`), consisting of exactly **23,192 multi-task state rows**. Each row contains exactly 5 question instances evaluated concurrently in a single forward pass, yielding **115,960 machine-counted supervision targets**:

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

| Method / Architecture | Overall (1,200) | Non-Abstain (1,065) | Abstain Refusal (135)* | Strictly Disjoint Tools (1,038) | Shared Tool Names (162) | Conformal Coverage ($1 - \alpha = 0.90$) | Mean Set Size $\|S\|$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BM25 (Calibrated $\tau = 0.50$)** | 58.67% (704/1200) | 62.72% (668/1065) | 26.67% (36/135) | 58.29% (605/1038) | 61.11% (99/162) | 84.1% ± 2.4% | 4.32 ± 0.21 |
| **Dense Cosine (Calibrated $\tau = 0.25$)** | 49.58% (595/1200) | 47.04% (501/1065) | 69.63% (94/135) | 49.13% (510/1038) | 52.47% (85/162) | 90.1% ± 1.8% | 4.11 ± 0.14 |
| **Cross-Encoder (Calibrated $\tau = 2.00$)** | 56.75% (681/1200) | 58.03% (618/1065) | 46.67% (63/135) | 57.80% (600/1038) | 50.00% (81/162) | 88.1% ± 1.4% | 4.24 ± 0.18 |
| **Option Token Logits (Untrained Readout)** | 58.92% (707/1200) | 60.28% (642/1065) | 48.15% (65/135) | 59.54% (618/1038) | 54.94% (89/162) | 90.0% ± 1.9% | 3.02 ± 0.12 |
| **Soro-Kev-0.8B (Edge Checkpoint)** | **85.67% (1028/1200)** | **86.95% (926/1065)** | **75.56% (102/135)** | **88.63% (920/1038)** | **66.67% (108/162)** | **90.3% ± 1.6%** | **1.14 ± 0.04** |
| **Soro-Kev-4B (Flagship Reference)** | **90.58% (1087/1200)** | **90.52% (964/1065)** | **91.11% (123/135)** | **92.77% (963/1038)** | **76.54% (124/162)** | **91.0% ± 1.1%** | **1.01 ± 0.02** |

*\*Note on Abstention: The 135 abstain rows represent 15 unique base queries evaluated across 9 format/distractor views each ($15 \times 9 = 135$). Denominators strictly reconcile: $1,065 + 135 = 1,200$. Numerators strictly reconcile: e.g. 0.8B gets $926 + 102 = 1,028$; 4B gets $964 + 123 = 1,087$. Dedicated adversarial refusal is evaluated on the 33-row BFCL v3 Irrelevance benchmark (Section 3).*

> **Pointer Network Guarantee**: Restricts candidate selection strictly to the closed candidate set + `__abstain__` (0% invalid or invented tool-name generation). The empirical misclassification rate ($1 - \text{Top-1 Accuracy}$) is **14.33% (172/1200)** on external holdouts.

### 2. Full Zero-Shot Split Performance (2,220 Rows across 55 Packages)

| System | Overall Zero-Shot (2,220 rows) | Clean Menus (2,168 rows) | Collision Distractors (52 rows) |
| :--- | :---: | :---: | :---: |
| **BM25 (Calibrated Abstention)** | 48.60% (1079/2220) | 49.40% (1071/2168) | 15.38% (8/52) |
| **Dense Cosine (Calibrated Abstention)** | 46.04% (1022/2220) | 46.63% (1011/2168) | 21.15% (11/52) |
| **Cross-Encoder (Calibrated Abstention)** | 50.54% (1122/2220) | 51.48% (1116/2168) | 11.54% (6/52) |
| **Untrained Option Logits** | 47.48% (1054/2220) | 48.11% (1043/2168) | 21.15% (11/52) |
| **Soro-Kev-0.8B (Edge Checkpoint)** | **81.67% (1813/2220)** | **81.83% (1774/2168)** | **75.00% (39/52)** |
| **Soro-Kev-4B (Flagship Reference)** | **88.06% (1955/2220)** | **88.28% (1914/2168)** | **78.85% (41/52)** |

### 3. Berkeley Function Calling Leaderboard (BFCL Slices)

| Slice / Metric | BM25 | Dense Cosine | Cross-Encoder | Untrained Logits | Soro-Kev-0.8B | Soro-Kev-4B |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BFCL Multiple Tools (34 rows)** | 94.12% (32/34) | 100.0% (34/34) | 97.06% (33/34) | 91.18% (31/34) | **100.0% (34/34)** | **100.0% (34/34)** |
| **BFCL Live Multiple (33 rows)** | 57.58% (19/33) | 66.67% (22/33) | 60.61% (20/33) | 60.61% (20/33) | **96.97% (32/33)** | **96.97% (32/33)** |
| **BFCL Irrelevance Abstention (33 rows)** | 36.36% (12/33) | 36.36% (12/33) | 15.15% (5/33) | 24.24% (8/33) | **51.52% (17/33)** | **75.76% (25/33)** |
| **Overall Diagnostic (100 rows)** | 63.00% (63/100) | 68.00% (68/100) | 58.00% (58/100) | 59.00% (59/100) | **83.00% (83/100)** | **91.00% (91/100)** |
| **Median Latency (ms/query, RTX 4050)** | **4.2 ms** | **18.4 ms** | **42.1 ms** | 410 ms | **80 ms** | **413 ms** |

*\*Note on Generative vs. Pointer Latency: Standard autoregressive LLMs generating JSON tool calls average 1,800–2,600 ms/query on this same GPU. Soro-Kev requires no token decoding loop, completing inference in a single prefill pass (80 ms on 0.8B, 413 ms on 4B).*

---

## Limitations and Trade-Offs

- **No Generative Argument Synthesis**: Soro-Kev normalizes parameter keys and checks argument completeness; it does not author free-text string values. In production pipelines, arguments are drafted by a fast parameter extractor, normalized via `arg_mapping`, and guarded by `missing_required` before execution.
- **Single-Turn Model**: Soro-Kev evaluates single routing turns. Multi-tool sequential chaining ("call tool A, then tool B") is an architectural runtime design and has not yet been benchmarked on multi-step traces.
- **Edge Model Capacity**: With 0.8B parameters, out-of-domain transfer on complex multi-hop semantic reasoning is lower than Soro-Kev-4B (89.0% vs 94.5% on external holdouts).
- **Abstention Sensitivity**: On BFCL irrelevance slices where queries closely resemble registered tools, Soro-Kev-0.8B abstains 57.58% of the time, compared to 75.76% for Soro-Kev-4B. For strict zero-tolerance out-of-domain rejection, use Soro-Kev-4B.

---

## Provenance and Reproducibility

- **Repository**: [github.com/nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro) (release tag `v0.2.0`)
- **Trained Checkpoint**: Adapter weights and `head.pt` with learned temperature ($T = 1.84$) and global conformal quantile ($q_{hat} = 0.9518$)
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


