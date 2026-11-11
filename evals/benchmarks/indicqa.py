"""Load IndicQA-hi (mteb/IndicQARetrieval) for bench-quick."""

from pathlib import Path
from typing import Any, cast

from evals.benchmarks.dataset import BenchDataset
from evals.benchmarks.trec import read_qrels, read_topics


def load_indicqa_hi_from_dir(root: Path) -> BenchDataset:
    """Offline fixture layout: topics.tsv, qrels.tsv, corpus.tsv (docid\\ttext)."""
    corpus: dict[str, str] = {}
    for line in (root / "corpus.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        docid, text = line.split("\t", maxsplit=1)
        corpus[docid] = text
    return BenchDataset(
        name="indicqa-hi",
        split="test",
        topics=read_topics(root / "topics.tsv"),
        qrels=read_qrels(root / "qrels.tsv"),
        corpus=corpus,
    )


def _row(item: Any) -> dict[str, Any]:
    return cast(dict[str, Any], dict(item))


def load_indicqa_hi(*, cache_dir: Path | None = None) -> BenchDataset:
    """Download `mteb/IndicQARetrieval` hi-* configs via Hugging Face `datasets`."""
    from datasets import load_dataset  # noqa: PLC0415

    cache: str | None = None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache = str(cache_dir)

    corpus_ds = load_dataset("mteb/IndicQARetrieval", "hi-corpus", split="test", cache_dir=cache)
    queries_ds = load_dataset("mteb/IndicQARetrieval", "hi-queries", split="test", cache_dir=cache)
    qrels_ds = load_dataset("mteb/IndicQARetrieval", "hi-qrels", split="test", cache_dir=cache)

    corpus: dict[str, str] = {}
    for item in corpus_ds:
        row = _row(item)
        docid = str(row.get("_id") or row.get("id"))
        title = str(row.get("title") or "")
        text = str(row.get("text") or "")
        corpus[docid] = f"{title} {text}".strip() if title else text

    topics: dict[str, str] = {}
    for item in queries_ds:
        row = _row(item)
        qid = str(row.get("_id") or row.get("id"))
        topics[qid] = str(row.get("text") or "")

    qrels: dict[str, dict[str, int]] = {}
    for item in qrels_ds:
        row = _row(item)
        qid = str(row.get("query-id") or row.get("query_id"))
        docid = str(row.get("corpus-id") or row.get("corpus_id"))
        score = int(row.get("score", 1))
        qrels.setdefault(qid, {})[docid] = score

    return BenchDataset(name="indicqa-hi", split="test", topics=topics, qrels=qrels, corpus=corpus)
