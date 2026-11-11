from sahayak.embed.fake import FakeEmbedder


def test_fake_embedder_returns_unit_vectors_with_stable_shape() -> None:
    emb = FakeEmbedder()
    empty = emb.embed_passages([])
    assert empty.shape == (0, 384)
    vecs = emb.embed_passages(["केवाईसी", "KYC norms"])
    assert vecs.shape == (2, 384)
    assert abs(float(vecs[0] @ vecs[0]) - 1.0) < 1e-5
    assert (emb.embed_passages(["केवाईसी"]) == vecs[:1]).all()
