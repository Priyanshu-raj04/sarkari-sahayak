from types import SimpleNamespace
from typing import Any

import numpy as np

from sahayak.embed.onnx_e5 import OnnxE5Embedder


class FakeTokenizer:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def enable_truncation(self, max_length: int) -> None: ...
    def enable_padding(self) -> None: ...

    def encode_batch(self, texts: list[str]) -> list[SimpleNamespace]:
        self.texts += texts
        return [SimpleNamespace(ids=[1, 2, 0], attention_mask=[1, 1, 0]) for _ in texts]


class FakeSession:
    def get_inputs(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=n) for n in ("input_ids", "attention_mask", "token_type_ids")]

    def run(self, output_names: Any, feed: dict[str, np.ndarray], /) -> list[np.ndarray]:
        assert set(feed) == {"input_ids", "attention_mask", "token_type_ids"}
        batch = feed["input_ids"].shape[0]
        hidden = np.zeros((batch, 3, 384), dtype=np.float32)
        hidden[:, 0, 0] = 3.0  # token 1
        hidden[:, 1, 1] = 4.0  # token 2
        hidden[:, 2, 2] = 100.0  # padding — must be ignored by mean pooling
        return [hidden]


def test_mean_pooling_ignores_padding_and_normalises() -> None:
    tok = FakeTokenizer()
    emb = OnnxE5Embedder(tok, FakeSession())
    vec = emb.embed_query("केवाईसी")
    assert np.allclose(vec[:3], [0.6, 0.8, 0.0])  # (3,4)/2 normalised; padding ignored
    assert vec.dtype == np.float32
    assert emb.embed_passages(["a", "b"]).shape == (2, 384)
    assert tok.texts == ["query: केवाईसी", "passage: a", "passage: b"]
