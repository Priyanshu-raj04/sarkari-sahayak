"""Deterministic 384-d embedder for S1 (real E5 arrives in S2)."""

from collections.abc import Sequence

import numpy as np


class FakeEmbedder:
    """Writes unit-ish vectors so the ingest → pgvector path is exercised without torch."""

    dim: int = 384

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        n = len(texts)
        if n == 0:
            return np.zeros((0, self.dim), dtype=np.float32)
        # Stable per-length pattern so re-ingest is deterministic.
        out = np.zeros((n, self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            out[i, i % self.dim] = 1.0 + (len(text) % 7) * 0.01
            norm = float(np.linalg.norm(out[i]))
            if norm > 0:
                out[i] /= norm
        return out
