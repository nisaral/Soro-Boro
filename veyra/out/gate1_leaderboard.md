# Gate 1: Leaderboard Oracle Headroom Report

**Dataset:** `harborframework/terminal-bench-2-leaderboard` (Terminal-Bench 2.0)
**Filter Criteria:** Valid submissions only (`timeout_multiplier == 1.0`, no overrides, >=5 trials/task, single model held fixed).
**Matched Attempts:** Oracle over m agents at 1 trial each vs Null (best-of-m trials for single best agent).

## Summary by Fixed Model Group

| Model | Agents (m) | Best Agent | Best Pass Rate | Oracle Rate | Null Rate (best-of-m) | Net Headroom | 95% CI | MDE (80%) | Margin | Decision |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `gpt-5.3-codex (all 6 agents: Sage, Droid, Mux, CodeBrain-1/1.5, spoox)` | CodeBrain-1, CodeBrain-1.5, Droid, Mux, SageAgent, spoox-o-m (6) | CodeBrain-1.5 | 76.4% | 92.9% | 86.1% | **+6.75pp** | [+0.02pp, +16.95pp] | 12.79pp | 12.8pp | **INCONCLUSIVE** |
| `gpt-5.3-codex (triplet: SageAgent, Droid, Mux)` | Droid, Mux, SageAgent (3) | SageAgent | 78.4% | 88.1% | 85.0% | **+3.13pp** | [+0.73pp, +6.04pp] | 3.79pp | 5.0pp | **INCONCLUSIVE** |
| `gpt-5.3-codex (pair: SageAgent, Droid)` | Droid, SageAgent (2) | SageAgent | 78.4% | 85.3% | 82.9% | **+2.38pp** | [+0.49pp, +4.90pp] | 3.18pp | 5.0pp | **STOP** |
| `gemini-3.1-pro-preview (Forge Code, TongAgents)` | Forge Code, TongAgents (2) | TongAgents | 80.2% | 88.7% | 86.6% | **+2.11pp** | [-0.40pp, +5.03pp] | 3.90pp | 5.0pp | **INCONCLUSIVE** |
| `claude-opus-4.7 (vix, 0error Ledger)` | 0error Ledger, vix (2) | vix | 89.9% | 91.2% | 94.0% | **-2.79pp** | [-4.58pp, -1.08pp] | 2.56pp | 5.0pp | **STOP** |
| `claude-opus-4.6 (Mux, Meta-Harness)` | Meta-Harness, Mux (2) | Meta-Harness | 76.4% | 83.5% | 81.5% | **+2.00pp** | [-0.76pp, +5.14pp] | 4.34pp | 5.0pp | **INCONCLUSIVE** |

## Gate 1 Stop Rule Interpretation

- **CLEAR:** Headroom >= Margin AND 95% CI lower bound > 0 (Headroom clears detectable margin with statistical confidence).
- **STOP:** 95% CI upper bound < Margin OR Net Headroom <= 0 (Falsifiable stop rule: null confirmed or effect smaller than detectable margin).
- **INCONCLUSIVE:** Positive headroom exists but interval overlaps decision margin.

## Cost & Resource Usage

| Model | Oracle Total Cost (m trials) | Null Total Cost (m trials) | Delta Cost |
| :--- | :---: | :---: | :---: |
| `gpt-5.3-codex (all 6 agents: Sage, Droid, Mux, CodeBrain-1/1.5, spoox)` | $0.0000 | $0.0000 | $+0.0000 |
| `gpt-5.3-codex (triplet: SageAgent, Droid, Mux)` | $0.0000 | $0.0000 | $+0.0000 |
| `gpt-5.3-codex (pair: SageAgent, Droid)` | $0.0000 | $0.0000 | $+0.0000 |
| `gemini-3.1-pro-preview (Forge Code, TongAgents)` | $0.0000 | $0.0000 | $+0.0000 |
| `claude-opus-4.7 (vix, 0error Ledger)` | $0.0000 | $0.0000 | $+0.0000 |
| `claude-opus-4.6 (Mux, Meta-Harness)` | $2.1470 | $4.1223 | $-1.9752 |