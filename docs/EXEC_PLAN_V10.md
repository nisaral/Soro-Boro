# Execution plan v10 (16 Nov 2026)

Replaces v9. Built only on what the two novelty audits and the code pass left standing. No claim in this file rests on an unaudited idea; section 7 lists ideas that would raise the ceiling and must be audited before any work.

## 1. What the paper is

**Claim.** Coverage sets for tool decisions, as built today on menu-normalised (softmax or listwise) scores, lose their guarantee when the menu is manipulated or grows. Sets built on per-option scores read before any untrusted evidence do not. We build that system in one small pointer, with speech as the trusted request and the screenshot as untrusted evidence, and measure what it costs.

**What is ours, per the audits.** The construction in a decision pointer (independent pre-evidence score, conformal set P, listwise refinement only inside P, trust-split packing) and the measured comparison. Not ours: any theorem, isolation masks, conformal tool sets, singleton-act, reference sets, speech tool calling, screenshot injection defence.

**What decides the venue.** Three bars. All three: main-track submission. First two only: a strong text paper. First fails: benchmark paper (section 6).

| Bar | Passes if |
|---|---|
| A. The failure is real and broad | Under injected or lookalike tools, coverage of softmax-based sets falls by 15 points or more on at least three existing pipelines, including a valid Drex run |
| B. The fix is usable | Per-option sets: coverage holds under every attack with the correct tool present; wrong-action rate at or below α; single-option rate on clean traffic 60% or more at 90% coverage |
| C. It carries to speech and screenshots | Speech stage 1 within 3 points of text; rendered-text attacks do not move stage 1; stage 2 residual and the deferral cost when the value is only on screen are reported |

## 2. Code facts to fix first (from the code pass)

1. Coverage is computed on softmax after the refiner. Move it to pre-refiner, per-option scores.
2. Media and state are packed before the question, so every option sees a screenshot in stage 1. Split packing by trust.
3. `eval_conformal_action.py` clips the conformal rank; `soro/routing/conformal.py` is correct. Use one.
4. Ties are broken by menu position. Break them by a hash of the option key.
5. The external 1,200 rows contain repeated views of a request. Use group-aware splits and intervals.
6. The media encoder takes audio or image, not both with different trust.

## 3. Phase A, 16 to 20 Nov: decide

Evaluation only. No training.

| # | Task | Output |
|---|---|---|
| A0 | Fixes 3, 4, 5 | Valid tables |
| A1 | Per-option, pre-refiner scores from the locked 0.6B on the external rows; split conformal at 90% | Coverage, set size, single-option rate |
| A2 | Same rows with injected tools: lookalikes, attractive-metadata text, instruction-carrying descriptions. Compare softmax sets and per-option sets on our model | Coverage and wrong-action rate under attack |
| A3 | Gemma mask check: (a) run the locked Qwen 0.6B in bfloat16 on the same rows and record its spread; (b) run Gemma in fp32 on 100 rows, on CPU or across two GPUs | Whether Gemma's spread of 0.22 is rounding or a mask leak |

Reading A3: the Qwen mask is known to be correct, so its bfloat16 spread is the reference. If it is also near 0.2, Gemma is fine. If it is near 1e-3, Gemma has a leak and nothing multimodal starts until it is fixed.

**Decision on 20 Nov.** A2 shows a clear separation and A1's single-option rate is workable: go to Phase B. Separation but poor single-option rate: train an absolute-score head (the unused RBF head) and repeat A1. No separation: go to section 6.

## 4. Phase B, 20 Nov to 2 Dec: make the text result unarguable

| # | Task |
|---|---|
| B1 | Valid Drex baseline: native protocol, full precision, one published number reproduced first. Until then the 73.92% and 33% figures stay quarantined |
| B2 | Breadth for bar A: softmax-based sets on Drex, Hammer, xLAM, a KnowNo-style multiple-choice LLM, and the conformal-tool-exposure pipeline (check whether its scores are per-tool or normalised) |
| B3 | Baseline defences on fixed menus: PlanGuard, Tool-Guard, a plain per-option cross-encoder |
| B4 | Attack suite from published attacks: ToolHijacker, Attractive Metadata, Spoofing the Toolbox, MCPTox descriptions, catalog growth with benign lookalikes |
| B5 | Stage 2 inside P: refiner on, collisions, readiness on the chosen tool. What interaction recovers once the set is fixed |
| B6 | Residuals: no correct tool on the menu; tampered correct tool; attacker cost to force deferral |
| B7 | Three true seeds on every table row; 4B row |

## 5. Phase C, 2 to 16 Dec: speech and screenshots on the corrected packing

Starts only after A3 passes and fix 2 and 6 are in.

| # | Task |
|---|---|
| C1 | Trust-split packing: `[spoken or typed request] [options]` for stage 1; `[same request] [screenshot or tool output] [options in P]` for stage 2 |
| C2 | Gemma abstain repair: it scores 40.74% on abstain rows and 83.15% on zero-shot against 88.31% for Qwen. Longer training and a tuned abstain threshold before any speech run |
| C3 | Speech as request: twins, per-modality calibration, cascade baseline on the same menus and sets; external spoken sets where licences allow |
| C4 | Screenshot as evidence: minimal pairs (value on screen or absent), rendered-text attacks on stage 2, deferral cost |
| C5 | The text-to-speech coupling inequality reported as a corollary with its measured penalty, nowhere as a headline |

Do not run VPI-Bench through the vision tower before C1. With today's packing the image is in the trusted prefix, so the test would measure a design flaw we already know about.

## 6. If bar A fails: the benchmark paper

A released benchmark and evaluation of decision models: order stability, ask and abstain, coverage under menu manipulation, and injected twins across text, speech and screenshots, with Drex, Hammer, xLAM and ours. It does not depend on method novelty. Target: the NeurIPS datasets and benchmarks track (deadline usually May; confirm). Phases B4, C3 and C4 feed it directly, so no work is lost.

## 7. Ideas that could raise the ceiling: audit before any work

Unverified. Mine. Not part of the plan until a primary-source audit clears them.

1. **Small sets without giving up robustness.** Per-option sets are large because options do not compete. Allow competition only among tools of trusted provenance, and score third-party tools independently, so an untrusted tool cannot suppress a trusted one. This turns the mask into an information-flow policy. Prior work to check first: information-flow control for agents (FIDES, CaMeL), attention-level instruction/data separation.
2. **Benign catalog growth as the motivating case.** If adding ordinary lookalike tools after calibration is enough to break softmax-based coverage, the finding applies to every deployed agent, not only to attacks.

## 8. Dates

| Date | Milestone |
|---|---|
| 20 Nov | Phase A decision |
| 2 Dec | Text result complete |
| 16 Dec | Speech and screenshot results |
| 20 Dec to 10 Jan | Writing, ablations, preprint |
| Late Jan | ICML 2027 (confirm date) |
| May | NeurIPS 2027, main or benchmark track |

## 9. Rules

One variable per run; explicit seeds; results saved per split; fp32 for any flip claim, with a known-good control for any other precision; no number about another system until the harness reproduces one of its published numbers; no "first" without the searches and reads named beside it.
