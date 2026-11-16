# Soro decision model: paper knowledge base

Written 2026-11-15. One file to write the paper from and to study other papers against.
Companions: `RESEARCH_GUIDE_V5.md` (full literature tables, ~45 papers), `DREX_DELTA.md` (Drex numbers), `EXEC_PLAN_V7.md` (work plan), `RESULTS_LEDGER.md` (raw results).

## 0. How to read this file

Every number and claim carries one of these labels. Only **[M]** and **[C]** may go into the paper as they stand.

| Label | Meaning |
|---|---|
| **[M]** | Measured by us, on a named split, and consistent across reports |
| **[C]** | True by construction (follows from the architecture) |
| **[P]** | Provisional: measured once, or reports disagree, or the checkpoint is unclear |
| **[A]** | Taken from the agent's notes on another paper; not yet checked by the owner in that paper |
| **[H]** | Hypothesis or plan; no result yet |

Open naming issue: the small backbone is `Qwen/Qwen3-0.6B-Base` in the training notebooks, but the script default is `Qwen/Qwen2.5-0.5B`. Read `base_model_name_or_path` in the locked checkpoint's `adapter_config.json` and use that name everywhere. This file says "0.6B" until that is settled.

---

## 1. The paper in one page

**Problem.** Decision models take a request and a menu of options and return a probability per option, without generating text. Published ones (Drex, Jev) still change their answer when the menu is reordered, give no guarantee on how often the right option is covered, and take text and images only.

**Thesis.** A small pointer model can give (a) the same answer for every menu order, (b) answer sets with a coverage guarantee, (c) a principled choice between calling, asking and abstaining, and (d) the same behaviour on speech and screenshots, and it can hand the hard cases to a larger model so the system matches large-model accuracy at small-model cost.

**Contributions and their status.**

| # | Contribution | Status |
|---|---|---|
| 1 | Exact order invariance in a decision model, by masking option-to-option attention, with the measured cost on near-duplicate tools | **[M]** at 0.6B; 4B and Gemma pending in fp32 |
| 2 | A permutation-equivariant refiner that recovers the near-duplicate cost | **[H]** +1.66 pts on 421 rows, p = 0.40, one seed. Unproven |
| 3 | Coverage sets tied to actions (singleton = act, large = defer or ask, empty = abstain) | **[P]** coverage holds in-split; sets are large on When2Call |
| 4 | Tool choice separated from readiness (pick the tool, then judge whether its required information is present) | **[H]** built, no result |
| 5 | Selective deferral: small model keeps confident requests, defers the rest | **[P]** curve computed on the wrong checkpoint; redo |
| 6 | Speech and screenshot requests under the same mask and guarantees; label-free bound on coverage across modalities | **[H]** data only |
| 7 | Early commit on streaming speech with bounded error | **[H]** not started |
| 8 | Learning from outcomes at use time; changing tool catalog benchmark | **[H]** not started |
| 9 | Tri-modal decision benchmark with ask and abstain labels | **[H]** not started |

**What an A* reviewer needs:** contribution 1 plus at least two of 3 to 6 with numbers. Contribution 1 alone is thin because Set-LLM and parallel context windows use the same masking idea.

---

## 2. The system

### 2.1 Layout and mask (from `veyra/python/src/soro/routing/upp.py`)

- Sequence: `[prefix/state] [request] [option 1] ... [option K]`. The request comes first.
- Each option's tokens attend to the prefix, the request, and earlier tokens of the same option. Attention from one option to another is blocked (`_query_iso_allowed`, line 595).
- Every option starts at the same position index, so position carries no order information.
- A request vector is read from the request; an option vector is pooled from each option; the score is a pointer (dot product by default). Confirm in code which token gives the request vector.
- Config name of the locked model: query_first + dot + option_isolation + 1-layer refiner, evaluated in fp32 ("v3b_fp32", checkpoint `ckpt_A`).

