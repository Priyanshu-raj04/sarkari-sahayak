from sahayak.retrieve.rerank import CrossEncoderReranker


class _FakeCE:
    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        return [0.1 * i for i in range(len(pairs))]


def test_cross_encoder_reranker_scores_in_order() -> None:
    rr = CrossEncoderReranker(model=_FakeCE())
    assert rr.score("q", ["a", "b", "c"]) == [0.0, 0.1, 0.2]
