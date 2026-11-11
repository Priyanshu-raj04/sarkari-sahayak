"""In-process BM25 with bm25s — used where ParadeDB isn't available (hosted on Neon)."""

from collections.abc import Sequence

import bm25s

from sahayak.text.normalize import tokenize


class InMemoryBM25:
    name = "bm25"

    def __init__(self, chunk_ids: Sequence[str], texts: Sequence[str]) -> None:
        if len(chunk_ids) != len(texts):
            msg = "chunk_ids and texts must have the same length"
            raise ValueError(msg)
        self._ids = list(chunk_ids)
        self._retriever = bm25s.BM25()
        self._retriever.index([tokenize(t) for t in texts], show_progress=False)

    def search(self, query: str, k: int) -> list[str]:
        tokens = tokenize(query)
        if not tokens or not self._ids:
            return []
        k = min(k, len(self._ids))
        docs, scores = self._retriever.retrieve([tokens], k=k, show_progress=False)
        return [self._ids[int(i)] for i, s in zip(docs[0], scores[0], strict=True) if s > 0]