### 2.2 Invariance proposition **[C]**

*Claim.* For any reordering of the K options, each option receives the same score, so the chosen option and the full probability vector are unchanged.

*Proof sketch.*
1. Prefix and request tokens come before the options and attend causally, so their hidden states do not depend on the options at all.
2. By induction over layers, the hidden state of a token in option i depends only on (prefix, request, option i): its attention inputs are exactly those tokens, and its position indices are the same wherever the option sits.
3. The pooled option vector is therefore a function of (prefix, request, option i) only.
4. The refiner is a set function over the option vectors with no position input, so it is permutation-equivariant.
5. The score for option i is a function of the request vector and that option's refined vector. Reordering the menu reorders the scores and changes nothing else.

*Floating-point caveat.* The proof holds in exact arithmetic. On a GPU the order of additions changes with the layout, so scores differ by rounding. Measured spread across five orders in fp32: at most 1.99e-5, median 1.19e-7 **[M]**. A flip is possible only when the top two scores are closer than that. In half precision the spread is much larger and false flips appear (seen with fp16 autocast and suspected with 4-bit loading). Wording for the paper: "invariant up to floating-point rounding; 0 flips observed in fp32". Never "bit-exact".

*Reviewer question to pre-empt.* "Why not sort the menu into a fixed order?" Sorting makes any model deterministic but leaves it position-biased: accuracy still depends on where the arbitrary order puts the right option, and adding one tool reshuffles everything. Include a sorted-menu baseline in the flip table. Sorting can also be used on top of isolation to get exactly zero flips in any precision.

### 2.3 Why isolation costs accuracy on near-duplicates, and the refiner

- With isolation, an option cannot see that a more specific near-twin is also on the menu.
- Measured on 421 collision rows: no isolation 73.40%, isolation only 68.65%, isolation + refiner 70.31% **[M]**. The loss from isolation is real in direction; the refiner's recovery is not significant (7 rows).
- A 1,641-row collision set exists for the three-seed test. Until that test is done, the refiner is described as a hypothesis.
- Alternative to test in the same experiment: leave-one-out max over option vectors (exactly order-independent even in floating point).

### 2.4 Actions

Four learned actions: call a tool, answer directly, ask, abstain. Escalate is an inference rule (set size times cost above a threshold), not a class.

Two designs have been tried or planned:

| Design | What it is | Status |
|---|---|---|
| 4-card router | Four action cards added to the menu and scored like tools | **[M]** 0 flips; trains, but damages tool choice and scores 51 to 56% on the recast When2Call |
| Locked pointer + readiness | Tool choice stays with the locked pointer; a second score on the chosen tool says "ready" or "information missing" | **[H]** built; cannot hurt tool choice by construction |
| Three-state head per option | Each option scored as no fit / fits but information missing / ready | Both runs were invalid (wrong config, then trained from scratch). Not refuted, not supported |

Design rule learned: pick the tool first, then judge readiness on that tool only. Taking independent maxima over the menu lets a bystander tool force a false ask.

### 2.5 Coverage sets

- Split conformal: score each option, calibrate a threshold on held-out rows, return every option above it. Guarantee: the right option is in the set with probability at least 1 − α, on data exchangeable with the calibration rows.
- The guarantee is marginal (on average), not per request, and it weakens under distribution shift. Both go in Limitations.
- Set size follows model accuracy. Where the model is weak, sets are large; no reformulation fixes that.
- Planned extension: a joint space of (call, tool i), (ask, tool i), abstain, so the set speaks about actions and not only tools. This is a standard construction, not a novelty claim.

### 2.6 Selective deferral

The small model answers when its uncertainty is low and passes the rest to a larger model. Evidence that this should work: error detection AUROC 0.91 to 0.94 **[M]**. The figure for the paper is accuracy on kept requests against deferral rate from 0 to 50%, for the locked 0.6B, against the 4B and against Drex's reported accuracy.

