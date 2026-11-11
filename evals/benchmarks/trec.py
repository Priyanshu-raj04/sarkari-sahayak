"""Readers for MIRACL-style topics/qrels files and metric computation with ranx."""

from collections.abc import Iterable, Mapping
from pathlib import Path

from ranx import Qrels, Run, evaluate

METRICS = ("ndcg@10", "recall@10", "recall@100", "mrr@10")


def read_topics(path: Path) -> dict[str, str]:
    """`qid<TAB>query` per line (MIRACL topics.*.tsv)."""
    topics: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            qid, query = line.split("\t", maxsplit=1)
            topics[qid] = query
    return topics


def read_qrels(path: Path) -> dict[str, dict[str, int]]:
    """TREC format `qid Q0 docid relevance` (whitespace separated). Keeps zero-relevance rows."""
    qrels: dict[str, dict[str, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        qid, _, docid, rel = line.split()
        qrels.setdefault(qid, {})[docid] = int(rel)
    return qrels


def score_run(
    qrels: Mapping[str, Mapping[str, int]],
    run: Mapping[str, Iterable[str]],
    metrics: tuple[str, ...] = METRICS,
) -> dict[str, float]:
    """`run` maps qid → ranked doc ids (best first); converted to descending pseudo-scores."""
    run_scores = {
        qid: {doc: float(len(ids) - i) for i, doc in enumerate(ids)}
        for qid, ids in ((q, list(d)) for q, d in run.items())
        if ids
    }
    judged = {q: dict(d) for q, d in qrels.items() if any(r > 0 for r in d.values())}
    for qid in judged:
        run_scores.setdefault(qid, {})
    result = evaluate(Qrels(judged), Run(run_scores), list(metrics), make_comparable=True)
    return {m: round(float(v), 4) for m, v in dict(result).items()}  # type: ignore[arg-type]
