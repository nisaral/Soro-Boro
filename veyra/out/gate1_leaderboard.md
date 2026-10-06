# Gate 1 Advanced Analysis: Three Bounds, Cost Cascades, and Task Complementarity

**Dataset:** `harborframework/terminal-bench-2-leaderboard` (Terminal-Bench 2.0, 89 Tasks, Static Leaderboard Data)  
**Analysis Discipline:** Model held strictly fixed, matched attempts ($m$ agents $\times$ 1 attempt vs $m$ retries on best agent), out-of-sample Winner's Curse check (trials 1–2 train, 3–5 test), task-bootstrap standard errors.

---

## 1. Summary of the Three Bounds across Cohorts

| Model & Cohort | Agents ($m$) | Bound 1: Best Fixed (In-Sample / OOS) | Bound 1: Null (Best-of-$m$) | Bound 2: Routing Oracle (Pre-Run Ceiling) | Bound 2: 5-Fold Task CV Router | Bound 3: Cascade Union Oracle | Bound 3: Net Headroom vs Null [95% CI] | Task Disjointness (Complementary Tasks) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **GPT-5.3-Codex (Vendor Triplet)** | 3 | SageAgent (78.4% / 78.7%) | 85.0% | **85.5%** (+7.02pp) | 78.4% | **88.1%** | **+3.13pp** [+0.83pp, +6.02pp] | 19 / 89 tasks (21.3%) |
| **GPT-5.3-Codex (Vendor Pair)** | 2 | SageAgent (78.4% / 78.7%) | 82.9% | **83.4%** (+4.94pp) | 78.4% | **85.3%** | **+2.38pp** [+0.49pp, +4.81pp] | 11 / 89 tasks (12.4%) |
| **GPT-5.3-Codex (All 6 Available)** | 6 | CodeBrain-1.5 (76.4% / 77.3%) | 86.1% | **88.2%** (+11.82pp) | 66.1% | **92.9%** | **+6.75pp** [+0.01pp, +16.93pp] | 12 / 22 tasks (54.5%) |
| **Gemini 3.1 Pro (TongAgents + Forge)** | 2 | TongAgents (80.2% / 78.3%) | 86.6% | **88.1%** (+7.87pp) | 80.2% | **88.7%** | **+2.11pp** [-0.40pp, +5.03pp] | 12 / 89 tasks (13.5%) |
| **Claude Opus 4.7 (vix + 0error)** | 2 | vix (89.9% / 90.3%) | 94.0% | **90.6%** (+0.67pp) | 89.9% | **91.2%** | **-2.79pp** [-4.58pp, -1.08pp] | 41 / 89 tasks (46.1%) |
| **Claude Opus 4.6 (Meta + Mux)** | 2 | Meta-Harness (76.8% / 77.4%) | 82.0% | **81.0%** (+4.20pp) | 76.8% | **83.1%** | **+1.09pp** [-1.28pp, +3.70pp] | 14 / 81 tasks (17.3%) |
| **Gemini 3 Flash (Dirac + Gemini CLI)** | 2 | Dirac (65.9% / 67.4%) | 71.6% | **69.1%** (+3.18pp) | 65.9% | **71.1%** | **-0.50pp** [-2.50pp, +1.59pp] | 27 / 88 tasks (30.7%) |

---

## 2. Branch A: Cost at Equal Success & Cheap-First Cascades

| Model Cohort | Best Fixed Cost / task | Null (Best-of-$m$) Cost / task | Cheap-First Cascade Cost / task | Cost Savings at Equal/Superior Success |
| :--- | :---: | :---: | :---: | :---: |
| **Claude Opus 4.7 (`vix` + `0error`)** | $0.8991 | $1.7983 | **$1.0869** | **39.6% reduction** |
| **Claude Opus 4.6 (`Meta` + `Mux`)** | $2.0812 | $4.1624 | **$2.1470** | **48.4% reduction** (logged spend) |
| **GPT-5.3-Codex (`Sage` + `Droid` + `Mux`)** | $0.2140 | $0.6420 | **$0.3120** | **51.4% reduction** (token derived) |

---

## 3. Task-Level Complementarity Analysis (Disjoint Solves)

Across the 19 complementary tasks in the GPT-5.3-Codex triplet (`SageAgent`, `Droid`, `Mux`):
- **Systems & Compilation:** `compile-compcert`, `make-mips-interpreter`, `polyglot-c-py`, `polyglot-rust-c`, `qemu-alpine-ssh`, `sqlite-with-gcov`
- **Database & Storage:** `db-wal-recovery`, `query-optimize`
- **Scientific & ML:** `dna-insert`, `mcmc-sampling-stan`, `model-extraction-relu-logits`, `torch-tensor-parallelism`, `mteb-retrieve`, `mteb-leaderboard`
- **Network / Protocol:** `configure-git-webserver`, `mailman`, `gcode-to-text`, `winning-avg-corewars`