### 2.7 Modalities

- Speech and vision run on `google/gemma-4-E2B`, which has native audio and vision inputs (`routing/media.py`). The Qwen models are text-only.
- Because the request comes first, option tokens attend to audio frames and image patches directly, and the request can be encoded once and cached.
- Cross-modal bound **[H]**: coverage on speech ≥ coverage on text − rate at which the speech set fails to contain the text set. The last term needs no labels; at deployment the transcript plays the text role. To be proved and tested before it is claimed.
- Cross-modal minimal pairs **[H]**: the same request with a required field present or absent in a screenshot or clip. Remove the field by re-rendering, never by blur or crop.

---

## 3. Results

### 3.1 Tool choice on the matched external split (1,200 rows) **[M]**

| System | Size | Overall | Tool rows | Abstain rows | Flips | Latency |
|---|---|---|---|---|---|---|
| Soro 0.6B locked (isolation + refiner) | 0.6B | 86.00% (CI 83.9 to 87.8) | 86.38% | 82.96% | 0 | ~180 ms |
| Soro 4B, isolation + refiner | 4B | 89.58% (CI 87.7 to 91.2) | 89.77% | | pending in fp32 | |
| Soro 4B, no isolation (old) | 4B | 90.58% | | | 3.8% | |
| Soro 0.8B, no isolation (old) | 0.8B | 85.67% | | | ~4% | |
| Hammer-1.5B | 1.5B | 82.58% | 87.23% | 45.93% | not measured | 1,239 ms |
| xLAM-1B | 1B | 73.42% | 75.40% | 57.78% | not measured | 718 ms |
| MiniLM cosine | 33M | 79.17% | | | 0 | |
| BM25 | | 58.67% | | | 0 | |

How to state it: the 0.6B beats Hammer overall by 3.42 points (p = 0.016) and xLAM by 12.58 points. Hammer is slightly better at choosing among tools (87.23 against 86.38); our margin comes from abstaining. The cross-encoder baseline (24%) is broken and must be fixed or dropped. Flip rates for Hammer and xLAM have never been measured; do not print any.

### 3.2 Order invariance **[M]**

- Locked 0.6B: 0 flips over five orders on every split evaluated (5,207 rows in the S1 pack; 6,050 rows in the action pack). Spread ≤ 1.99e-5.
- Same model without isolation: 8.08% of rows flip overall, 28.74% on collisions.
- Accuracy cost of isolation + refiner against no isolation, 5,207 rows: −0.61 points overall (p = 0.113, not significant); +2.17 points on external (p = 0.0004); collisions 70.31 against 73.40 (p = 0.19).
- 4B with isolation: 23 flips in 5,007 rows in low-precision evaluation **[P]**; fp32 result pending.
- Gemma 4 E2B, 4-bit: 4/300 and 2/300 flips **[P]**; fp32 result pending.

### 3.3 Other 0.6B numbers

| Split | n | Accuracy | Label |
|---|---|---|---|
| Collisions | 421 | 70.31% | **[M]** |
| Zero-shot tools | 2,172 | 88.31% | **[P]** (a later table shows 86.33% on n = 300) |
| BFCL slice | 100 | 84 or 85% | **[P]** too small to cite; reports disagree |
| Error AUROC, collisions | 421 | 0.914 | **[M]** |

4B with isolation: collisions 79.33%, zero-shot 90.52%, error AUROC 0.937 external and 0.904 collisions **[M]**.

### 3.4 Actions **[P]**

All on our recast of When2Call (3,394 rows), which is not the benchmark's original format.

| Run | Action-kind accuracy | Notes |
|---|---|---|
| Untrained, set-size heuristic | 52.3% | ask recall 0 |
| 4-card, original data (2 true seeds) | ~56.5% | external tool accuracy fell to ~83%, collisions to ~60% |
| 4-card, enriched data | 52.27% (51.06% strict) | external tool accuracy 76.0% |
| Trained only on When2Call's training split | 46.7% (58.3% with prior correction) | undertrained, unbalanced; training and test come from different sources |

