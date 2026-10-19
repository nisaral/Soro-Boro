---
title: Soro-Kev Tool Router
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 6.30.0
app_file: app.py
pinned: false
license: apache-2.0
---

# Soro-Kev: Calibration-Aware System-One Tool Router Demo

This Hugging Face Space demonstrates prefill-only tool routing over a catalog of 114 tools spanning MCP, REST APIs, Developer Toolchains, Cloud Infrastructure, and Business Systems. The demo uses the current production path: a lexical shortlist, the neural pointer scorer, and a top-mass abstention gate. The checkpoints also contain split-conformal calibration artifacts, but `SoroHarness.route()` does not yet apply `q_hat`; do not read the demo as a finite-sample coverage guarantee.

- **Model Weights**: [nisaralll/soro-kev-4b](https://huggingface.co/nisaralll/soro-kev-4b) and [nisaralll/soro-kev-0.8b](https://huggingface.co/nisaralll/soro-kev-0.8b)
- **Dataset**: [nisaralll/soro-universal-tool-harness](https://huggingface.co/datasets/nisaralll/soro-universal-tool-harness)
- **GitHub**: [nisaral/Soro-Boro](https://github.com/nisaral/Soro-Boro)
