"""Torch-free e5 embedder for the 512 MB hosted profile: tokenizers + onnxruntime + mean pooling."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np


class _Session(Protocol):  # the subset of onnxruntime.InferenceSession we use
    def run(self, output_names: Any, input_feed: Any, /) -> Any: ...
    def get_inputs(self) -> Any: ...


class OnnxE5Embedder:
    dim = 384

    def __init__(self, tokenizer: Any, session: _Session, max_length: int = 512) -> None:
        self.tokenizer, self.session = tokenizer, session
        self.tokenizer.enable_truncation(max_length=max_length)
        self.tokenizer.enable_padding()
        self._input_names = {i.name for i in session.get_inputs()}

    @classmethod
    def load(cls, model_dir: str | Path, threads: int = 1) -> "OnnxE5Embedder":
        import onnxruntime as ort  # noqa: PLC0415 - optional (extra "onnx")
        from tokenizers import Tokenizer  # noqa: PLC0415

        d = Path(model_dir)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads  # Render free = 0.1 CPU; more threads only thrash
        session = ort.InferenceSession(
            str(d / "model.onnx"), opts, providers=["CPUExecutionProvider"]
        )
        return cls(Tokenizer.from_file(str(d / "tokenizer.json")), session)

    def embed_query(self, query: str) -> np.ndarray:
        return self._encode([f"query: {query}"])[0]

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([f"passage: {t}" for t in texts])

    def _encode(self, texts: list[str]) -> np.ndarray:
        enc = self.tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = np.asarray(self.session.run(None, feed)[0])  # (batch, seq, dim) last_hidden_state
        summed = (hidden * mask[..., None]).sum(axis=1)
        pooled = summed / np.clip(mask.sum(axis=1, keepdims=True), 1, None)  # mean pooling (e5)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return (pooled / np.clip(norms, 1e-12, None)).astype(np.float32)
