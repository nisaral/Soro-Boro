# Declared vs Verified: Empirical Evidence on Tool Execution Semantics

---

## 1. The Core Research Question

> **"Can black-box fault injection discover execution-contract violations that declared tool metadata fails to identify, and can verified execution profiles improve safe autonomous recovery?"**

---

## 2. Experimental Results: Declared vs Verified Matrix

We evaluated declared metadata against active fault injection across 5 system architectures:

| System / Operation | Declared Idempotency | Declared Status Probe | Observed Idempotency | Observed Read Consistency | False Assurance Detected? | Verified Autonomy Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **PostgreSQL (`UPDATE`)** | Supported | Supported | **VERIFIED** | STRONG | **NO** | `FULL_AUTONOMOUS` |
| **Git (`git push`)** | Supported | Supported | **VERIFIED** | STRONG | **NO** | `FULL_AUTONOMOUS` |
| **MCP Filesystem (`write_file`)** | Unstated / None | Supported | **UNVERIFIED** | EVENTUAL | **YES [!]** | `PROHIBITED (Blind retry duplicates)` |
| **Payment Gateway (`charge`)** | Supported | Supported | **VERIFIED** | EVENTUAL (Lag) | **YES [!]** | `CONDITIONAL (Key Replay Only)` |
| **Enterprise CRM (`create_ticket`)**| None | Supported | **UNVERIFIED** | EVENTUAL | **YES [!]** | `PROHIBITED (Blind retry duplicates)` |

---

## 3. Findings

1. **Declared Hints Mask Execution Failures:** 3 out of 5 audited tools exhibited **False Assurance**: their declared capabilities or probes encouraged naive retries under network timeouts, but delayed commits and replica lag resulted in duplicate side effects.
2. **The Value of Verified Profiles:** When runtime controllers use the **Verified Execution Profile** rather than declared metadata, duplicate mutations drop to 0 observed duplicates ($UCB_{95\%} = 3.00\%$) because the runtime knows when probes suffer from replica lag and strictly enforces idempotency-only replays or safe abstention.
3. **The Wedge:** Enterprises cannot allow AI agents to invoke tools based solely on documentation or MCP annotations. Veyra provides the active testing engine that verifies these capabilities before deployment.
