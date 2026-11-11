"""CLI: `python -m evals.benchmarks.run_retrieval --dataset indicqa-hi`."""

from __future__ import annotations

import argparse
import platform
import subprocess
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import numpy as np
import structlog

from evals.benchmarks.dataset import BenchDataset
from evals.benchmarks.indicqa import load_indicqa_hi, load_indicqa_hi_from_dir
from evals.benchmarks.memory_dense import InMemoryDense
from evals.benchmarks.results_io import append_result, render_markdown
from evals.benchmarks.trec import score_run
from sahayak.retrieve.bm25_memory import InMemoryBM25
from sahayak.retrieve.hybrid import HybridRetriever
from sahayak.retrieve.types import Passage

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON = ROOT / "docs" / "results" / "retrieval.json"
DEFAULT_MD = ROOT / "docs" / "results" / "retrieval.md"


def _git_sha() -> str:
    try:
        cmd = ["git", "rev-parse", "HEAD"]
        return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()  # noqa: S603
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _prefer_device() -> str | None:
    if platform.system() == "Darwin":
        try:
            import torch  # type: ignore[import-not-found]  # noqa: PLC0415

            if torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            return None
    return None


class _DictStore:
    def __init__(self, corpus: dict[str, str]) -> None:
        self._passages = {
            cid: Passage(chunk_id=cid, doc_id=cid, lang="hi", page=1, text=text)
            for cid, text in corpus.items()
        }

    def get_many(self, chunk_ids: list[str]) -> dict[str, Passage]:
        return {c: self._passages[c] for c in chunk_ids if c in self._passages}


def _load_dataset(name: str, fixture_dir: Path | None, cache_dir: Path) -> BenchDataset:
    if name == "indicqa-hi":
        if fixture_dir is not None:
            return load_indicqa_hi_from_dir(fixture_dir)
        return load_indicqa_hi(cache_dir=cache_dir)
    if name == "miracl-hi-50k":
        from evals.benchmarks.miracl import load_miracl_hi_50k  # noqa: PLC0415

        corpus = cache_dir / "corpus.jsonl.gz"
        shard = corpus if corpus.exists() else None
        return load_miracl_hi_50k(cache_dir=cache_dir, corpus_jsonl_gz=shard)
    msg = f"unknown dataset: {name}"
    raise ValueError(msg)


def _build_embedder(model_name: str):
    from sahayak.config import get_settings  # noqa: PLC0415
    from sahayak.embed.e5 import E5Embedder  # noqa: PLC0415

    settings = get_settings()
    name = model_name or settings.embed_model
    return E5Embedder.load(name, device=_prefer_device()), name


def _embed_corpus(embedder, texts: Sequence[str], batch: int = 32) -> np.ndarray:
    parts: list[np.ndarray] = []
    for i in range(0, len(texts), batch):
        parts.append(embedder.embed_passages(texts[i : i + batch]))
    return np.vstack(parts) if parts else np.zeros((0, 384), dtype=np.float32)


def _run_system(
    system: str,
    ds: BenchDataset,
    *,
    bm25: InMemoryBM25,
    dense: InMemoryDense,
    store: _DictStore,
    k: int,
) -> dict[str, list[str]]:
    run: dict[str, list[str]] = {}
    for qid, query in ds.topics.items():
        if system == "bm25":
            run[qid] = bm25.search(query, k)
        elif system == "dense":
            run[qid] = dense.search(query, k)
        elif system == "hybrid":
            hits = HybridRetriever([bm25, dense], store).search([query], k=k)
            run[qid] = [h.chunk_id for h in hits]
        else:
            msg = f"unknown system: {system}"
            raise ValueError(msg)
    return run


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default="indicqa-hi", choices=["indicqa-hi", "miracl-hi-50k"])
    p.add_argument("--systems", default="bm25,dense,hybrid")
    p.add_argument("--fixture-dir", type=Path, default=None, help="offline IndicQA-style dir")
    p.add_argument("--cache-dir", type=Path, default=ROOT / "data" / "bench")
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    p.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    p.add_argument("--k", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--model", default="")
    args = p.parse_args(list(argv) if argv is not None else None)

    ds = _load_dataset(args.dataset, args.fixture_dir, args.cache_dir)
    ids = list(ds.corpus.keys())
    texts = [ds.corpus[i] for i in ids]
    bm25 = InMemoryBM25(ids, texts)
    embedder, model_name = _build_embedder(args.model)
    vectors = _embed_corpus(embedder, texts)
    dense = InMemoryDense(ids, vectors, embedder.embed_query)
    store = _DictStore(ds.corpus)

    rows = []
    for system in [s.strip() for s in args.systems.split(",") if s.strip()]:
        log.info("bench_system_start", system=system, n_queries=ds.n_queries)
        run = _run_system(system, ds, bm25=bm25, dense=dense, store=store, k=args.k)
        metrics = score_run(ds.qrels, run)
        row = {
            "dataset": ds.name,
            "split": ds.split,
            "n_queries": ds.n_queries,
            "corpus_size": ds.corpus_size,
            "system": system,
            "model": model_name if system != "bm25" else "bm25s+regex-tokenize",
            "metrics": metrics,
            "date": date.today().isoformat(),
            "git_sha": _git_sha(),
            "seed": args.seed,
        }
        rows = append_result(args.json_out, row)
        log.info("bench_system_done", system=system, **metrics)

    render_markdown(rows, args.md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
