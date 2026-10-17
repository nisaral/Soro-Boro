# Soro progress since the approved plan

Scope: from the middleware-first / wrap-only plan (rename to Soro, then framework + routing research) through the last completed eval round. Does **not** include conformal shortlists or later steps (those were proposed but not started).

## Product identity (locked)

**Soro** = agent framework whose MVP kernel is the tool boundary:

> Middleware between the agent and tools. Deterministic filter and shortlist. Verify-before-replay on unknown ack. No LLM on the mutating path. Abstain when unsure.

- Package: `veyra/python/src/soro` (`pip` package / distribution name: `soro-boro`, importable as `soro`)
- Public API: `Soro`, `wrap`, `@soro.tool`, `route`, `register_mcp` / `register_http`, optional thin `run`
- Not a LangGraph replacement; wraps LangGraph / OpenAI Agents / raw chatbots
- Veyra brand retired for this product (name collisions elsewhere)

## What shipped in code

| Layer | Location | Status |
|---|---|---|
| Wrap + UNKNOWN_ACK | `production/production_layer.py` | Working; five-minute charge/verify test green |
| Deterministic / scale router | `routing/scale.py` | Contract filter → shortlist → EXECUTE/ASK/ABSTAIN/DENY |
| Framework surface | `framework/{router,agent}.py` | Thin loop over shortlist |
| Protocols | `routing/protocol_v1.py`, `protocol_v2.py` | v1 invalidated; v2 frozen before scores |
| Public bench harness | `routing/public_bench.py`, `public_encoders.py` | Authors’ FAISS + local MiniLM |
| Local Kev | `routing/kev_local.py` | Loads HF `jaredpalmer/kev-0.8b` on CPU |
| Eval suite | `routing/eval_*.py`, `eval_next.py` | Reports under `veyra/reports/` |
| Website | `veyra/web` | Rebranded Soro; ToolMisuse +25pp quarantined |

## Eval chronology (what was wrong, what fixed it)

### Broken first suite (`routing_scale.json` — INVALIDATED)

- Shared-boilerplate synthetic catalog → every arm ≈ **0.28** R@1
- “Dense” was hashed n-grams, not neural
- Kev 6/6 on an easy overlapping split (uninformative)
- LinUCB in RRF with no learning (dragged ensemble)

### Protocol v1 (`routing_protocol_v1.json` — INVALIDATED as *semantic* evidence)

- Unique-token (`ZXQ####`) catalog: oracle ceiling 1.0
- BM25/hash ≈ 0.93–1.0; MiniLM ~0.4 (tokens are noise to MiniLM)
- Proved plumbing only; label as unit-test fixture

### Protocol v2 (`routing_protocol_v2.json` — CURRENT hard set)

- **141** real MCPAgentBench tools + **80** paraphrases with **zero** gold-name lexical overlap
- Confusable clusters locked; query golds frozen before scoring
- Self second-pass labels: 79/80 agree (1 multi-defensible)

| Arm (v2) | R@1 | R@5 | R@20 |
|---|---|---|---|
| MiniLM | **0.325** | 0.725 | **0.888** |
| Hybrid RRF | 0.24–0.26 | ~0.55–0.61 | ~0.875 |
| BM25 | 0.113 | 0.288 | 0.463 |

McNemar MiniLM vs BM25: **p ≈ 8e-5** (settled). MiniLM vs hybrid: **p ≈ 0.17** (not settled).

### Harness external validation (`routing_v2_addendum.json`)

- Authors’ cached `gemini-embedding-001` scored with our FAISS path: **483/505 = 0.9564**, `match_paper: true`
- Scoring code is correct

### Latest round (`routing_next.json`)

**Public 505 with MiniLM (same document layout as the paper):**

| Encoder | R@1 | R@5 | R@20 |
|---|---|---|---|
| Paper gemini | 0.956 | ~1.0 | 1.0 |
| MiniLM | **0.756** | **0.956** | **0.994** |
| Hash | 0.436 | 0.689 | 0.865 |

→ v2’s 0.325 is **hard queries + weaker encoder**, not a broken scorer (~20pp gap to Gemini on the easy public set).

**Document expansion on v2:** 0.325 → 0.400 R@1 (McNemar p≈0.11, unproven); R@20 slightly down.

**Kev on v2 (MiniLM top-8, n=80):**

- Unconditional R@1 **0.338** vs MiniLM **0.325** (14 vs 13, **p=1.0**)
- R@1 | gold in shortlist **0.415** (ceiling R@8 = 0.8125)
- Option-order flip rate **0.35**
- **~25.5 s/query** CPU → off hot path; treat as negative serving result

**5-fold margin:** ~15% coverage, ~0.91–0.92 precision on 11–12 covered queries — hint only.

**Non-oracle poison (synthetic templates, not test queries):** MiniLM hijack 0%, BM25 2.5%; length flag caught decoy (non-adaptive attacker).

**LinUCB:** wiring bug fixed (synthetic bandit learns); on v2 still worse than static MiniLM at 80 steps — park until real feedback / 2k+ stream.

## Product conclusion (supported by data so far)

On hard paraphrases, Soro is a **shortlist** (v2 MiniLM R@20 ≈ 0.89; public MiniLM R@20 ≈ 0.99) plus contract filter / UNKNOWN_ACK / attack flags — **not** an autonomous top-1 router. Fast path is thin; clarify-or-confirm remains the fallback.

## Explicitly not done (still open)

1. Conformal shortlists (proposed next)
2. Real chatbot catalog eval
3. bge / e5 / gte + MS MARCO cross-encoder
4. Contrastive fine-tune with held-out tools
5. Length-matched / adaptive poison + defense cost
6. v2b 300+ queries, two writers, independent annotator
7. Agent A/B: full catalog vs conformal shortlist
8. LiveMCPBench 527-tool catalog
9. Qwen3.5-0.8B-Base TDM zero-shot baseline

## Key report files

- `veyra/reports/routing_protocol_v2.json` — frozen hard set
- `veyra/reports/routing_v2_addendum.json` — public 483/505, McNemar, QL poison
- `veyra/reports/routing_next.json` — MiniLM@505, expansion, Kev, 5-fold, held-out poison
- `veyra/reports/routing_scale.json` / `routing_protocol_v1.json` — invalidated
