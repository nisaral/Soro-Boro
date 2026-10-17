#!/usr/bin/env bash
set -euo pipefail

echo "======================================================="
echo "Veyra Independent Reproducibility & Audit Protocol (POSIX)"
echo "======================================================="

PYTHON=${PYTHON:-python3}

echo -e "\n[1/5] Running Safety Property Tests (Hypothesis)..."
$PYTHON -m pytest python/tests/test_safety_properties_hypothesis.py

echo -e "\n[2/5] Running Independent Frozen Evaluator (ContinuityBench-v1.0)..."
$PYTHON -m benchmarks.frozen_eval.run --system veyra

echo -e "\n[3/5] Evaluating Harder ContinuityBench 300..."
$PYTHON benchmarks/continuitybench/eval_300_scorecard.py

echo -e "\n[4/5] Running Case Memory Leakage & Adversarial Invariance Audit..."
$PYTHON benchmarks/final_evidence/case_memory_leakage_audit.py

echo -e "\n[5/5] Executing Blind Independent Scorer over Raw Trajectories..."
$PYTHON benchmarks/reproducibility/score.py

echo -e "\n>>> ALL VERIFICATION GATES PASSED <<<\n"
