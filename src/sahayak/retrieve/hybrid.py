"""Hybrid retrieval: run several retrievers, fuse with RRF, optionally rerank."""

from collections.abc import Sequence
from dataclasses import dataclass

import structlog

from sahayak.retrieve.fusion import reciprocal_rank_fusion
from sahayak.retrieve.types import Passage, PassageStore, Reranker, Retriever

log = structlog.get_logger()


@dataclass(slots=True)
class HybridRetriever:
    retrievers: Sequence[Retriever]
    store: PassageStore
    reranker: Reranker | None = None
    candidates_per_retriever: int = 30
    rrf_k: int = 60

    def search(self, queries: Sequence[str], k: int) -> list[Passage]:
        """`queries` may contain rewrites (e.g. Hindi + English); all rankings are fused."""
        rankings: list[list[str]] = []
        per_retriever: dict[str, dict[str, int]] = {}
        for query in queries:
            for retriever in self.retrievers:
                try:
                    ids = retriever.search(query, self.candidates_per_retriever)
                except Exception:  # one failing retriever must not take the whole search down
                    log.exception("retriever_failed", retriever=retriever.name)
                    continue
                rankings.append(ids)
                for rank, cid in enumerate(ids, start=1):
                    per_retriever.setdefault(cid, {}).setdefault(retriever.name, rank)
        fused = reciprocal_rank_fusion(rankings, k=self.rrf_k)
        pool = fused[: max(k, self.candidates_per_retriever)] if self.reranker else fused[:k]
        found = self.store.get_many([cid for cid, _ in pool])
        passages = [
            found[cid].model_copy(
                update={
                    "score": s,
                    "scores": {f"rank_{n}": float(r) for n, r in per_retriever[cid].items()},
                }
            )
            for cid, s in pool
            if cid in found
        ]
        if self.reranker and passages:
            rerank = self.reranker.score(queries[0], [p.text for p in passages])
            passages = [
                p.model_copy(update={"score": s, "scores": {**p.scores, "rerank": s}})
                for p, s in sorted(zip(passages, rerank, strict=True), key=lambda x: -x[1])
            ]
        return passages[:k]
