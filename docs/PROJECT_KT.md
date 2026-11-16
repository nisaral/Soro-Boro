# Soro project knowledge transfer (16 Nov 2026)

One document for the whole story: what we set out to do, what we planned, what failed, what held up, and where the paper stands today. Numbers are measured unless marked otherwise. Older documents this replaces as the entry point: `HANDOFF.md`, `NORTH_STAR.md`, `PAPER_KT.md`. The current plan is `EXEC_PLAN_V10.md`; the prior-art register is `PAPER_LITERATURE_NOTES.md`.

## 1. Summary

- **Goal.** A main-track paper (ICML or NeurIPS 2027) and a Hugging Face release for a small decision model: given a request and a menu of tools, pick one, ask, or abstain, across text, speech and screenshots, with a coverage guarantee.
- **What works.** A 0.6B pointer model that scores 86.00% on our external 1,200 rows, beats Hammer-1.5B and xLAM-1B on that set, and never changes its answer when the menu is reordered (in fp32).
- **What failed.** Every novelty claim we tried to build on top of it: order invariance, conformal tool sets, set-as-action, and injection defence are all published. Action cards hurt tool choice. The canonical When2Call score is 33.19% against 89.7% for Drex.
- **Where the paper stands.** One measured finding survives: coverage sets built on softmax scores break when lookalike tools are added; sets built on per-option scores do not, but today they defer on almost everything. One experiment (an absolute-score head) decides whether this is a method paper or a benchmark paper. Decision date: 20 Nov.

## 2. The problem and the vision

**Problem.** An agent must choose among listed tools, and also know when to ask the user or do nothing. Large models do this slowly and without guarantees. Drex (9B to 35B, 1.15M training records) owns the "plain decision model" space, so a small model cannot win on scale.

**Vision (12 to 13 Nov, `NORTH_STAR.md`).** "Decision models with guarantees", 0.6B to 4B, one forward pass:

| Label | Promise |
|---|---|
| G1 | Zero answer changes under any menu order, plus a small refiner so options can still be compared |
| G2 | Split conformal sets with finite-sample coverage, per modality |
| G3 | The set decides the action: empty = abstain, one = act, several = ask |
| G4 | Raw speech in, with a bounded-error early commit mid-utterance |
| G5 | Test-time outcome cards so the model adapts to tool failures without retraining |

Screenshots were added to this as a third modality ("Soro-Kev-Omni").

## 3. Timeline

| When | What happened | Outcome |
|---|---|---|
| Before 12 Nov | Architecture ablation: query-first pointer (A) against block, cross-attention and late-gist layouts | A won clearly (0.858 against 0.342 and 0.250 at 1,000 steps). Closed |
| 12 Nov | S0: six papers read; 842 errors of the 4B model bucketed | Top buckets: name-overlap swaps 283, false calls 192, over-abstain 162 |
| 12 Nov | S1 with shuffle and order-KL loss | Accuracy up, flips stuck at 5%. A loss term does not give invariance |
| 13 Nov | Option isolation mask + shared positions + refiner ("v3b"), fp32 | 0 flips. Model locked |
| 13 to 15 Nov | S2 action cards, three-state heads, When2Call recasts, baselines, 4B runs | Tool choice damaged; When2Call far below Drex |
| 15 to 16 Nov | Readiness head on frozen features; Gemma 4 E2B text run; speech clips generated | Readiness signal exists; Gemma trains; speech quality check not passed |
| 16 Nov | Two literature audits and a code pass by a second agent | The G1 to G3 novelty claims and my "ladder of guarantees" pitch were prior art |
| 16 Nov | Plan v10, Phase A1 to A3 | Softmax sets break under lookalikes; per-option sets hold but defer |

## 4. The locked model

`ckpt_A` / `v3b_fp32` on `Qwen/Qwen3-0.6B-Base` (confirm through the adapter config; the script default names a different model).

