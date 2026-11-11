from sahayak.retrieve.hybrid import HybridRetriever
from tests.fakes import DictStore, FakeReranker, FakeRetriever, passage

STORE = DictStore({c: passage(c) for c in ["A#p1c0", "B#p1c0", "C#p1c0", "D#p1c0"]})


def test_fuses_bm25_and_dense_and_returns_passages() -> None:
    bm25 = FakeRetriever("bm25", {"q": ["A#p1c0", "B#p1c0"]})
    dense = FakeRetriever("dense", {"q": ["B#p1c0", "C#p1c0"]})
    hits = HybridRetriever([bm25, dense], STORE).search(["q"], k=3)
    assert hits[0].chunk_id == "B#p1c0"  # found by both
    assert hits[0].scores == {"rank_bm25": 2.0, "rank_dense": 1.0}


def test_query_rewrites_are_all_searched_and_fused() -> None:
    bm25 = FakeRetriever("bm25", {"केवाईसी": ["A#p1c0"], "KYC": ["D#p1c0"]})
    hits = HybridRetriever([bm25], STORE).search(["केवाईसी", "KYC"], k=5)
    assert {h.chunk_id for h in hits} == {"A#p1c0", "D#p1c0"}
    assert [q for q, _ in bm25.calls] == ["केवाईसी", "KYC"]


def test_failing_retriever_degrades_gracefully() -> None:
    ok = FakeRetriever("bm25", {"q": ["A#p1c0"]})
    broken = FakeRetriever("dense", {}, fail=True)
    assert [h.chunk_id for h in HybridRetriever([ok, broken], STORE).search(["q"], 3)] == ["A#p1c0"]


def test_reranker_reorders_candidates() -> None:
    bm25 = FakeRetriever("bm25", {"q": ["A#p1c0", "B#p1c0"]})
    rr = FakeReranker({"A#p1c0": 0.1, "B#p1c0": 0.9})
    hits = HybridRetriever([bm25], STORE, reranker=rr).search(["q"], k=2)
    assert [h.chunk_id for h in hits] == ["B#p1c0", "A#p1c0"]
    assert hits[0].scores["rerank"] == 0.9


def test_ids_missing_from_store_are_skipped() -> None:
    bm25 = FakeRetriever("bm25", {"q": ["ghost#p1c0", "A#p1c0"]})
    assert [h.chunk_id for h in HybridRetriever([bm25], STORE).search(["q"], 5)] == ["A#p1c0"]
