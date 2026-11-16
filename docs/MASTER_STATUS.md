# Soro: master status and direction (16 Nov 2026)

Entry point for the project. History is in `PROJECT_KT.md`. Tasks are in `TASK_BOARD.md`. Prior art is in `PAPER_LITERATURE_NOTES.md` and `PAPER_V9_NOVELTY_AUDIT.md`. This file replaces `EXEC_PLAN_V10.md` as the plan (v11).

Evidence labels: **[M]** measured by us and seen in a result file, **[R]** reported by an agent but not re-checked, **[S]** from a web search summary or vendor page, not read in full, **[P]** a plan or hypothesis.

## 1. The situation in six lines

1. We have a working small text decision model. Its accuracy and order stability are real. [M]
2. Nothing about its architecture is new. Three more papers found today make that final (section 4).
3. "Decision models" are now a crowded class: 30+ open-weight models, two public indexes, vendors from Cloudflare to Abacus. [S]
4. One finding of ours is not in any paper we have found: coverage sets and act/ask rules built on decision-model scores break when lookalike tools are added, and the obvious fix makes the model stop acting. [M]
5. That finding rests on one model, one crude attack and half-precision runs. It is not yet evidence a reviewer accepts.
6. The plan below turns it into a study across the model class plus a fix, built so that a paper exists whether or not our fix wins.

## 2. Why a decision pointer and not a language model

The reasoning holds, and it is the reasoning of the whole class, not ours alone.

- A generating model writes the tool name token by token. It can invent tools, it is slow, and its confidence is hard to read.
- A decision model scores the listed options in one pass and returns a probability for each. It cannot name a tool that is not on the menu, and the probabilities can be calibrated and thresholded.
- Jev, then the open Kev, then Drex, D3, Valen, OneJev, Clef and Smaug all follow from this. So the class is not our contribution. What we do with the probabilities can be.

The consequence that matters: every one of these systems tells users to act when the probability clears a threshold. Whether that rule survives a manipulated menu is the question we can own.

## 3. What the code and results support today

### 3.1 Code

| Piece | File | State |
|---|---|---|
| Pointer model (request first, isolation, shared positions, refiner) | `veyra/python/src/soro/routing/upp.py` | Works; locked checkpoint `ckpt_A` |
| Trainer | `veyra/training/p0_upp_ablation.py` | Works; default backbone name differs from the one used |
| Conformal sets | `soro/routing/conformal.py` | Correct |
| Conformal action eval | `veyra/training/eval_conformal_action.py` | Clips the rank; has uncommitted edits |
| Media encoder | `soro/routing/media.py` | Audio or image, one at a time, packed before the question. No trust split |
| Earlier poisoning defences | `soro/routing/poison_defenses.py` | Exists; reusable for the attack suite |
| Multi-model benchmark | `veyra/training/benchmark_decision_models.py` | Already loads Kev-0.8b and Soro models. Seed of the backend harness |
| Phase A generators and results | `scratch/` | **Git-ignored. None of the Phase A evidence is tracked or in the ledger** |

### 3.2 Results and what each one supports

| Result | Supports | Does not support |
|---|---|---|
| 0.6B: 86.00% external (1,032/1,200), Hammer-1.5B 82.58%, xLAM-1B 73.42% [M] | "Competitive for its size on our external set" | Any claim on public benchmarks |
| 0 flips over 5 orders, fp32, 5,207 rows [M] | Order stability at full precision | Half precision (spread 0.85 logits in bfloat16) |
| 4B: 89.58% external [M] | Scaling helps | Zero flips (ledger shows 23/5,007 in one place and 2/1,200 in another) |
| Readiness head: AUC 0.9016, ask recall 58.93% [M] | A readiness signal exists in frozen features | A working ask policy |
| Canonical When2Call 33.19% against Drex 89.7% [M] | We are far behind on ask/abstain benchmarks | |
| Gemma 4 E2B text: 84.08% bf16, abstain rows 40.74% [M] | The multimodal backbone trains | Any speech or image result |
| Phase A2: softmax coverage 89.14% to 67.04% under lookalikes [M, file checked] | The failure exists on our model | Generality; realism of the attack |
| Per-option coverage unchanged; acts on 10.93% clean, 3.46% attacked [M] | The robustness and its cost | A usable system |
| Recalibrated softmax: 89.43% coverage, acts on 5.49% [M] | Per-option matches it without seeing the attack | An advantage on clean traffic |
| MiniLM cosine with conformal: set size 1.54 at 90.4% (ledger) [M] | A plain pointwise scorer may already give smaller sets than our raw per-option score (2.46) | Nothing yet; this must be run as a baseline |

