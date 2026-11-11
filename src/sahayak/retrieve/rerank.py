"""Cross-encoder reranker (local/benchmarks). Not used on Render (too big for 512 MB)."""

from typing import Protocol


class _PredictingEncoder(Protocol):
    def predict(self, pairs: list[tuple[str, str]]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(
        self,
        name: str = "BAAI/bge-reranker-v2-m3",
        device: str | None = None,
        max_length: int = 512,
        model: _PredictingEncoder | None = None,
    ) -> None:
        if model is None:
            from sentence_transformers import (  # type: ignore[import-not-found]  # noqa: PLC0415
                CrossEncoder,
            )

            # CrossEncoder.predict typing is wider than our protocol; runtime OK.
            loaded = CrossEncoder(name, device=device, max_length=max_length)
            self.model: _PredictingEncoder = loaded  # type: ignore[assignment]
        else:
            self.model = model

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self.model.predict([(query, t) for t in texts])]
