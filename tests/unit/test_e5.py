import numpy as np

from sahayak.embed.e5 import E5Embedder


class RecordingModel:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray:
        self.seen += sentences
        assert kwargs["normalize_embeddings"] is True
        return np.ones((len(sentences), 384), dtype=np.float64)


def test_prefixes_and_dtype() -> None:
    model = RecordingModel()
    emb = E5Embedder(model)
    assert emb.embed_passages(["क"]).dtype == np.float32
    assert emb.embed_query("ख").shape == (384,)
    assert model.seen == ["passage: क", "query: ख"]