- The request comes first. Each option attends to the request and to its own tokens only.
- All options start at the same position index, so position carries no order information.
- A dot product between the request vector and each option vector gives the score.
- A one-layer refiner then lets option vectors see each other, in a way that is the same for any order.
- Code: `veyra/python/src/soro/routing/upp.py`; trainer `veyra/training/p0_upp_ablation.py`.

## 5. What was successful

### 5.1 Accuracy for size (external 1,200 rows)

| Model | Overall | Tool rows | Abstain rows |
|---|---|---|---|
| Soro 0.6B (locked) | 86.00% | 86.38% | 82.96% |
| Soro 4B v2 | 90.58% | | |
| Hammer-1.5B | 82.58% | 87.23% | 45.93% |
| xLAM-1B | 73.42% | 75.40% | 57.78% |
| MiniLM retrieval | 79.17% | | |
| BM25 | 58.67% | | |

The lead over Hammer comes from abstaining correctly, not from tool choice.

### 5.2 Order stability

- 0 answer changes over 5 menu orders in fp32; score spread at most 1.99e-5.
- Without isolation: 8.08 to 8.12% of rows change answer, 28.74% on name collisions.
- In bfloat16 the same correct mask gives a mean spread of 0.85. Zero flips is an fp32 result; at half precision a fixed menu order is also needed.

### 5.3 Other things that held

- **Readiness head.** A small head on the frozen pointer, with train and test tools kept apart: accuracy 88.4%, AUC 0.9016. It catches 96.91% of "ready to call" rows but only 58.93% of "needs more information" rows.
- **Gemma 4 E2B trains as a backbone.** External 84.08% in bfloat16. Its score spread (0.22) was cleared as rounding by a Qwen control.
- **Process.** A results ledger, group-aware splits, a quarantine rule for unvalidated numbers, and an independent literature register.

## 6. What failed, and why

| What we tried | Result | Lesson |
|---|---|---|
| Order-KL loss for invariance | Flips stayed at 5% | Invariance has to come from the architecture |
| Refiner to fix name collisions | 70.31% against 68.65% without it, p = 0.40 | Unproven; do not claim it |
| Isolation, on collisions | 70.31% against 73.40% without isolation | Isolation costs accuracy where options must be compared |
| Action cards in the menu (4-card router) | Tool rows fell to 76 to 83%, collisions to about 60% | Pick the tool first, then decide readiness |
| Recast When2Call | 51 to 56% on 0.6B, 62.08% on 4B | The recast did not match the benchmark |
| Canonical When2Call (3,652 rows) | 33.19% zero-shot against 89.7% for Drex v1.5 | Training data had bare cards, artificial "ask" rows and a different tool source |
| Our Drex run (4-bit) | 73.92%, 33% flips | Quarantined: the harness never reproduced a published Drex number |
| 4B with isolation | 89.58%, with unexplained flips | Open |
| Gemma abstain rows | 40.74%; zero-shot 83.15% against 88.31% for Qwen | Needs longer training and a tuned threshold |
| Gemma in fp32 | Out of memory on one T4 | Use two GPUs or CPU for the 100-row check |
| Speech clips (42,057 Kokoro) | 30% word error on a 30-clip check | Quality check not passed; no speech result yet |
| Action dataset "300k" | The file holds 24,000 menus | Do not quote 300k |
| Screenshots | Media is packed before the question, so every option sees it | Trust-split packing is not implemented |

### 6.1 The novelty failure

This was the largest setback and it was partly my error: I proposed claims before the literature was fully read.

| Claim we wanted | Already published in |
|---|---|
| Isolation, shared positions, order-invariant scoring | Set-LLM, PCW, InvariRank, CompRank, Drex appendix C.2 |
| Conformal sets and ask/defer rules for agents | KnowNo, Conformal Cascade, CICC, ACI, CCPO, PACE, ToolChain-CRC, a public conformal-tool-exposure repo |
| Injection defence for tool selection | MELON, CaMeL, PlanGuard, Tool-Guard, Task Shield, ClawGuard, AgentDojo |
| Tool-menu attacks | ToolHijacker, MCPTox, Attractive Metadata, ToolTweak, Spoofing the Toolbox, ToolFlood |
| Spoken and visual injection | CADV (audio), VPI-Bench (screens); Drex Max takes images |