### 3.3 Faults found in the Phase A evidence

- All Phase A runs used bfloat16, where even a correct mask moves scores.
- Lookalike tools are named `fake_…`, built from each request's keywords, and written as a plain sentence while real tools are JSON cards. The format difference alone could change scores.
- "Softmax" was taken after the refiner and "per-option" before it. Two things changed at once. A softmax over the same pre-refiner scores is missing.
- The lookalike audit was done by the agent that generated the rows.
- Public 4B model card says 115 base queries for the 1,200 rows; our splits use 321 groups. Unreconciled.

## 4. What we researched and what it closed

### 4.1 Claims that are closed

| Claim | Closed by |
|---|---|
| Order-invariant option scoring | Set-LLM, PCW, InvariRank, CompRank, Drex appendix C.2, **Jeva (2610.18773)** |
| Coverage unchanged when distractors are added | **Conformal Evidence Sets (2611.10335), section V-I** |
| Pointwise scores with conformal thresholds | TRAQ (NAACL 2024) |
| Prune with a conformal set, then compare inside it | **Prune 'n Predict / CROQ (ICML 2025)**, tested on ToolAlpaca |
| Act on a single option, otherwise ask | KnowNo, CICC, Conformal Cascade |
| Trusted plan before untrusted evidence | PlanGuard, CaMeL, CaMeL-NOVA |
| A robustness benchmark for decision models | **DecisionRobust (2610.19118)**: 30 text and 17 vision configurations, perturbation and instruction injection |
| A small speech decision model | Smaug-Audio-Decisions-0.7B (Abacus, 2 Nov 2026) [S] |
| Multimodal decision model | Drex Max, D3, Valen, OneJev, Clef-Omni, Smaug-Decisions [S] |

New today and not yet read in full: Jeva, DecisionRobust, the two decision indexes, Smaug-Audio. Jeva is the closest architecture to ours: options encoded separately by a shared encoder, no flips, a separate estimate of "some option fits", 2,048 candidates [S]. DecisionRobust removes the simple version of our fallback benchmark paper.

### 4.2 What the mathematics gives and does not give (from the audit)

- With a per-option score and clean calibration, the correct tool stays in the set under any change to the other tools. This is a corollary of known results.
- If the system acts only when the original set has one tool, the chance of "acted and wrong tool" is at most α.
- The error among requests acted on is bounded only by α divided by the share acted on. At 10% acting this bound says nothing.
- If anything narrows a larger set and then acts, the bound is gone. A set of {correct, malicious} has full coverage and can be wrong every time.
- None of it covers arguments, readiness, permissions or whether the correct tool is on the menu at all.

### 4.3 Competitor landscape

From vendor pages through a pasted review and my searches. All [S]; none run by us.

| Model | Inputs | Notes for us |
|---|---|---|
| Drex v1.5 / Max | Text; Max adds image, video | 89.7 on When2Call; 4.3 to 5.9% flips |
| D3 (vLLM Semantic Router) | Text, image, video | 0.6B to 27B; router has tool-need and tool-rank steps; thresholds default to 0.5 |
| Valen 1.5 | Text, image, video, boxes | Vendor docs reportedly admit order dependence |
| OneJev 1.6 | Text, image, frames | Self-reported results |
| Clef / Clef-Omni (Cloudflare) | Text, image, audio, video | Open weights for Clef; 30B MoE for Omni |
| Smaug-Decisions, Smaug-Audio-0.7B | Text, image, audio | Open weights; audio capped at 30 s |
| Jeva-4B | Not confirmed | Independent option encoding; academic paper |

Size, multimodality and order stability are each matched by someone. None of these pages reports behaviour under a manipulated option set, and none gives a guarantee on wrong actions.

## 5. The gaps that remain

| # | Gap | Evidence it is open | Risk |
|---|---|---|---|
| G1 | No study of option-set manipulation (lookalike, cloned or promoted tools) on decision models | DecisionRobust covers perturbation and instruction injection; an extended search found no option-set test | Its full text may include one. Audit L1 |
| G2 | No one measures selective execution (share acted on, wrong among acted, deferral under attack) for these models | Indexes report accuracy and calibration only | Medium |
| G3 | No comparison of menu-normalised and per-option scoring for act/ask decisions on tools, with CROQ and pointwise conformal as baselines | Audit found the parts, not the comparison | Jeva's "some option fits" estimate may already be the per-option answer. Audit L2 |
| G4 | No answer to "who resolves a set of two" that an attacker cannot steer and that still lets third-party tools win | Audit confirmed the hole | Signed manifests (ETDI) may cover most of it. Audit L3 |
| G5 | Speech as the trusted request with the same act/ask accounting | Smaug and Clef take audio but report no such test | Lowest priority; our speech data has not passed quality checks |

