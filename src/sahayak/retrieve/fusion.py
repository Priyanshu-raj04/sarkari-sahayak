"""Reciprocal Rank Fusion (Cormack et al., 2009)."""

from collections.abc import Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, k: int = 60, limit: int | None = None
) -> list[tuple[str, float]]:
    """Fuse ranked id lists: score(d) = sum over lists of 1 / (k + rank(d)), rank starting at 1.

    Ties are broken by id so results are deterministic.
    """
    if k <= 0:
        msg = "k must be positive"
        raise ValueError(msg)
    scores: dict[str, float] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, doc_id in enumerate(ranking, start=1):
            if doc_id in seen:  # a retriever listing a doc twice must not double-count
                continue
            seen.add(doc_id)
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    fused = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return fused[:limit] if limit is not None else fused
