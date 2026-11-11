import json
from pathlib import Path

import numpy as np

from evals.benchmarks.memory_dense import InMemoryDense
from evals.benchmarks.results_io import append_result, render_markdown


def test_append_and_render(tmp_path: Path) -> None:
    path = tmp_path / "retrieval.json"
    md = tmp_path / "retrieval.md"
    row = {
        "dataset": "indicqa-hi",
        "split": "test",
        "n_queries": 2,
        "corpus_size": 10,
        "system": "bm25",
        "model": "bm25s",
        "metrics": {"ndcg@10": 0.5, "recall@10": 0.5, "recall@100": 1.0, "mrr@10": 0.5},
        "date": "2026-11-11",
        "git_sha": "abcdef0123456789",
        "seed": 42,
    }
    rows = append_result(path, row)
    assert len(rows) == 1
    assert json.loads(path.read_text(encoding="utf-8"))[0]["system"] == "bm25"
    render_markdown(rows, md)
    text = md.read_text(encoding="utf-8")
    assert "0.5" in text
    assert "abcdef01" in text


def test_in_memory_dense_orders_by_cosine() -> None:
    ids = ["a", "b"]
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

    def embed_query(q: str) -> np.ndarray:
        return np.array([1.0, 0.0], dtype=np.float32)

    dense = InMemoryDense(ids, vectors, embed_query)
    assert dense.search("q", k=2) == ["a", "b"]
