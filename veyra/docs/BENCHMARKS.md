# Benchmarks

Primary evaluation is **Harbor**, not MCPAgentBench. Harbor is the official Terminal-Bench 2.0 harness, records tokens, cost, duration and reward, and already wraps Claude Code, OpenHands, Codex CLI, Terminus-2, and mini-SWE-agent. Veyra should be a Harbor **agent**. Derive `HandoffV1` from **ATIF**, not a private format.

## Initial order (spend nothing until step 0)

| Step | What | Why | Cost |
|---|---|---|---|
| 0 | Public Harbor release (8 models × Terminus-2 vs native, 54 benches, 3 trials) | Oracle gap + 3-trial null if per-task outcomes exist. Lower bound with two harnesses. | $0 |
| 1 | Terminal-Bench 2.0 (89 tasks) | Harbor-native, verifier-scored. Mid-strength model. Arms: Terminus-2, mini-SWE-agent, Veyra. 3 seeds. Pilot 20 first. | 89×3×3 = 801 after pilot |
| 2 | One SWE-style Harbor adapter (~100 tasks, **split by repo**) | External harness, leakage-safe split | After $/run known |
| 3 | Aider Polyglot | Cheap, large published harness gaps | Cheap |
| 4 | Harbor-Index (82 hard tasks) | Breadth, low pass rates → rescue candidates | After 1–2 |
| 5 | STT-Arena (227 tasks, 30 impossible) | Shift + abstain. Simulated tools → strawman risk if only in-repo harnesses | Later |
| smoke | MCPAgentBench | Tool-call plumbing only | Do not headline |
| later | ToolSandbox, τ²/τ³-bench, TUA-Bench, SWE-bench | Stateful / user / terminal / SE | After Gate 1 |

## Controls every public table must include

- Same-harness resampling (best-of-k)
- Random switch
- Fresh restart in the same harness
- Best **fixed** harness
- Always-escalate
- Embedding router
- Embedding-pruned handoff (bar for Kev)

Primary metrics: **deterministic verifiers**. LLM-judge scores are secondary. Count controller tokens, handoff tokens, wall-clock, cache misses.

## Outcome matrix

Parquet columns: `task, arm, seed, pass, tokens, cache, cost, time, steps, failure_tag`.

## Status

| Suite | Status |
|---|---|
| Scripted 30-task / `out/kev` | Measured, **synthetic** |
| MCPAgentBench Gemma 1-task smoke | TFS 0.0; model wrote `tool_code` text, not function calls |
| Harbor public re-analysis | Not started |
| Terminal-Bench 2.0 | Not started |
