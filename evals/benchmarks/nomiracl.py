"""NoMIRACL-hi loader (relevant / non_relevant) for S3 refusal stats — fixture-friendly."""

from pathlib import Path

from evals.benchmarks.dataset import BenchDataset
from evals.benchmarks.trec import read_qrels, read_topics

# HF: https://huggingface.co/datasets/miracl/nomiracl — verify split names before live use.
NOMIRACL_REPO = "miracl/nomiracl"


def load_nomiracl_hi_from_dir(root: Path, *, split: str) -> BenchDataset:
    """Offline layout: topics.tsv, qrels.tsv, corpus.tsv under `root / split`."""
    base = root / split
    corpus: dict[str, str] = {}
    for line in (base / "corpus.tsv").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        docid, text = line.split("\t", maxsplit=1)
        corpus[docid] = text
    return BenchDataset(
        name=f"nomiracl-hi-{split}",
        split=split,
        topics=read_topics(base / "topics.tsv"),
        qrels=read_qrels(base / "qrels.tsv"),
        corpus=corpus,
    )
