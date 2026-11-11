import pytest

from sahayak.retrieve.bm25_memory import InMemoryBM25

IDS = ["kyc#p1c0", "kyc-en#p1c0", "rate#p1c0"]
TEXTS = [
    "केवाईसी नियमों का पालन सभी बैंकों के लिए अनिवार्य है।",
    "KYC norms apply to all regulated entities.",
    "ब्याज दर पर निर्देश।",
]


@pytest.fixture(scope="module")
def bm25() -> InMemoryBM25:
    return InMemoryBM25(IDS, TEXTS)


def test_hindi_query_finds_hindi_chunk(bm25: InMemoryBM25) -> None:
    assert bm25.search("केवाईसी नियमों", k=2)[0] == "kyc#p1c0"


def test_english_query_finds_english_chunk(bm25: InMemoryBM25) -> None:
    assert bm25.search("kyc norms", k=1) == ["kyc-en#p1c0"]


def test_zero_score_docs_are_not_returned(bm25: InMemoryBM25) -> None:
    assert bm25.search("मौसम", k=3) == []


def test_empty_query_and_mismatched_input() -> None:
    assert InMemoryBM25(IDS, TEXTS).search("   ", 3) == []
    with pytest.raises(ValueError, match="same length"):
        InMemoryBM25(["a"], [])
