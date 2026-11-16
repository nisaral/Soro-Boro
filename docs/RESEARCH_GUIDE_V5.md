# Soro decision model: literature review, gap map, paper guide, scaling plan (v5)

Written 2026-11-13. Supersedes the thesis sections of `HANDOFF.md` and `PAPER_PLAN.md`.

**Evidence level.** Almost every paper below was read through search summaries and abstracts, not full text. Rows marked (M) are from memory and need a citation check. Before any claim about a paper goes into the draft, someone reads that paper. Numbers quoted from other papers are their own reported numbers.

---

## 0. Why the pressure is justified

- Drex (Nace.AI, arXiv 2611.07854, 5 Nov 2026) published "foundation decision models" at 8B-35B and says its pointer models are built on the open Kev code base. Jev (TypeSafe AI, Sept 2026) is the commercial version of the same idea.
- So the general idea ("options in, probabilities out, no generation") is now public, funded and benchmarked. A small-lab paper that only says "a pointer decision model" is late.
- Drex names option isolation as untested and has no speech, no guarantees and no adaptation. Those openings will not stay open for long.
- Consequence: plant a flag early (arXiv preprint of the invariance + guarantee results), then the full paper.

---

## 1. Literature review

### 1.1 Decision models (closest competitors)

| Work | What / how | How good | What it lacks |
|---|---|---|---|
| **Drex** (2611.07854) | State + questions + options -> probability per option. Pointer head (`<decide>` query, `</opt>` keys, dot product) on hybrid backbones; Max = 27B with bidirectional layers and a readout head. SFT + permutation consistency loss + "RLAF" (soft targets from teacher + verified outcome). 1.15M decision records, 11 domains. Images in Max. | When2Call: Max 94.0, v1.5 84.8. Decision Bench v4: Max 94.0 (Opus 5.5 95.6). Flips 4.3-5.9%. 183 ms. | Option isolation described, never tested (backbones cannot mask). No speech. One temperature; 8.4% ECE on 6-20 options. No coverage guarantee. No in-context examples, no learning after training, no cost-aware action. |
| **Jev** (TypeSafe AI) | Proprietary "System One" model, typed answers + probabilities, up to 255 options, fields in parallel. | Decision Index 60.7 (per Drex). Flips 4.3%. | Closed weights. Same gaps as Drex as far as public material shows. |
| **Kev** (open code base) | Small Jev-like pointer models users train themselves; Soro-Kev is built on it. | Soro-4B v2: 90.6 external, 91 BFCL(100), flips 3.8%. | Order flips; no guarantees; text only. |

### 1.2 Order invariance

| Work | What / how | How good | What it lacks |
|---|---|---|---|
| **Set-LLM** (2505.15433, NeurIPS 2025) | Set attention mask + set positional encoding on a pretrained LLM; proves permutation invariance. | Same accuracy in random and adversarial order. | Generative LLM setting; no study of near-duplicate options; mask incompatible with sparse attention. **Read in full: do elements attend to each other?** |
| **InvariRank** (2604.27599, SIGIR 2026) | Blocks cross-candidate attention + shared RoPE framing for listwise reranking in one pass. | Position-invariant by design. | Recommendation reranking only; no abstain/guarantees. |
| Consistency-loss training (Drex, others) | KL between permuted menus. | Reduces flips 6.3 -> 4.2%. | Not exact. |
| CompRank (2606.11700) | Attention-based decision-token score over isolated blocks. | Trains on isolated blocks. | (from earlier session; re-read) |

### 1.3 When to call / ask / abstain

| Work | What / how | How good | What it lacks |
|---|---|---|---|
| **When2Call** (2504.18851) | 4-way MCQ: call, ask, say unable, answer. Train + test sets. | Benchmark; small models poor. | Text only; no guarantees. |
| **ClarifyBench / SAGE-Agent** (2511.08798) | Reward over TOOLCALL / ASK / REFUSE / DIRECTLY; structured uncertainty over parameters. | Multi-turn disambiguation. | Generative agent; no small-model decision head. |
| **AgentAbstain** (2607.10059) | Tests whether agents know when not to act. | Benchmark. | Diagnosis only. |
| When2Tool (2605.09252), AskBench (2602.11199), RegretBench (2607.21143) | Call-vs-answer probing; ask-vs-answer with RL; clarification as a regret-scored policy. | Each covers one decision. | Not unified. |
| **Uncertainty-aligned RL for tool-calling** (2606.06976) | RL on the call decision aligned to uncertainty. | Not read. | **Must read: direct competitor on training.** |
| "Calibration is the Bottleneck" (2609.00949) | Action-class diagnostic of multi-turn tool calling. | Not read. | Supports our framing; read. |
| Probe papers (2608.27750, 2608.00218, 2608.03071) | Linear probes detect tool-call errors, missing parameters. | Show the signal is in hidden states. | Probes on big LLMs, not a trained decision model. |

