"""MIRACL-hi topics/qrels + 50K-distractor corpus subset builder."""

from __future__ import annotations

import gzip
import json
import random
from pathlib import Path

from huggingface_hub import hf_hub_download

from evals.benchmarks.dataset import BenchDataset
from evals.benchmarks.trec import read_qrels, read_topics

# Exact paths inside https://huggingface.co/datasets/miracl/miracl (checked 2026-11-11).
MIRACL_REPO = "miracl/miracl"
MIRACL_CORPUS_REPO = "miracl/miracl-corpus"
TOPICS_DEV = "miracl-v1.0-hi/topics/topics.miracl-v1.0-hi-dev.tsv"
QRELS_DEV = "miracl-v1.0-hi/qrels/qrels.miracl-v1.0-hi-dev.tsv"
# Corpus shards live under miracl/miracl-corpus (docs-*.jsonl.gz); listed at download time.


def download_miracl_hi_dev_files(cache_dir: Path) -> tuple[Path, Path]:
    """Fetch hi-dev topics + qrels into cache_dir; return (topics, qrels) paths."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    topics = Path(
        hf_hub_download(MIRACL_REPO, TOPICS_DEV, repo_type="dataset", local_dir=cache_dir)
    )
    qrels = Path(hf_hub_download(MIRACL_REPO, QRELS_DEV, repo_type="dataset", local_dir=cache_dir))
    return topics, qrels


def load_miracl_hi_dev_from_dir(root: Path) -> tuple[dict[str, str], dict[str, dict[str, int]]]:
    return read_topics(root / "topics.tsv"), read_qrels(root / "qrels.tsv")


def build_miracl_hi_50k_subset(
    topics: dict[str, str],
    qrels: dict[str, dict[str, int]],
    corpus_jsonl_gz: Path,
    *,
    n_distractors: int = 50_000,
    seed: int = 42,
) -> BenchDataset:
    """All judged hi-dev passages + `n_distractors` random others from a corpus shard."""
    judged = {docid for rels in qrels.values() for docid, rel in rels.items() if rel > 0}
    by_id: dict[str, str] = {}
    others: list[str] = []
    opener = gzip.open if str(corpus_jsonl_gz).endswith(".gz") else open
    with opener(corpus_jsonl_gz, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            docid = str(row["docid"])
            text = f"{row.get('title', '')} {row.get('text', '')}".strip()
            by_id[docid] = text
            if docid not in judged:
                others.append(docid)

    rng = random.Random(seed)  # noqa: S311
    if len(others) > n_distractors:
        others = rng.sample(others, n_distractors)
    keep = judged | set(others)
    corpus = {d: by_id[d] for d in keep if d in by_id}
    return BenchDataset(
        name="miracl-hi-50k",
        split="dev",
        topics=topics,
        qrels=qrels,
        corpus=corpus,
    )


def load_miracl_hi_50k(
    *,
    cache_dir: Path,
    corpus_jsonl_gz: Path | None = None,
    n_distractors: int = 50_000,
    seed: int = 42,
) -> BenchDataset:
    """Download topics/qrels; require a local corpus shard path (too large to auto-pick blindly)."""
    topics_path, qrels_path = download_miracl_hi_dev_files(cache_dir)
    topics, qrels = read_topics(topics_path), read_qrels(qrels_path)
    if corpus_jsonl_gz is None:
        msg = (
            "pass corpus_jsonl_gz= path to a miracl-corpus hi docs-*.jsonl.gz shard "
            f"(repo {MIRACL_CORPUS_REPO}); full 506K overnight embed is out of bench-quick scope"
        )
        raise FileNotFoundError(msg)
    return build_miracl_hi_50k_subset(
        topics, qrels, corpus_jsonl_gz, n_distractors=n_distractors, seed=seed
    )
