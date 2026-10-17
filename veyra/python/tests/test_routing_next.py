from soro.routing.expand import expand_document, synthetic_examples
from soro.routing.fold_calib import five_fold_margin
from soro.routing.scale import ToolSpec


def test_synthetic_examples_are_not_copied_from_arg():
    s = ToolSpec(name="weather_tool", description="Queries a weather service for a city.")
    ex = synthetic_examples(s)
    assert any("weather" in e.lower() or "queries" in e.lower() for e in ex)
    doc = expand_document(s)
    assert "Tokens:" in doc
    assert "Typical requests:" in doc


def test_five_fold_margin_runs():
    margins = [0.2] * 10 + [0.01] * 10
    correct = [True] * 10 + [False] * 10
    out = five_fold_margin(margins, correct, 0.9)
    assert out["n_test_pooled"] == 20
    assert 0.0 <= out["pooled_coverage"] <= 1.0