### 1.4 Guarantees and uncertainty

| Work | What / how | What it lacks |
|---|---|---|
| **KnowNo** (2307.01928, CoRL 2023) | Conformal set over LLM planner options; singleton -> act, else ask. | Robots; LLM logits; no abstain/empty-set meaning; no modalities. |
| Conformal MCQ (2305.18404) | Conformal sets for LLM multiple choice; tests cross-subject shift. | No actions. |
| **Conformal Cascade** (2607.25018) | Empty set = out-of-distribution = defer to next tier. | Model cascades, not tools or modalities. |
| Domain-shift-aware conformal (2510.05566) | Reweights calibration data under shift. | Text domains only. |
| Role-stratified conformal risk control for tool calls (2607.24343) | Conformal risk control per tool role. | **Not read; closest on guarantees for tool calls.** |
| conformal-tool-exposure (GitHub) | Conformal tool sets on ToolRet. | Repo, not a paper. |
| "Conformity Breaks Conformal Prediction" (2609.04445) | Score-distribution shift breaks coverage. | Warning we must address. |
| UQ in LLM Agents (2602.05073, ACL 2026) | Position paper: turn-level UQ scarce (9% of 44 benchmarks). | No method. |
| TRACER (2602.11409, ICML 2026) | Trajectory risk on tau2-bench. | Post-hoc on big LLMs. |
| Passive Metric to Active Signal (2601.15690) | Survey: uncertainty as control signal. | Survey. |

### 1.5 Tool results (gap LLM-2)

| Work | What / how | What it lacks |
|---|---|---|
| **ToolFailBench** (2607.04686) | 1,000 tasks; labels skip / ignore / fabricate / unnecessary; best of 19 models 86.3%. | Diagnosis only. |
| **ToolBench-X** (2606.25819) | Injects five recoverable tool hazards. | Diagnosis only. |
| LettuceDetect / span detection (2607.00895) | 2B detector flags unsupported spans; ~0.72 F1 on tool output. | Detection after the fact; not trained on counterfactual results. |
| AgentLTL (2607.02599), Tool Receipts (2603.10060) | Trace rules; signed tool outputs. | Rule-based. |
| Faithfulness-QA (2604.25313) | Counterfactual entity swaps for RAG faithfulness. | RAG, not tool results. |

### 1.6 Speech and screens

| Work | What / how | What it lacks |
|---|---|---|
| **Audio2Tool** (2604.22821, Interspeech 2026) | 30k spoken tool queries, 3 domains, 8 tiers. | Benchmark for generative speech LMs. |
| **Spoken Function Calling** (2608.05126) | 300 spoken tools, in/out-of-distribution split. | Same. |
| **Full-Duplex-Bench v3** (2604.04847) | Real human speech with disfluencies; includes a cascade. | Same; 86% of silent cases still call tools (abstain failure). |
| MIST (2605.06897), From Text to Voice (2605.15104) | Smart-home speech tool calling; text-to-voice eval framework. | Benchmarks. |
| RASSG (2610.14659), Stream RAG (2510.02044), tool-intent stabilisation (2606.20113) | Launch/cancel tools on partial speech. | Heuristic gates, no error bound. |
| MM-ToolSandBox (2607.11818), GUI-Actor (2506.03143, NeurIPS 2025) | Visual tool calling; attention-based pointer over image patches, head-only training works. | No abstain/guarantee; GUI-Actor is the screenshot analogue of our pointer: cite. |

### 1.7 Small function-calling models and retrieval

| Work | What / how | What it lacks |
|---|---|---|
| Hammer (M) | Function masking in training to stop reliance on names. | Generative; flips ~5% in our table. |
| xLAM (M) | Large synthetic API data (APIGen). | Generative; flips. |
| Arch-Router / Arch-Function, FunctionGemma (M) | Small routers / function callers. | Verify details. |
| **ToolRet** (2503.01763) | 7.6k tasks, 43k tools; best embedder nDCG@10 33.8. | Retrieval only. |
| Tool-DE (2510.22670) | Document expansion + Tool-Embed + Tool-Rank. | Retrieval only. |

### 1.8 Learning from use

| Work | What / how | What it lacks |
|---|---|---|
| MemToolAgent (2606.07909) | Memory of past experiences + critiques, no fine-tuning. | Generative agent; no guarantee; no changing catalog test. |
| VisTA (CVPR 2026), BaRP (2510.07429) | RL / bandit selection policies. | Need training; BaRP routes models not tools. |
| Training-free GRPO, ICAL (M) | Experience libraries as context. | Generative. |

### 1.9 Training small rankers

