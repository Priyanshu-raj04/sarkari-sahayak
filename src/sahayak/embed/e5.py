"""multilingual-e5 embedders. E5 needs "query: " / "passage: " prefixes or recall drops."""

from collections.abc import Sequence
from typing import Protocol

import numpy as np


class Encoder(Protocol):
    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray: ...


class E5Embedder:
    dim = 384

    def __init__(self, model: Encoder, batch_size: int = 32) -> None:
        self.model, self.batch_size = model, batch_size

    @classmethod
    def load(
        cls, name: str = "intfloat/multilingual-e5-small", device: str | None = None
    ) -> "E5Embedder":
        # Optional `[ml]` extra — not installed in default/CI unit environments.
        from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]  # noqa: PLC0415

        # ST.encode typing is wider than our Encoder protocol; runtime contract holds.
        model: Encoder = SentenceTransformer(name, device=device)  # type: ignore[assignment]
        return cls(model)  # device="mps" on the M1

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, query: str) -> np.ndarray:
        return self._encode([f"query: {query}"])[0]

    def _encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)
