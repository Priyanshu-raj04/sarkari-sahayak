import gzip
import json
from pathlib import Path

from evals.benchmarks.indicqa import load_indicqa_hi_from_dir
from evals.benchmarks.miracl import build_miracl_hi_50k_subset
from evals.benchmarks.nomiracl import load_nomiracl_hi_from_dir


def _write_triplet(root: Path) -> None:
    (root / "topics.tsv").write_text("1\tकेवाईसी क्या है?\n", encoding="utf-8")
    (root / "qrels.tsv").write_text("1 Q0 d1 1\n", encoding="utf-8")
    (root / "corpus.tsv").write_text("d1\tकेवाईसी नियम\nd2\tअन्य पाठ\n", encoding="utf-8")


def test_indicqa_loader_from_dir(tmp_path: Path) -> None:
    _write_triplet(tmp_path)
    ds = load_indicqa_hi_from_dir(tmp_path)
    assert ds.name == "indicqa-hi"
    assert ds.topics == {"1": "केवाईसी क्या है?"}
    assert ds.qrels["1"]["d1"] == 1
    assert ds.corpus_size == 2


def test_nomiracl_loader_from_dir(tmp_path: Path) -> None:
    rel = tmp_path / "non_relevant"
    rel.mkdir()
    _write_triplet(rel)
    ds = load_nomiracl_hi_from_dir(tmp_path, split="non_relevant")
    assert ds.name == "nomiracl-hi-non_relevant"
    assert ds.n_queries == 1


def test_miracl_50k_subset_keeps_judged_and_samples_distractors(tmp_path: Path) -> None:
    topics = {"q1": "query"}
    qrels = {"q1": {"judged1": 1, "judged0": 0}}
    shard = tmp_path / "docs.jsonl.gz"
    rows = [
        {"docid": "judged1", "title": "t", "text": "relevant"},
        {"docid": "judged0", "title": "", "text": "zero"},
        *[{"docid": f"x{i}", "title": "", "text": f"other {i}"} for i in range(20)],
    ]
    with gzip.open(shard, "wt", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    ds = build_miracl_hi_50k_subset(topics, qrels, shard, n_distractors=5, seed=0)
    assert "judged1" in ds.corpus
    assert ds.corpus_size == 1 + 5  # judged>0 + 5 distractors
