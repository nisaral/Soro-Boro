# Single-command full audit and reproduction script (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "======================================================="
Write-Host "Veyra Independent Reproducibility & Audit Protocol"
Write-Host "======================================================="

$Python = "python"
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $Python = "python"
} elseif (Test-Path "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe") {
    $Python = "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe"
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    $Python = "py"
}

# 1. Run all unit and safety property tests
Write-Host "`n[1/5] Running Safety Property Tests (Hypothesis)..."
& $Python -m pytest python/tests/test_safety_properties_hypothesis.py

# 2. Run Frozen Evaluator
Write-Host "`n[2/5] Running Independent Frozen Evaluator (ContinuityBench-v1.0)..."
& $Python -m benchmarks.frozen_eval.run --system veyra

# 3. Run Harder Scorecard 300
Write-Host "`n[3/5] Evaluating Harder ContinuityBench 300..."
& $Python benchmarks/continuitybench/eval_300_scorecard.py

# 4. Run Case Memory Leakage Audit
Write-Host "`n[4/5] Running Case Memory Leakage & Adversarial Invariance Audit..."
& $Python benchmarks/final_evidence/case_memory_leakage_audit.py

# 5. Run Independent Blind Scorer
Write-Host "`n[5/5] Executing Blind Independent Scorer over Raw Trajectories..."
& $Python benchmarks/reproducibility/score.py

Write-Host "`n>>> ALL VERIFICATION GATES PASSED <<<`n"
