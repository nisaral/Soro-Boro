import os

from soro.routing.catalog import build_unique_catalog, make_queries, oracle_ceiling
from soro.routing.encoders import HashEncoder
from soro.routing.eval_v1 import _bm25_rank, _encoder_rank, _poison, _summarize
from soro.routing.protocol_v1 import POISON_PHRASE, PROTOCOL_ID


def test_protocol_id_frozen():
    assert PROTOCOL_ID == "soro-routing-protocol-v1"


def test_unique_catalog_oracle_is_one():
    specs = build_unique_catalog(16)
    queries = make_queries(specs, __import__("random").Random(0), 0.25)
    ceil = oracle_ceiling(specs, queries)
    assert ceil["oracle_ceiling"] == 1.0
    assert ceil["multi_match"] == 0.0


def test_hash_and_bm25_beat_old_plateau_on_unique_gold():
    specs = build_unique_catalog(24)
    queries = make_queries(specs, __import__("random").Random(7), 0.0)
    h = _summarize(_encoder_rank(HashEncoder(), specs, queries), queries)
    b = _summarize(_bm25_rank(specs, queries), queries)
    assert h["recall@1"] >= 0.8
    assert b["recall@1"] >= 0.8
    assert h["recall@5"] >= 0.95


def test_poison_bm25_is_positive_control():
    os.environ["SORO_SKIP_MINILM"] = "1"
    out = _poison(24, HashEncoder(), None, 7)
    assert out["bm25"]["top1_hijack"] > out["hash_dense"]["top1_hijack"] or out["bm25"]["top1_hijack"] > 0
    assert POISON_PHRASE.split()[0] == "BEST"
    assert out["rug_pull_hash_changed"] is True