| Work | What / how |
|---|---|
| On-policy distillation + off-policy GRPO for compact rerankers (2609.01947) | 4B teacher trained with GRPO on judge feedback, distilled to 1B with on-policy GRPO and teacher soft rewards. Closest recipe to ours. |
| RLHN (Findings of EMNLP 2025) | LLM cascade relabels false hard negatives; less data, better rerankers. |
| CoRanking (2503.23427) | Teacher unreliable on long-tail queries. |
| Drex note | REINFORCE did not beat direct differentiation for them. |

---

## 2. Gaps that are still open (after this review)

1. **Nobody has tested exact invariance in a decision model, or measured what it costs on near-duplicate options.** Set-LLM proves the mechanism elsewhere; Drex leaves it untested.
2. **No decision model returns sets with a coverage guarantee**, and none ties the set to an action.
3. **"Ask" has two causes that nobody separates in the model:** several options fit, or one fits but information is missing.
4. **No non-generative decision model takes speech.** Speech tool benchmarks exist; all entrants are generative.
5. **No guarantee that survives a change of modality** (calibrate on text, deploy on speech; TTS to real speech).
6. **Early commit on streaming speech has only heuristic gates.**
7. **No decision model improves from outcomes at use time**, and no benchmark has a catalog that changes.
8. **Tool-result faithfulness is diagnosed, not trained.**
9. **Small vs large:** no evidence yet on how small a decision model can be for a given accuracy when the guarantees are kept.

---

## 3. How our work fills each gap

| Gap | Our piece | Status | What is still needed |
|---|---|---|---|
| 1 | v2 / v3 / v3b: query-conditioned isolated options + equivariant refiner | 0 flips measured; external +2.2 vs v2; refiner benefit unproven | 3 seeds, collisions eval >= 1,500, menus of 6-20 options, 4B backbone |
| 2 | Split-conformal sets per split | In-split coverage holds; transfer over-covers | Per-slice coverage and set size after S2 |
| 3 | Per-option 3-state head (no fit / fits, info missing / ready) | Design only | Prior-work check, S2 run 2 vs 4-card run 1 |
| 4 | Speech twins (42.7k Kokoro clips) | TTS nearly done | S3 training, cascade baseline, Audio2Tool, Spoken FC, FDB-v3 |
| 5 | Per-modality calibration; shift-aware weighting for TTS -> real | Not started | Needs real-speech set |
| 6 | Prefix training + commit when set is a singleton, with bounded error | Not started | After S3 |
| 7 | Outcome cards appended to options; stream eval with changing catalog | Not started | Stretch |
| 8 | Counterfactual result pairs | Not started | Optional / second paper |
| 9 | 0.6B vs 4B rows, same recipe | 0.6B only | 4B v3b run |

**Paper core = gaps 1-5. Gap 6 strengthens it. Gap 7 is the stretch. Gap 8 is out unless time allows.**

---

## 4. Paper structure guide (no prose yet)

Working title: *Decision Models with Guarantees: Exact Order Invariance, Calibrated Actions and Speech in a Sub-Billion-Parameter Pointer*.

**Abstract (5 sentences):** problem (decision models flip with order, give no guarantee, text/image only); method (isolated options + equivariant refiner; per-option states; conformal sets; speech twins); headline numbers [PLACEHOLDER]; size/latency; release.

**1 Introduction.** Decision models are replacing generated tool calls (Drex, Jev). Three failures: order flips (Drex 4.3-5.9%), no guarantee (ECE 8.4% on large menus), text/image only. Contributions list (4 bullets = sections 4.1-4.4). Figure 1: one request in three modalities -> same set -> action.

**2 Related work.** Six paragraphs mirroring 1.1-1.8. Each ends with one sentence on the difference. Be exact about Set-LLM, KnowNo and Conformal Cascade: we build on them.

**3 Problem setup.** State, request (text/speech/screenshot), menu of options, actions {call, answer, ask, abstain}, costs. Definitions: flip rate, coverage, set size, cross-modal agreement.

**4 Method.**
- 4.1 Query-conditioned option isolation: mask, shared positions, proposition (invariance up to floating point) + proof sketch. Cite Set-LLM, InvariRank.
- 4.2 Equivariant refiner: why isolation hurts near-duplicates; one permutation-equivariant layer over option vectors.
- 4.3 Per-option states and derived actions (or the 4-card head if that wins).
- 4.4 Conformal sets: score, calibration, per-modality calibration, shift weighting. Cite 2305.18404, 2510.05566, 2609.04445.
- 4.5 Speech and screenshot requests: media towers, twins, cross-modal distillation, prefix training.
- 4.6 (stretch) Outcome cards.

**5 Training.** Data table (sources, counts, licences, leakage firewall). Losses. Hard negatives. What was tried and dropped (teacher distillation: teacher 21 pts worse; block layouts at chance). Compute budget.

