"""Pluggable encoders. Hash is lexical baseline. MiniLM is the neural dense arm."""

from __future__ import annotations

from typing import Protocol

from soro.routing.scale import cosine_similarity, text_to_vector


class Encoder(Protocol):
    name: str

    def encode(self, texts: list[str]) -> list[list[float]]: ...


class HashEncoder:
    name = "hash_dense"

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [text_to_vector(t) for t in texts]


class MiniLMEncoder:
    name = "minilm"

    def __init__(self, model_id: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_id)

    def encode(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vecs]


def rank_by_encoder(query: str, docs: dict[str, str], encoder: Encoder, top_k: int = 10) -> list[tuple[str, float]]:
    names = list(docs)
    qv = encoder.encode([query])[0]
    dv = encoder.encode([docs[n] for n in names])
    scored = [(n, cosine_similarity(qv, d)) for n, d in zip(names, dv)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def try_minilm() -> MiniLMEncoder | None:
    try:
        return MiniLMEncoder()
    except Exception:
        return None
