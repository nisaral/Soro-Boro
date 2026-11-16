# Execution plan v6 (13 Nov 2026)

Companion to `RESEARCH_GUIDE_V5.md`. This file is the order of work. If something here conflicts with older docs, this wins.

## Decisions (made, do not reopen)

1. **Sizes:** 0.6B (efficiency claim) and 4B (accuracy claim). **No 8B/9B.** Reasons: exact-invariance evaluation needs fp32 compute; an 8B run would take most of a week's Kaggle quota per run; the paper's point is that stability and guarantees do not need a large model. Revisit only if other compute appears.
2. **Speech backbone:** Qwen3-0.6B and Qwen3-4B are text-only. Speech uses **Gemma 4 E2B** (native audio and vision towers, code in `routing/media.py`) with the same option-isolation mask. Three backbones in the paper = evidence the method is backbone-agnostic.
3. **Paper core:** order invariance (G1), coverage (G2), actions incl. the two kinds of ask (G3), speech with per-modality guarantee (G4). **Stretch:** early commit (G5), outcome cards (G6). **Out:** tool-result check, multi-turn RL.
4. **Teacher:** never the 4-bit 8B model again. Teacher = our own 4B once it passes its gate.
5. **RL:** not on the critical path. Single decisions use exact expected-cost loss. RL is allowed only for the early-commit stopping policy (G5), and only if the conformal rule is not enough.
6. **Targets (projected dates, confirm):** arXiv preprint by ~20 Dec 2026 (G1-G3 + first speech numbers). ICML 2027 (deadline usually late January) if G4 is done by ~15 Jan; otherwise NeurIPS 2027 (May).

## Standing rules

- Local 100-step smoke before every push. Every run saves its checkpoint, is <= 8 h, resumable.
- All evals: fp32 compute, 5 menu orders, paired tests, results appended to `docs/RESULTS_LEDGER.md` (config, seed, commit, every split).
- One variable per run. Final table rows get 3 seeds.
- CPU sessions for data, TTS, mining, baselines that fit on CPU.
- Reports separate "true by construction" from "measured gain". No superlatives.
- Do not cite a number about another paper unless it was read in that paper (the "Drex 4.3-16.2%" range in the last scorecard has no source for 16.2).

## Week 1 (14-20 Nov): text decisions

GPU budget ~20 h.

| # | Task | Compute | Gate |
|---|---|---|---|
| 1.1 | Stop/finish filter job; apply 15% rule; never rerun it | - | - |
| 1.2 | **S2 run 1**, 0.6B: 4 action cards, hard negatives, expected-cost loss | ~1 h GPU | When2Call MCQ reported vs 84.8; ASK recall > 0; external_s2 not below v3b |
| 1.3 | **S1 v3b on Qwen3-4B.** Match the quantisation and training setup of Soro-4B v2 as closely as possible; fp32 compute for eval | 6-8 h GPU | external >= 90.6, flips 0. If 4-bit costs accuracy, report and try 8-bit or full weights with gradient checkpointing |
| 1.4 | Finish baseline table: xLAM, Hammer, Arch on external 1,200 + collisions 421; full BFCL; fix cross-encoder | 1-2 h GPU | table complete |
| 1.5 | Data (CPU): collisions eval >= 1,500; near-miss eval >= 500; recast ToolRet-train and When2Call train as menus; relabel false hard negatives; `s2_gold_100` for owner | CPU | leakage firewall passes |
| 1.6 | **S2 run 2**, 0.6B: per-option 3-state head (no fit / fits, info missing / ready); prior-work check first | ~1 h GPU | beats run 1 on When2Call and ask/abstain confusion; else keep run 1 |
| 1.7 | Refiner proof: v3 vs v3b, 3 seeds, on the larger collisions eval. Cache backbone outputs so head-only variants cost minutes | 3-4 h GPU | paired test significant, or drop the refiner claim |

## Week 2 (21-27 Nov): scale and distil

| # | Task | Gate |
|---|---|---|
| 2.1 | S2 (best head) on 4B | When2Call >= 84.8 target; flips 0 |
| 2.2 | Distil 4B -> 0.6B: teacher logits on the same menus; round 2 on the student's own errors | 0.6B external >= 87; report gap to 4B |
| 2.3 | Step / LoRA-rank sweep on 0.6B (2-3 short runs) | pick final recipe |
| 2.4 | Conformal: coverage and set size per split, per menu size (2-5, 6-20), under shift; `none` option vs empty set | coverage within 2 pts of nominal in-split; honest shift table |
| 2.5 | Post-training: temperature per split, seed weight-averaging, 8-bit/4-bit check of flips and coverage | no loss of invariance or coverage |

## Week 3-4 (28 Nov - 11 Dec): speech

| # | Task | Gate |
|---|---|---|
| 3.1 | Port isolation mask + head to Gemma 4 E2B, **text only first** | text accuracy within 2 pts of Qwen 0.6B run; flips 0 |
| 3.2 | Merge 8 TTS shards; add noise/speed augmentation; held-out voices | twin data card |
| 3.3 | Speech twins training: shared labels, most-confident-modality distillation | speech within 3 pts of text; agreement > 95% |
| 3.4 | Baseline: Whisper -> text model cascade, clean and noisy | reported |
| 3.5 | External speech evals: Audio2Tool, Spoken Function Calling, Full-Duplex-Bench v3 (real speech), recast as menus where licences allow | reported |
| 3.6 | Per-modality calibration; then TTS -> real-speech shift with weighting | coverage on real speech reported |

## Week 5 (12-20 Dec): write and post

- Fill `RESEARCH_GUIDE_V5.md` section 4 structure with results. Ablation table. Limitations.
- Read in full every paper cited for a comparison (list in guide section 6).
- arXiv preprint. Hugging Face: 0.6B, 4B, speech model, data cards, eval harness.

## January (stretch, for ICML or NeurIPS version)

- G5 early commit: prefix training; commit when the conformal set is a singleton; error bound vs fraction of utterance heard; compare with RASSG-style gating. RL stopping policy only if needed.
- G6 outcome cards: stream eval with tools added, removed and failing; accuracy vs number of cards.
- Screenshots: GUI element choice as options (ScreenSpot-style), only if time.

## Cut rules (if behind)

1. Drop G6, then screenshots, then G5.
2. If 4B misses 90.6: report it, keep 0 flips as the claim, lead with guarantees and speech.
3. If the 3-state head does not beat 4 cards: keep 4 cards, move the idea to future work.
4. If speech on Gemma is not within 3 pts of text by 11 Dec: preprint goes out with G1-G3 only.

## Owner tasks (cannot be delegated)

- Hand-check `s2_gold_100`.
- Confirm ICML 2027 / NeurIPS 2027 dates.
- Read Drex and Set-LLM yourself.
- Revoke the old Kaggle token if not done.
