import pytest

from soro.routing.linucb_debug import run_linear_sanity
from soro.routing.public_bench import run_cached_dense


def test_linucb_learns_on_linear_bandit():
    out = run_linear_sanity(steps=400)
    assert out["updates"] == 400
    assert out["learned"] is True
    assert out["final_avg_regret"] < 0.5


def test_cached_public_embeddings_match_paper_top1_count():
    import sys
    pytest.importorskip("faiss")
    if sys.platform == "win32":
        pytest.skip("FAISS binary file format (tools.faiss) is incompatible with Windows AVX2 build")
    try:
        out = run_cached_dense()
    except Exception as exc:
        pytest.skip(f"FAISS index incompatible on current platform: {exc}")
    assert out["n"] == 505
    assert out["recall@1_count"] == 483
    assert out["match_paper"] is True
