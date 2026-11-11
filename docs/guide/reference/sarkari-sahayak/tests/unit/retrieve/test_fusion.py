import pytest
from hypothesis import given
from hypothesis import strategies as st

from sahayak.retrieve.fusion import reciprocal_rank_fusion


def test_doc_found_by_both_retrievers_ranks_first() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["d", "b", "a"]])
    assert fused[0][0] in {"a", "b"}
    assert {d for d, _ in fused[:2]} == {"a", "b"}


def test_score_formula() -> None:
    ((doc, score),) = reciprocal_rank_fusion([["x"]], k=60)
    assert doc == "x"
    assert score == pytest.approx(1 / 61)


def test_ties_are_broken_deterministically_by_id() -> None:
    assert reciprocal_rank_fusion([["b", "a"], ["a", "b"]]) == reciprocal_rank_fusion(
        [["a", "b"], ["b", "a"]]
    )
    assert [d for d, _ in reciprocal_rank_fusion([["b", "a"], ["a", "b"]])] == ["a", "b"]


def test_duplicate_ids_within_one_ranking_count_once() -> None:
    assert reciprocal_rank_fusion([["a", "a"]]) == reciprocal_rank_fusion([["a"]])


def test_limit_and_invalid_k() -> None:
    assert len(reciprocal_rank_fusion([["a", "b", "c"]], limit=2)) == 2
    with pytest.raises(ValueError, match="k must be positive"):
        reciprocal_rank_fusion([["a"]], k=0)


@given(st.lists(st.lists(st.sampled_from("abcdefgh"), max_size=8), max_size=4))
def test_output_is_the_union_of_inputs_sorted_by_score(rankings: list[list[str]]) -> None:
    fused = reciprocal_rank_fusion(rankings)
    assert {d for d, _ in fused} == {d for r in rankings for d in r}
    scores = [s for _, s in fused]
    assert scores == sorted(scores, reverse=True)