Confusion for the enriched 4-card run: tool recall 76.2%, ask recall 48.1%, abstain recall 26.6%. Largest errors: abstain predicted as ask (563 rows), ask predicted as call (490 rows).

Not yet run: the benchmark in its original four-way format (3,652 rows), which is the only number comparable with Drex.

### 3.5 Coverage **[P]**

- Nominal 90%, calibration rows disjoint from test: empirical coverage 94.8 to 96.1% in-split (over-covers).
- Set sizes reported so far: external 1.19 to 1.55, selection 1.28, collisions 1.99, When2Call recast 2.5 to 2.6 (about 42% of the menu). Reports use different checkpoints; redo on the final model and report size as a fraction of menu size.

### 3.6 Gemma 4 E2B, text only, 4-bit **[P]**

Selection 82.67% and zero-shot 81.67% on 300 rows each; abstain rate on zero-shot 36.4%. Compared against an unclear Qwen checkpoint. The gate (within 2 points of the locked 0.6B on the external 1,200, 0 flips in fp32) has not been evaluated.

### 3.7 Speech **[P]**

42,057 Kokoro clips synthesised. Quality check not passed: 30% word error rate on 30 clips with `whisper-tiny`. Redo on at least 500 clips with a larger Whisper model, scoring tool names and argument values.

### 3.8 Numbers that must not be used

| Number | Why |
|---|---|
| "AskOrExact" 74.7% or 85.7% | Counts any "ask" prediction as correct |
| p = 10⁻¹⁶¹ against the untrained head | Meaningless comparison |
| Collisions 71.26% after action training | Scored on a subset; the real figure is ~60% |
| Three-seed means for action runs | Seeds 42 and 43 were the same run |
| Flip rates for Hammer, xLAM, "any baseline 8 to 15%", "GPT-4 14.2%" | Never measured; no source |
| xLAM 85.12% | The matched run gave 73.42% |
| Latency under 120 ms | Measured value is ~180 ms |
| Sets of 1.25 to 1.45 joint actions on When2Call | A prediction, not a result |
| Risk-coverage tables starting at 72.4% or 82.3% | Not the locked model (which scores 86.00%) |

---

## 4. What failed, and what it taught (material for ablations and limitations)

| What was tried | Outcome | Lesson |
|---|---|---|
| Block, cross-attention and late-interaction layouts | 25 to 34% against 86% for request-first | Options must read the request inside the backbone |
| Distilling from a 4-bit Qwen3-8B teacher | Teacher 21.5 points worse than the student on 270 rows | A teacher must be shown to be better first; use our own 4B |
| fp16 and 4-bit evaluation | False flips | Evaluate invariance in fp32 and report the spread |
| Action training on 9k rows | Tool choice fell 3 to 10 points | Protect tool choice: lock the pointer or replay tool rows |
| Enriched data with parameter schemas | When2Call no better | 36.7% bare cards was a real defect, but not the main cause |
| Ask rows made by deleting a value | Model learned to spot damaged text | Underspecified requests must be written naturally |
| Training on When2Call's training split | 46.7% on test | Training (ToolBench) and test (Berkeley live set) differ in source, menu size, language and class mix |
| Agreement-filter job | Timed out at 12 h | Not worth rerunning |
| Near-miss evaluation set | 29 of 84 gold labels wrong | Hand-audit small evaluation sets; 55 clean rows remain |

---

## 5. Open experiments and their gates