**6 Experiments.**
- 6.1 Setup: splits, baselines (BM25, dense, cross-encoder, Arch, xLAM, Hammer, Soro v2 0.8B/4B, Drex v1.5 if runnable, cascade for speech), metrics, 3 seeds, paired tests.
- 6.2 Order invariance: flips, logit spread, accuracy cost, collisions, menu size. [TABLE]
- 6.3 Tool choice vs baselines. [TABLE]
- 6.4 Actions: When2Call, AgentAbstain, ClarifyBench; confusion matrix. [TABLE]
- 6.5 Guarantees: coverage and set size per slice, under shift. [FIGURE]
- 6.6 Speech: Audio2Tool, Spoken FC, FDB-v3; end-to-end vs cascade; clean vs noisy; cross-modal agreement; coverage transfer. [TABLE]
- 6.7 Early commit: fraction of utterance heard vs error bound. [FIGURE]
- 6.8 Size: 0.6B vs 4B; latency; cost per 1k decisions.
- 6.9 Ablations: mask, refiner depth, hard negatives, head type, distillation.

**7 Limitations.** Cannot generate answers; synthetic speech in training; conformal guarantees are marginal; small eval slices; floating-point caveat.

**8 Release.** Weights, data cards, eval harness.

**Appendix.** Proof; data construction; label audit (gold-100); negative results; per-domain tables.

---

## 5. Small model vs large models

### 5.1 Where a small model can match a large one
Decision quality on a fixed menu depends more on training signal than on world knowledge. Drex's own limits say its models trail on knowledge-heavy tasks; tool routing is not one. Our evidence: Soro-4B v2 at 90.6 external vs 0.8B at 85.7, so size still buys about 5 points. Plan to close it, in order of expected gain per GPU hour:

1. **Hard negatives done properly.** Mine top-k confusable tools from a retriever; relabel false negatives with a model cascade (RLHN idea); train where the model fails (collisions 0.70, near-miss 0.42).
2. **A teacher that is actually better.** The 4-bit 8B teacher failed. Use Soro-4B (once it has the v3b mask) as teacher for 0.6B: logits over the same menu, same eval, known to be 5 points better. Self-family distillation is cheap and reliable.
3. **More training.** 1,000 steps in 95 minutes is small. Sweep steps and LoRA rank before any new idea.
4. **Data scale.** Drex used 1.15M records; we have tens of thousands. Add ToolRet-train (200k tasks), When2Call train, Audio2Tool, recast as menus.
5. **Menu augmentation.** Function-name masking (Hammer), description paraphrase, menu size 2-64, removing the gold tool.
6. **Retrieval in front.** For catalogs beyond 64 tools: retriever top-k, then the pointer. Report recall of stage 1 separately.

### 5.2 RL: where it helps and where it does not
- **Single decisions:** labels are known and the action space is tiny, so exact expected-cost training beats sampled RL. Drex reports REINFORCE did not beat direct differentiation.
- **Use RL only where the reward is not a label:** multi-turn episodes with a tool simulator and injected faults; early-commit timing on speech (reward = time saved minus error cost).
- **On-policy distillation** (2609.01947): the student trains on its own mistakes with teacher scores. For us this means: run the student, collect its errors, have the 4B teacher score those menus, retrain. Two rounds.

### 5.3 Post-training
- Temperature per modality, then conformal calibration.
- Model soup / weight averaging over seeds (keeps the mask, costs nothing at inference).
- Quantise only after checking invariance spread and coverage still hold (fp16 already broke flips once).

### 5.4 GPU budget rules (Kaggle 2xT4, 12 h, weekly quota)
- Inference-only work first (re-scoring, baselines, calibration): minutes.
- Every training run: local 100-step smoke, saves checkpoint, fp32 5-order eval, <= 8 h, resumable.
- One variable per run. Cache backbone activations for head-only experiments (refiner depth, head type) so they cost minutes.
- CPU sessions for TTS, data building, retrieval mining.
- Order of spend: S2 run 1 -> 4B v3b -> seeds/refiner proof -> S2 run 2 (state head) -> S3 speech -> early commit.

### 5.5 Do we need a bigger model?
Ship two sizes: 0.6B (edge, the efficiency claim) and 4B (the accuracy claim). Do not go beyond 4B: it does not fit the compute, and the paper's point is that guarantees and stability do not need 27B.

---

## 6. Reading list still owed (full text)
Drex 2611.07854 incl. Appendix C.2; Set-LLM 2505.15433; InvariRank 2604.27599; KnowNo 2307.01928; Conformal Cascade 2607.25018; 2607.24343; 2606.06976; 2609.00949; When2Call 2504.18851; Audio2Tool 2604.22821; Spoken FC 2608.05126; FDB-v3 2604.04847; RASSG 2610.14659; GUI-Actor 2506.03143; MemToolAgent 2606.07909; 2609.01947; RLHN.
