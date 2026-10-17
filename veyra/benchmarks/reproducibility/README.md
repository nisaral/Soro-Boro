# Veyra Reproducibility & Independent Audit Protocol

This directory provides the end-to-end audit package to reproduce Veyra's headline evidence from a fresh checkout using a single command.

---

## 1. Quickstart

### Environment Setup
```bash
python3.11 -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\Activate.ps1
pip install -r benchmarks/reproducibility/requirements.txt
```

### Run All Verifications (One Command)
- **PowerShell (Windows):**
  ```powershell
  .\benchmarks\reproducibility\run_all.ps1
  ```
- **Bash (Linux / macOS):**
  ```bash
  bash benchmarks/reproducibility/run_all.sh
  ```

---

## 2. Verification Protocol Summary

1. **Safety Property Invariants (Hypothesis):**  
   Formally tests all 10 core safety properties in `python/tests/test_safety_properties_hypothesis.py` (permission boundaries, side-effects, tenant isolation, freshness limits, unknown-ack transaction safety, determinism).

2. **Frozen Independent Evaluator (`ContinuityBench-v1.0`):**  
   Executes `benchmarks/frozen_eval/run.py`. Recomputes SHA256 of `tasks.json` (`6c130e343f5dc...`), evaluates `raw`, `static`, `fair_static`, and `veyra` read-only without internal benchmark imports.

3. **Adversarial Harder Scorecard (`ContinuityBench 300`):**  
   Evaluates 100 strictly held-out scorecard tasks across 13 mismatch types. Validates the +84.0pp IPR lift over fair static ($p < 0.00001$).

4. **Case Memory Leakage & Invariance Audit:**  
   Verifies zero task ID overlap, zero tag outcome leakage, and robustness against 4 adversarial failure modes.

5. **Blind Independent Scoring Service:**  
   Executes `benchmarks/independent_scorer/scorer.py` over raw event trajectories with anonymous arm IDs, computing exact two-tailed McNemar test statistics and generating `reports/scorecard_audit_report.json`.

---

## 3. Dataset Integrity & Version Hashes

All pinned dataset SHA256 hashes, splits, and quarantine statuses are registered in `benchmarks/reproducibility/benchmark_versions.json`.
The runner aborts immediately if any benchmark file is modified or tampered with.