## 6. Direction (plan v11)

### 6.1 The paper

**Working title.** When can a decision model be trusted to act? Selective tool routing under option-set manipulation.

**Claim to test.** Decision models are deployed to authorise tool calls from their probabilities. That authorisation fails when the option set is manipulated, across the model class. Scores that do not depend on the other options keep wrong actions bounded but stop acting. We measure the trade-off and test whether an absolute-score head with a trust-priority rule removes most of the cost.

**Four questions.**

| | Question | Experiments |
|---|---|---|
| Q1 | Is the failure general? | Same attack suite on 6 or more decision models through one backend interface |
| Q2 | Which scoring designs are immune, and at what cost? | Softmax and per-option from the same scores; MiniLM with conformal; CROQ; recalibrated softmax; Jeva if weights exist |
| Q3 | Can the cost be removed? | Absolute-score head; trust-priority rule; risk against share-acted curves |
| Q4 | Does it carry to speech and screenshots? | Spoken request as trusted input; screenshot as untrusted evidence |

**Why this shape.** Q1 and Q2 give a paper even if our method loses. Q3 gives the method paper if it wins. Q4 is added only if its results are real. Your wish for interchangeable backends is the infrastructure Q1 needs, so product and paper share that work.

### 6.2 Gates

| Gate | Passes if | If it fails |
|---|---|---|
| A. General | Under request-blind lookalikes in correct card format, wrong actions at least double on 4 or more models, 2 of them third-party decision models whose published number we first reproduce | Model release and a short paper only |
| B. Fix wins | At equal wrong-action rate our head acts on clearly more requests than MiniLM with conformal, CROQ and recalibrated softmax, clean and attacked | Analysis paper built on Q1 and Q2 |
| C. Modalities | Speech stage 1 within 3 points of text on quality-checked audio; screen text cannot change the stage 1 set | Text-only paper |

The earlier bar of 60% single-tool decisions stays as a go/no-go on 20 Nov. The paper reports the whole curve.

### 6.3 Venue

- ICML (late January, date unconfirmed) is not realistic for Q1 across six models plus Q4.
- Target: arXiv preprint of the text result in January, because this field produced Jeva and DecisionRobust in one week of October. Then NeurIPS 2027 main track in May, with the datasets and benchmarks track as the fallback.
- I cannot promise acceptance. What I can say is that this design has no step that depends on an unaudited novelty claim.

### 6.4 Two tracks, kept apart

| | Paper track | Product track (Veyra) |
|---|---|---|
| Goal | Answer Q1 to Q4 | A tool router people can deploy |
| Shared | Backend interface, attack suite, trust labels on tools | Same |
| Only here | Controlled comparisons, seeds, baselines | Tool registry across Python, REST and MCP; video; argument readiness; outcome learning; 8B to 27B and MoE sizes |

Product-track items do not enter the paper unless a gate needs them. Video and larger models are parked until the text result is done.

### 6.5 Ideas not yet cleared

Mine or from the pasted reviews. No work until the audit task beside each is done.

| Idea | Audit |
|---|---|
| Trust-priority resolution: act when exactly one tool in the set is from a trusted source; a third-party tool can win only when no trusted tool is in the set | L3 |
| Outcome evidence as the tie-breaker: a tool with no verified outcomes cannot be acted on alone | L6 |
| Readiness on the chosen tool as a second veto | Already measured; needs a harder ask set |

## 7. Decision points

| Date | Decision |
|---|---|
| 20 Nov | Head result and rebuilt attack: is gate B plausible? |
| 5 Dec | Gate A across backends: method paper, analysis paper, or release only |
| 20 Dec | Gate C: modalities in or out |
| Mid Jan | Preprint |

## 8. Rules

- No "first" without the searches and the papers read named beside it.
- No number about another model until our harness reproduces one of its published numbers.
- fp32 for every table in the paper. Half precision only with a control.
- One variable per run. Softmax and per-option compared from the same scores.
- Every attack row audited by someone other than its generator.
- Every result file in a tracked folder and in the ledger on the day it lands.