What the audits did not find in any paper: a per-option score read before untrusted evidence, a conformal set on that score, and a measured comparison against softmax sets under menu manipulation. The mathematics is elementary, so the paper depends on the numbers.

## 7. Phase A results (16 Nov)

100 group-aware splits, target coverage 90%.

| Stream | Method | Coverage | Acts on | Wrong, of all requests | Wrong, of acted |
|---|---|---|---|---|---|
| Clean | Softmax sets | 89.14% | 83.19% | 6.53% | 7.58% |
| Clean | Per-option sets | 89.39% | 10.93% | 3.51% | 32.87% |
| Clean | Margin over abstain | 90.42% | 13.77% | 5.37% | 37.10% |
| Lookalike tools | Softmax, calibrated on clean | 67.04% | 60.78% | 29.71% | 49.51% |
| Lookalike tools | Softmax, recalibrated on attack | 89.43% | 5.49% | 3.50% | 62.36% |
| Lookalike tools | Per-option sets | 89.38% | 3.46% | 2.89% | 72.26% |

- Adding 3 to 10 real tools moved softmax coverage by 1.08 points. Instruction-carrying descriptions moved it by 0.19. Only lookalikes break it.
- Per-option coverage holding is true by construction, not a finding. The finding is its cost: it acts on 11% of clean requests.
- Per-option sets match recalibrated softmax under attack without having seen the attack.

**Known weaknesses of this evidence.** One model and one attack. The injected tools are named `fake_…` and are written from each request's keywords. The lookalike is wrong only by origin, so a reviewer will ask why a signed allowlist is not enough. The audit of the lookalike rows was done by the agent that generated them.

## 8. Open items, in order

1. Train an absolute-score head (per-option yes/no loss on frozen pre-refiner features) and repeat A1 and A2. Target: 60% or more single-tool decisions on clean traffic at 90% coverage.
2. Run Hammer and xLAM on the lookalike stream.
3. Rebuild the lookalike stream: no `fake_` names; one version written without seeing the request.
4. Score a trust-priority rule (act when exactly one tool in the set is from the original catalog), including the case where the correct tool is third-party.
5. Audit whether scoring or resolving by tool origin is published (ETDI, FIDES, CaMeL), with quoted passages.
6. Valid Drex baseline: native protocol, full precision, one published number reproduced first.
7. Trust-split packing, then speech as request and screenshot as evidence.
8. Three true seeds on every reported row; the 4B flips; the speech quality check.

## 9. Decision on 20 Nov

| Result | Path |
|---|---|
| Head reaches 60% and the attack survives the rebuild | Method paper. Claim: fails to deferral, not to wrong actions, without knowing the attack. Continue to Phase B and C of v10 |
| Head stays low | Benchmark paper (NeurIPS datasets and benchmarks track, usually May): order stability, ask and abstain, coverage under menu manipulation, across text, speech and screenshots |

## 10. Rules learned

- No "first" without the searches and the papers read named beside it.
- No number about another system until our harness reproduces one of its published numbers.
- fp32 for any flip claim; a known-good control for any other precision.
- One variable per run, explicit seeds, group-aware splits.
- Report accuracy on requests acted on beside every joint wrong-action rate.

## 11. Numbers that must not be used

- Drex at 73.92% or 33% flips (our unvalidated 4-bit run).
- "300k" action examples.
- Tool-Guard "3.7× latency".
- "Bit-exact" or zero flips for any half-precision run.
- p = 1e-161 against an untrained model; the AskOrExact metric; any three-seed claim where a seed was duplicated.
- "Bar A passed" or "integrity passes" for the Phase A tables.

## 12. Owner reminders

- Revoke the Kaggle API token after the runs (Kaggle Settings, API). It must never be written to the repository.
- Confirm the ICML and NeurIPS 2027 deadlines.
- Read 20 lookalike rows and hand-check `s2_gold_100` yourself.
- None of the documents written in this period are committed.