| Experiment | Gate |
|---|---|
| Gemma 4 E2B in fp32 on external 1,200 + zero-shot | 0 flips with spread ≤ 1e-4; within 2 points of locked 0.6B |
| 4B in fp32, results saved per split | 0 flips; When2Call ≥ 65% means size helps, ~55% means data is the limit |
| Original-format When2Call (3,652 rows) | First comparable number; report accuracy and macro F1 |
| Readiness on locked pointer | Separates ask from call on tool-disjoint natural pairs; tool choice unchanged |
| Risk-coverage curve on the locked 0.6B | Starts at 86.00%; report accuracy at 10, 20, 30% deferral |
| Refiner against no refiner against leave-one-out max | Three seeds, 1,641 collision rows, paired test |
| Action data build, ≥ 300k menus | Natural asks, ~30% abstain, menus up to 40, several tool sources |
| Start from Qwen3-Embedding-0.6B or Reranker-0.6B | +2 points on external, else keep the base model |
| Speech twins on Gemma | Speech within 3 points of text; agreement > 95% |
| Run Drex v1.5 ourselves | Its accuracy and flips on our external 1,200 and collisions (weights are open and fit a T4 in 4-bit **[A]**) |

Rules for every run: one variable changed; explicit seed; local 100-step smoke test; results written as each split finishes; fp32 five-order evaluation; paired test against the reference.

---

## 6. Competitor profile: Drex

Everything here is **[A]**: from `DREX_DELTA.md`, which the agent wrote. Check each line in the paper before citing.

- *Towards Foundation Decision Models*, Nace.AI, arXiv 2611.07854, 5 Nov 2026. Built on the open Kev code base and follows the Jev interface.
- Models: v1.5 (9B, Qwen3.5 hybrid), v2.0 (35B mixture, 3B active), Max (27B, full-attention readout, images), DLM (8B). Trained on 1,150,460 decision records, about 181k of them tool decisions, with supervised training plus a consistency loss and soft targets from a teacher.
- Order flips over three orders on 1,591 decisions: Max 4.3%, v2.0 5.9%, v1.5 5.3%, Jev 4.3%. On menus of six or more options (n = 173): 13.3%, 16.2%, 15.6%, 14.5%.
- When2Call has two reported numbers. On the Decision Index (n = 3,652): v1.5 89.7, v2.0 86.5, Max 85.2. On the Artificial Analysis index: Max 94.0, v2.0 86.2, v1.5 84.8. Our original-format run matches the first, so the number to compare with is 89.7, not 84.8.
- Calibration: on menus of 6 to 20 options, Max is 8.4% miscalibrated and v1.5 13.6%.
- Option isolation: described in Appendix C.2 and stated as untested because their backbones have recurrent layers that cannot apply the mask.
- Not present: speech, coverage guarantees, an ask/abstain cost policy, adaptation after training.

What this means for us: the flip table and the isolation result are a direct answer to something Drex leaves open. On When2Call accuracy Drex is far ahead, with 15 times the parameters and about 100 times the data.

---

## 7. Side-by-side study guide

For each paper, write down the answers to the questions before using it in the draft. IDs for older papers are from memory; check them. The remaining ~25 papers are in `RESEARCH_GUIDE_V5.md` section 1.

### 7.1 Read in full first

