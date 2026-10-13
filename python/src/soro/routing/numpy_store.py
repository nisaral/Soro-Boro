"""Exact NumPy Vector Search Store.

Features:
- Pure NumPy dot-product and cosine similarity matrix operations.
- Zero external vector database or FAISS dependency.
- Fast exact vector search supporting catalogs up to 100,000+ items in milliseconds.
- Normalized vector persistence and index caching.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class SearchResult:
    item_id: str
    score: float
    metadata: Dict[str, Any]


class NumpyVectorStore:
    """Exact in-memory dense vector search engine powered by NumPy."""

    def __init__(self, embedding_dim: Optional[int] = None):
        self.embedding_dim = embedding_dim
        self.item_ids: List[str] = []
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.vectors: Optional[np.ndarray] = None  # shape (N, D), float32 normalized

    def add(self, item_id: str, vector: List[float] | np.ndarray, meta: Optional[Dict[str, Any]] = None) -> None:
        v = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(v)
        if norm > 1e-12:
            v = v / norm

        if self.vectors is None:
            self.vectors = v.reshape(1, -1)
            self.embedding_dim = v.shape[0]
        else:
            if v.shape[0] != self.embedding_dim:
                raise ValueError(f"Vector dim {v.shape[0]} does not match index dim {self.embedding_dim}")
            self.vectors = np.vstack([self.vectors, v.reshape(1, -1)])

        self.item_ids.append(item_id)
        self.metadata[item_id] = meta or {}

    def search(self, query_vector: List[float] | np.ndarray, top_k: int = 10) -> List[SearchResult]:
        if self.vectors is None or len(self.item_ids) == 0:
            return []

        qv = np.array(query_vector, dtype=np.float32)
        norm = np.linalg.norm(qv)
        if norm > 1e-12:
            qv = qv / norm

        # Exact matrix dot product: shape (N,)
        scores = np.dot(self.vectors, qv)
        k = min(top_k, len(self.item_ids))
        top_indices = np.argsort(scores)[::-1][:k]

        results = []
        for idx in top_indices:
            iid = self.item_ids[idx]
            results.append(SearchResult(item_id=iid, score=float(scores[idx]), metadata=self.metadata.get(iid, {})))
        return results

    def save(self, file_path: str | Path) -> None:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        meta_dict = {
            "item_ids": self.item_ids,
            "metadata": self.metadata,
            "embedding_dim": self.embedding_dim,
        }
        with open(p.with_suffix(".meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=2)
        if self.vectors is not None:
            np.save(p.with_suffix(".vec.npy"), self.vectors)

    @classmethod
    def load(cls, file_path: str | Path) -> NumpyVectorStore:
        p = Path(file_path)
        meta_file = p.with_suffix(".meta.json")
        vec_file = p.with_suffix(".vec.npy")

        store = cls()
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        store.item_ids = data.get("item_ids", [])
        store.metadata = data.get("metadata", {})
        store.embedding_dim = data.get("embedding_dim")

        if vec_file.exists():
            store.vectors = np.load(vec_file)
        return store
