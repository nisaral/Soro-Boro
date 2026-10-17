"""Veyra Strategy Lab Plugins."""

from soro.lab.strategies.bm25 import BM25Strategy
from soro.lab.strategies.case_memory import CaseBasedMemoryStrategy
from soro.lab.strategies.dense_embedding import DenseEmbeddingStrategy
from soro.lab.strategies.exact_cache import ExactCacheStrategy
from soro.lab.strategies.process_mined import ProcessMinedStrategy
from soro.lab.strategies.structural import StructuralMatchingStrategy
from soro.lab.strategies.tage import TageHistoryStrategy

__all__ = [
    "ExactCacheStrategy",
    "StructuralMatchingStrategy",
    "BM25Strategy",
    "DenseEmbeddingStrategy",
    "CaseBasedMemoryStrategy",
    "TageHistoryStrategy",
    "ProcessMinedStrategy",
]
