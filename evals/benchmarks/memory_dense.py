"""In-memory dense retriever for benches (avoids mixing RBI and MIRACL DBs)."""

from collections.abc import Callable, Sequence

import numpy as np


class InMemoryDense:
    name = "dense"

    def __init__(
        self,
        chunk_ids: Sequence[str],
        vectors: np.ndarray,
        embed_query: Callable[[str], np.ndarray],
    ) -> None:
        if len(chunk_ids) != len(vectors):
            msg = "chunk_ids and vectors must have the same length"
            raise ValueError(msg)
        self._ids = list(chunk_ids)
        # L2-normalised rows → cosine via dot product
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)
        self._vectors = (vectors / norms).astype(np.float32)
        self._embed_query = embed_query

    def search(self, query: str, k: int) -> list[str]:
        if not self._ids:
            return []
        q = self._embed_query(query).astype(np.float32)
        q = q / max(float(np.linalg.norm(q)), 1e-12)
        scores = self._vectors @ q
        k = min(k, len(self._ids))
        if k == len(self._ids):
            idx = np.argsort(-scores)
        else:
            part = np.argpartition(-scores, kth=k - 1)[:k]
            idx = part[np.argsort(-scores[part])]
        return [self._ids[int(i)] for i in idx]
