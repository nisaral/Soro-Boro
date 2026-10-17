# Constrained Belief-State Recovery Controller — Limitations & Promotion Review

**Date:** October 8, 2026  
**Status:** Experimental Module Candidate  
**Directive Reference:** Veyra Algorithmic Upgrade (§18, §20)  

---

## 1. Limitations & Current Failure Modes

While the Constrained Belief-State Controller demonstrates superior safe recovery on the heterogeneous benchmark suite ($83.3\%$ vs $50.0\%$ for B6/B2 and $33.3\%$ for current Veyra), several important limitations must be maintained:

1. **Irreducible Ambiguity (Zero Information Asymmetry):**
   - When an external system provides no read-only status probe, no idempotency key, and no external journal ref (Scenario S3), the controller cannot conjure information from thin air. Under $P(\text{unsafe}) \le \epsilon$, the mathematical optimum remains **`DEFER`**. Veyra cannot recover tasks when the underlying API provides zero observability.
2. **Probe Dependability & Latency:**
   - Evidence acquisition introduces an additional network call. If a probe itself times out or exhibits stale caching, the posterior belief may remain ambiguous, causing a fallback to `DEFER`.
3. **No Automatic Probe Synthesis:**
   - The controller only executes declared, contract-specified evidence probes. It does not use an LLM to guess or synthesize arbitrary probes against undocumented API endpoints.

---

## 2. Product Exposure Decision (Directive §18)

In strict accordance with the freeze principle, the new algorithm will **NOT** immediately overwrite the canonical production default.

### Canonical Usage:
```python
from veyra import Veyra

# Production Default (Deterministic Invariants):
veyra_prod = Veyra(recovery_policy="deterministic")

# Experimental Controller (Opt-In):
veyra_exp = Veyra(recovery_policy="belief_state_experimental")
```

---

## 3. Promotion Gate Checklist (Directive §20)

| Promotion Criterion | Status | Evidence / Observation |
| :--- | :---: | :--- |
| **1. Safe recovery improves over current Veyra** | **MET** | Lifted from $33.3\% \to 83.3\%$ by eliminating unnecessary abstentions. |
| **2. Beats or complements B2 / B6 on mixed faults** | **MET** | Outperforms fixed B6 ($50.0\%$) and B2 ($50.0\%$) across heterogeneous boundaries. |
| **3. Duplicate effects remain at or near zero** | **MET** | Maintained strict $0.0\%$ DER (0 duplicate writes). |
| **4. Does not degrade nominal execution** | **MET** | Nominal execution incurs $0$ false blocks and $<0.25\,\text{ms}$ overhead. |
| **5. Transfer to external real-world benchmarks** | **PENDING** | Requires evaluation on live external MCP servers (MCPMark / MCP-Atlas) before default promotion. |

### Recommendation:
Keep **`belief_state_experimental`** available as an opt-in recovery policy mode. Do not promote to the unconfigured default until external multi-turn MCP transfer traces are recorded.