| Paper | ID | Questions to answer | How we differ |
|---|---|---|---|
| Drex | 2611.07854 | How is When2Call evaluated and on what training data? Exact wording on option isolation? Flip protocol (how many orders)? Which benchmarks are public? | Exact invariance tested; guarantees; speech; small size |
| Set-LLM | 2505.15433 | Do set elements attend to each other? How are positions handled? Is the task generative or selection? Any near-duplicate study? | Request-conditioned isolation in a pointer; measured near-duplicate cost |
| Parallel Context Windows | 2212.10947 | Exactly what mask and position reuse? Is invariance claimed or just longer context? | Same mechanism; we use it for invariance of a decision |
| Kev (find via Drex's references) | | What is the original pointer design and what do we change? | Our starting point; must be credited |
| When2Call | 2504.18851 | Exact metric (accuracy or macro F1)? Where do train and test come from? What is the fourth choice? | Our action benchmark |

### 7.2 Invariance and set functions

| Paper | ID | Read for |
|---|---|---|
| Pointer Networks | 1506.03134 | Origin of pointing at inputs |
| Deep Sets | 1703.06114 | Theorem on permutation-invariant functions; cite for the refiner |
| Set Transformer | 1810.00825 | Equivariant attention over sets |
| LLMs are not robust multiple-choice selectors | 2309.03882 | Evidence of order sensitivity for the introduction |
| InvariRank | 2604.27599 | Same idea in reranking; how they handle positions |

### 7.3 Coverage and uncertainty

| Paper | ID | Read for |
|---|---|---|
| Gentle Introduction to Conformal Prediction | 2107.07511 | All definitions and the coverage proof we rely on |
| Conformal prediction for multiple choice | 2305.18404 | Closest setting; how coverage breaks under shift |
| KnowNo | 2307.01928 | Singleton = act, otherwise ask; our set-to-action rule builds on this |
| Conformal Cascade | 2607.25018 | Empty set = defer; our deferral story builds on this |
| Conformal under domain shift | 2510.05566 | Weighting method for speech and real-audio shift |
| Role-stratified conformal risk control for tool calls | 2607.24343 | Closest work on guarantees for tool calls; not yet read |

### 7.4 Asking, abstaining, tool calling

| Paper | ID | Read for |
|---|---|---|
| Hammer | 2410.04587 | Function-name masking; how it handles irrelevance |
| xLAM | 2409.03215 | Data scale and format |
| Gorilla / Berkeley leaderboard | 2305.15334 | Evaluation protocol we borrow rows from |
| ToolRet | 2503.01763 | Large tool retrieval; source for menus |
| ClarifyBench | 2511.08798 | Action set and reward; multi-turn asking |
| AgentAbstain | 2607.10059 | Abstain benchmark we evaluate on |
| Uncertainty-aligned RL for tool calling | 2606.06976 | Direct competitor on training; not yet read |
| Logit adjustment | 2007.07314 | Principled fix for the ask/abstain class prior |

### 7.5 Speech, vision, streaming

| Paper | ID | Read for |
|---|---|---|
| Audio2Tool | 2604.22821 | Spoken tool benchmark; licence for recasting |
| Spoken Function Calling | 2608.05126 | In- and out-of-distribution split |
| Full-Duplex-Bench v3 | 2604.04847 | Real speech; cascade baseline |
| RASSG | 2610.14659 | Heuristic early gating we want to replace with a bound |
| Whisper | 2212.04356 | Cascade baseline and audio quality check |
| GUI-Actor | 2506.03143 | Pointer over image patches; screenshot analogue |

### 7.6 Small-model training

| Paper | ID | Read for |
|---|---|---|
| Distillation with GRPO for compact rerankers | 2609.01947 | 4B teacher to 1B student recipe |
| RLHN | (EMNLP 2025 Findings) | Relabelling false hard negatives |
| LoRA | 2106.09685 | Method citation |

### 7.7 Study template (one per paper)

1. Task and input/output format.
2. Model size and training data size.
3. Main claim, and the table that supports it.
4. Evaluation protocol: splits, metric, number of orders or seeds.
5. What it does not do that we do.
6. What it does that we do not, and whether a reviewer will ask for it.
7. One sentence for our related-work section.

---

## 8. Paper skeleton

Working title: *Decision Models with Guarantees: Exact Order Invariance, Calibrated Actions and Speech in a Small Pointer Model*.

| Section | Content | Source in this file | Ready to draft |
|---|---|---|---|
| 1 Introduction | Decision models; three failures (flips, no guarantee, text only); contributions | 1, 6 | Yes, with placeholders for results |
| 2 Related work | Six paragraphs: decision models, invariance, coverage, ask/abstain, speech, small models | 7 | Yes |
| 3 Setup | Request, menu, actions, costs; definitions of flip rate, coverage, set size | 2, 9 | Yes |
| 4.1 Isolation | Mask, shared positions, proposition, proof, floating-point caveat, sorted-menu baseline | 2.1, 2.2 | Yes |
| 4.2 Refiner | Why near-duplicates suffer; equivariant layer | 2.3 | After the three-seed test |
| 4.3 Actions | Tool first, then readiness | 2.4 | After readiness results |
| 4.4 Coverage and deferral | Conformal sets; risk-coverage | 2.5, 2.6 | After curve on the locked model |
| 4.5 Speech and vision | Gemma port; twins; cross-modal bound | 2.7 | After Gemma passes |
| 5 Training | Data table, losses, what was dropped | 4, 10 | Partly |
| 6.1 Tool choice | Table 3.1 | 3.1 | Yes |
| 6.2 Invariance | Flip table, spread, cost | 3.2 | Yes for 0.6B |
| 6.3 to 6.7 | Actions, coverage, speech, early commit, size | 3.4 to 3.7 | No |
| 7 Limitations | Marginal guarantees; synthetic speech; rounding; small slices; cannot generate | 2.2, 2.5 | Yes |
| Appendix | Proof; data construction; negative results (section 4); label audit | 4 | Partly |

---

## 9. Definitions

- **Decision model:** takes a request and a list of options, returns a probability for each option. It does not generate text.
- **Pointer:** the score for an option is computed from that option's own vector and the request vector, so the output points at one of the inputs.
- **Menu:** the list of options (tools plus any action cards) shown for one request. K is its size.
- **Flip:** the chosen option changes when only the order of the menu changes. Flip rate is the share of rows with at least one flip across the tested orders.
- **Option isolation:** blocking attention between different options, so each is read only with the request.
- **Collision:** a menu with near-duplicate tools, where only one is right.
- **Coverage set:** a set of options returned with a guarantee that it contains the right one at a chosen rate (for example 90%).
- **Set size:** how many options are in that set. Smaller is more useful.
- **Abstain:** no option on the menu fits. **Ask:** an option fits but the request lacks required information, or several options fit equally.
- **Deferral:** passing a request to a larger model or a person instead of answering.
- **Risk-coverage curve:** accuracy on the requests the model keeps, plotted against the share it keeps.
- **Twin:** the same request rendered in another modality (text and its spoken clip).

---

## 10. Data inventory

| Set | Rows | Use |
|---|---|---|
| External evaluation | 1,200 (1,065 tool, 135 abstain) | Main tool-choice comparison |
| Collisions | 421, and an expanded 1,641 | Near-duplicate tools |
| Zero-shot tools | 2,172 | Unseen tools |
| Action evaluation pack | 6,050 over 7 splits | When2Call recast 3,394; external 1,200; selection 572; collisions 421; AgentAbstain 301; escalate probe 107; near-miss 55 |
| When2Call original format | 3,652 (1,295 call, 1,295 cannot answer, 1,062 ask) | Comparable with Drex |
| Action training, original | 8,953 (tool 4,500; abstain 1,785; ask 1,420; answer 1,248) | Superseded |
| Action training, enriched | 10,220 incl. 1,267 minimal pairs | Asks made by deletion; to be rebuilt |
| When2Call training dialogues | ~24,000 | Source for natural asks |
| Speech twins | 42,057 Kokoro clips, ~15 GB | Quality check pending |

---

## 11. Wording rules for the draft

- Say "invariant up to floating-point rounding", never "bit-exact" or "mathematically eliminates".
- Two guarantees only: invariance and coverage. Cost-aware actions are an objective; native speech is a design choice.
- Report tool-choice accuracy and action-kind accuracy separately, always with n.
- Every comparison names the split, the row count, and the test used.
- A number about another paper is cited only after it has been read in that paper.
- State where we lose: Hammer on tool rows; the old 4B by one point on external; Drex on When2Call.
- No result is described before it exists.
