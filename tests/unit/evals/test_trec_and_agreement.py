from pathlib import Path

import pytest

from evals.agreement import cohens_kappa
from evals.benchmarks.trec import read_qrels, read_topics, score_run


def test_reads_topics_and_qrels(tmp_path: Path) -> None:
    (tmp_path / "t.tsv").write_text("1\tकेवाईसी क्या है?\n2\tRBI\n", encoding="utf-8")
    (tmp_path / "q.tsv").write_text("1 Q0 d1#0 1\n1 Q0 d2#0 0\n2 Q0 d3#0 1\n", encoding="utf-8")
    assert read_topics(tmp_path / "t.tsv") == {"1": "केवाईसी क्या है?", "2": "RBI"}
    assert read_qrels(tmp_path / "q.tsv") == {"1": {"d1#0": 1, "d2#0": 0}, "2": {"d3#0": 1}}


def test_perfect_run_scores_one_and_missing_query_scores_zero() -> None:
    qrels = {"1": {"a": 1, "b": 0}, "2": {"c": 1}}
    perfect = score_run(qrels, {"1": ["a", "b"], "2": ["c"]})
    assert perfect["ndcg@10"] == 1.0
    half = score_run(qrels, {"1": ["a"]})  # query 2 returned nothing
    assert half["recall@10"] == 0.5


def test_kappa() -> None:
    assert cohens_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert cohens_kappa([True, True, False, False], [True, False, True, False]) == 0.0
    assert cohens_kappa([True, True], [True, True]) == 1.0
    with pytest.raises(ValueError, match="equal length"):
        cohens_kappa([True], [])
