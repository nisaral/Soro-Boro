# Execution Contract Conformance: Black-Box Verification of Agent-Callable Tools

**Status:** Technical Architecture & Methodology Specification  
**Product Wedge:** Verified Execution Semantics for AI Tools  
**Primary Metric:** False Assurance Rate (FAR) & Contract Conformance Rate (CCR)

---

## 1. Executive Summary

Enterprise agent adoption faces a critical trust barrier: tools declare capabilities (e.g. `idempotent: true`, MCP `idempotentHint`, OpenAPI schemas), but runtime failures (lost ACKs, timeouts, stale replicas, late commits) trigger catastrophic duplicate operations.

Veyra solves this problem by functioning as a **black-box execution conformance engine**:
1. It ingests tool manifests, MCP annotations, or API endpoints.
2. It actively injects 12 realistic fault models at the execution boundary.
3. It measures actual side effects against an independent state ledger.
4. It outputs an immutable, machine-readable **Verified Execution Profile (VEP)**.
5. Downstream runtime layers enforce execution policies based on verified semantics rather than developer declarations.

---

## 2. Core Methodology: The Five Capability Dimensions

For every tool under test $T$, Veyra audits the capability set $C = \{ I, V, R, C, B \}$:

1. **Idempotency ($I$):** Does the tool enforce strict exactly-once deduplication across retried requests with client keys?
2. **Verification ($V$):** Does a reliable, queryable status probe exist, and what is its observed read consistency (Strong vs Eventual vs None)?
3. **Reconciliation ($R$):** Can batch operations or partial writes be audited and reconciled post-failure?
4. **Compensation ($C$):** Does a deterministic reverse action (e.g. refund, delete, revert) exist?
5. **Execution Bounds ($B$):** Is the maximum in-flight duration bounded and observable?

---

## 3. The Conformance Test Loop

```text
Tool Target (Manifest / Process / Endpoint)
                    │
                    ▼
┌──────────────────────────────────────┐
│       Veyra Conformance Engine       │
│  Phase 1: Ingest Declared Contracts  │
│  Phase 2: Generate Fault Matrix      │
│  Phase 3: Dispatch & Fault Injection │
│  Phase 4: Audit Oracle State Ledger  │
│  Phase 5: Compute Finite-Sample UCB  │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│      Verified Execution Profile      │
│  - Idempotency: VERIFIED / CONTRADICTED
│  - False Assurance: DETECTED / NONE  │
│  - Recommendation: AUTONOMOUS / DENY │
└──────────────────────────────────────┘
```

---

## 4. Key Metrics

- **False Assurance Rate (FAR):** The proportion of tools declared safe or idempotent that violate their contract under active fault injection.
- **Contract Conformance Rate (CCR):** The proportion of declared guarantees empirically verified across all 12 fault families.
- **Duplicate Effect Rate (DER):** Finite-sample observed rate of duplicate writes, reported with one-sided 95% upper confidence bounds:
  $$\text{DER}_{95\% \text{ UCB}} = \hat{p} + 1.645 \sqrt{\frac{\hat{p}(1 - \hat{p})}{N}} \quad (\text{or } \frac{2.9957}{N} \text{ if } \hat{p}=0)$$
