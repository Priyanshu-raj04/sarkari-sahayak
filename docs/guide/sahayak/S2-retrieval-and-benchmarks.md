# S2 — Retrieval + Benchmarks: hybrid search you can put numbers on

**Goal:** BM25 + dense (+ optional bge-m3 sparse, + optional reranker) fused with RRF, and a benchmark harness that produces a results table on MIRACL-Hindi, NoMIRACL-Hindi and IndicQA-Hindi.
**Time:** ~12–15 h (plus overnight embedding runs). **Branches:** `feat/s2-embedder`, `feat/s2-fusion`, `feat/s2-hybrid`, `feat/s2-bench-*`.

## Issue text

> **S2: Hybrid retrieval + benchmarks**
> - [ ] `E5Embedder` with correct `query:`/`passage:` prefixes, running on MPS
> - [ ] `reciprocal_rank_fusion` + `HybridRetriever` (multi-query, fail-soft, optional rerank) at ≥ 90 % coverage
> - [ ] `InMemoryBM25` (bm25s) for the hosted profile, using our Devanagari-safe tokenizer
> - [ ] Benchmark runner → `docs/results/retrieval.md` with nDCG@10, Recall@10/100, MRR@10 for BM25 / dense / hybrid / hybrid+rerank on MIRACL-hi dev (n=350) and IndicQA-hi; refusal-relevant stats on NoMIRACL-hi
> - [ ] Every number in the table states n, corpus size, model and date

## Concept primers

> 📘 **BM25** scores a passage by how many query words it contains, weighting rare words more and long passages less. Great for exact terms ("V-CIP", "NBFC-P2P"), useless for synonyms or cross-language.

> 📘 **Dense retrieval** embeds query and passage into vectors; similar meaning → nearby vectors (cosine). `multilingual-e5-small` (384-d, ~118 M params) maps Hindi and English into the *same* space, so a Hindi question can retrieve an English paragraph. E5 models were trained with the prefixes `query: ` and `passage: ` and lose accuracy without them.

> 📘 **Reciprocal Rank Fusion (RRF).** Scores from BM25 and cosine aren't comparable, but *ranks* are. RRF gives each document Σ 1/(k + rank) over the lists it appears in (k = 60 is the standard constant). A document ranked 3rd by both beats one ranked 1st by only one. No tuning, robust, and the default hybrid method in many search engines.

> 📘 **Cross-encoder reranking.** A bi-encoder (e5) embeds query and passage *separately*: fast but shallow. A cross-encoder (`BAAI/bge-reranker-v2-m3`, 568 M params) reads query + passage *together* and outputs a relevance score: slow but sharper. So we rerank only the top ~30 fused candidates.

> 📘 **nDCG@10** rewards putting relevant passages near the top (log-discounted). **Recall@k** asks "is the relevant passage anywhere in the top k?" (what matters for RAG, because the LLM reads the top k). **MRR@10** is 1/rank of the first relevant hit.

> 📘 **bge-m3 sparse ("lexical weights")** is a learned keyword representation: the model assigns weights to tokens, including related words. Obtain it with `BGEM3FlagModel(...).encode(texts, return_dense=True, return_sparse=True)` 📚, store it in pgvector's `sparsevec`. Optional ablation; do it only if time allows (bge-m3 needs ~2+ GB RAM).

## Step 1 — Embedder

`tests/unit/test_e5.py` ✅

```python
import numpy as np

from sahayak.embed.e5 import E5Embedder


class RecordingModel:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray:
        self.seen += sentences
        assert kwargs["normalize_embeddings"] is True
        return np.ones((len(sentences), 384), dtype=np.float64)


def test_prefixes_and_dtype() -> None:
    model = RecordingModel()
    emb = E5Embedder(model)
    assert emb.embed_passages(["क"]).dtype == np.float32
    assert emb.embed_query("ख").shape == (384,)
    assert model.seen == ["passage: क", "query: ख"]
```

`src/sahayak/embed/e5.py` ✅

```python
"""multilingual-e5 embedders. E5 needs "query: " / "passage: " prefixes or recall drops."""

from collections.abc import Sequence
from typing import Protocol

import numpy as np


class Encoder(Protocol):
    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray: ...


class E5Embedder:
    dim = 384

    def __init__(self, model: Encoder, batch_size: int = 32) -> None:
        self.model, self.batch_size = model, batch_size

    @classmethod
    def load(
        cls, name: str = "intfloat/multilingual-e5-small", device: str | None = None
    ) -> "E5Embedder":
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415 - heavy, optional

        return cls(SentenceTransformer(name, device=device))  # device="mps" on the M1

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, query: str) -> np.ndarray:
        return self._encode([f"query: {query}"])[0]

    def _encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)
```

On the M1 use `E5Embedder.load(device="mps")` for ingestion and benchmarks ⚠️ (if a PyTorch op isn't supported on MPS, set `PYTORCH_ENABLE_MPS_FALLBACK=1`). Encoding speed varies; measure on 1,000 passages and extrapolate before starting the full MIRACL job.

## Step 2 — Retrieval core (TDD, ≥ 90 % coverage)

The retrieval ports and the fakes used in every test:

`src/sahayak/retrieve/types.py` ✅

```python
"""Retrieval data types and ports (interfaces)."""

from typing import Protocol

from pydantic import BaseModel, Field


class Passage(BaseModel):
    chunk_id: str
    doc_id: str
    lang: str
    page: int
    text: str
    title: str = ""
    source_url: str = ""
    score: float = 0.0
    scores: dict[str, float] = Field(
        default_factory=dict
    )  # per-retriever ranks/scores for debugging


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int) -> list[str]:
        """Return chunk ids, best first."""
        ...


class PassageStore(Protocol):
    def get_many(self, chunk_ids: list[str]) -> dict[str, Passage]: ...


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...
```

`tests/fakes.py` ✅

```python
"""Hand-written fakes for our own ports (prefer these over mocks)."""

from dataclasses import dataclass, field

from pydantic import BaseModel

from sahayak.retrieve.types import Passage


@dataclass
class FakeRetriever:
    name: str
    results: dict[str, list[str]]
    calls: list[tuple[str, int]] = field(default_factory=list)
    fail: bool = False

    def search(self, query: str, k: int) -> list[str]:
        self.calls.append((query, k))
        if self.fail:
            raise RuntimeError(f"{self.name} down")
        return self.results.get(query, [])[:k]


@dataclass
class DictStore:
    passages: dict[str, Passage]

    def get_many(self, chunk_ids: list[str]) -> dict[str, Passage]:
        return {c: self.passages[c] for c in chunk_ids if c in self.passages}


@dataclass
class FakeReranker:
    scores: dict[str, float]

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [self.scores.get(t, 0.0) for t in texts]


def passage(cid: str, text: str = "", lang: str = "hi") -> Passage:
    doc_id = cid.split("#", maxsplit=1)[0]
    return Passage(chunk_id=cid, doc_id=doc_id, lang=lang, page=1, text=text or cid)


class FakeLLM:
    """Returns scripted outputs per schema type, in order; records every call."""

    def __init__(self, script: dict[type[BaseModel], list[BaseModel | Exception]]) -> None:
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[tuple[str, str, type[BaseModel]]] = []

    def complete_json[T: BaseModel](
        self, *, system: str, user: str, schema: type[T], temperature: float = 0.0
    ) -> T:
        self.calls.append((system, user, schema))
        queue = self.script.get(schema, [])
        if not queue:
            raise AssertionError(f"FakeLLM: no scripted output left for {schema.__name__}")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if not isinstance(item, schema):
            raise TypeError(f"FakeLLM: scripted {type(item).__name__}, expected {schema.__name__}")
        return item
```

(`FakeLLM` at the bottom of `fakes.py` is used from S3 on.)

`tests/unit/retrieve/test_fusion.py` ✅

```python
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
```

> ✋ **Try it yourself first.** You have the failing tests above. Spend 30–45 minutes making them pass on your own before reading the reference implementation below. Then compare: what did you do differently, and why?

`src/sahayak/retrieve/fusion.py` ✅

```python
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
```

`tests/unit/retrieve/test_hybrid.py` ✅

```python
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
```

> ✋ **Try it yourself first.** You have the failing tests above. Spend 30–45 minutes making them pass on your own before reading the reference implementation below. Then compare: what did you do differently, and why?

`src/sahayak/retrieve/hybrid.py` ✅

```python
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


def _ranks(ranks: dict[str, int]) -> dict[str, float]:
    return {f"rank_{name}": float(rank) for name, rank in ranks.items()}
```

`tests/unit/retrieve/test_bm25_memory.py` ✅

```python
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
```

`src/sahayak/retrieve/bm25_memory.py` ✅

```python
"""In-process BM25 with bm25s — used where ParadeDB isn't available (hosted on Neon)."""

from collections.abc import Sequence

import bm25s

from sahayak.text.normalize import tokenize


class InMemoryBM25:
    name = "bm25"

    def __init__(self, chunk_ids: Sequence[str], texts: Sequence[str]) -> None:
        if len(chunk_ids) != len(texts):
            msg = "chunk_ids and texts must have the same length"
            raise ValueError(msg)
        self._ids = list(chunk_ids)
        self._retriever = bm25s.BM25()
        self._retriever.index([tokenize(t) for t in texts], show_progress=False)

    def search(self, query: str, k: int) -> list[str]:
        tokens = tokenize(query)
        if not tokens or not self._ids:
            return []
        k = min(k, len(self._ids))
        docs, scores = self._retriever.retrieve([tokens], k=k, show_progress=False)
        return [self._ids[int(i)] for i, s in zip(docs[0], scores[0], strict=True) if s > 0]
```

Verified: bm25s 0.3.16 with our tokenizer retrieves the Hindi chunk for a Hindi query and drops zero-score documents ✅.

### Reranker adapter (local only)

```python
# src/sahayak/retrieve/rerank.py
"""Cross-encoder reranker (local/benchmarks). Not used on Render (too big for 512 MB)."""

from sentence_transformers import CrossEncoder


class CrossEncoderReranker:
    def __init__(self, name: str = "BAAI/bge-reranker-v2-m3", device: str | None = None,
                 max_length: int = 512) -> None:
        self.model = CrossEncoder(name, device=device, max_length=max_length)

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self.model.predict([(query, t) for t in texts])]
```

⚠️ Not run in the sandbox (needs a ~2.3 GB download). Test it with an `@pytest.mark.slow` integration test that reranks 3 hand-made pairs and asserts the obviously relevant one wins. If RAM is tight, an int8 ONNX variant `BAAI/bge-reranker-v2-m3-int8` is listed by fastembed 0.9.1 (`fastembed.rerank.cross_encoder.TextCrossEncoder`) ✅ (listing verified, quality not).

## Step 3 — Benchmark data (local only, never committed)

| Dataset | What we use | Notes |
|---|---|---|
| **MIRACL** `miracl/miracl` (topics, qrels) + `miracl/miracl-corpus` (passages) | Hindi **dev**: 350 queries, 3,494 judgments; corpus 506,264 passages in 2 `docs-*.jsonl.gz` shards 📚 | Topics file: `qid<TAB>query`; qrels TREC format `qid Q0 docid rel`. Passages: `{"docid","title","text"}`. ⚠️ exact file paths inside the HF repos: list them with `hf` / the web UI before coding the loader; record them in `docs/data-sources.md`. |
| **NoMIRACL** `miracl/nomiracl` | Hindi, `relevant` and `non_relevant` subsets 📚 | Non-relevant queries have **no** correct passage in their candidate set: the right behaviour is to refuse. Used in S3/S5 for refusal rate. ⚠️ check split names. |
| **IndicQARetrieval** `mteb/IndicQARetrieval` | `hi` (and `mr` in S7) corpus/queries/qrels, CC0-1.0 📚 | Small, fast; good for quick iteration. |

The 506 K-passage MIRACL-hi corpus is the expensive part: embedding it with e5-small on the M1 is an overnight job, and bge-m3 will take several times longer ⚠️ measure first. **Practical plan:**
1. Iterate on **IndicQA-hi** (small) and a **MIRACL-hi subset**: all passages judged for the dev queries + 50,000 random others (state this clearly as "MIRACL-hi dev, 50K-distractor subset").
2. Run the full 506K corpus once, overnight, for the final e5 numbers.

Store benchmark corpora in a **separate database** (`createdb miracl`) or a separate schema, never mixed with the RBI corpus.

## Step 4 — Benchmark harness

`tests/unit/evals/test_trec_and_agreement.py` ✅

```python
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
```

`evals/benchmarks/trec.py` ✅

```python
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
```

Runner skeleton (`evals/benchmarks/run_retrieval.py`; write it yourself, it's glue):

```python
"""uv run python -m evals.benchmarks.run_retrieval --dataset miracl-hi --systems bm25,dense,hybrid"""
# 1. load topics + qrels (read_topics / read_qrels)
# 2. for each system: run = {qid: retriever.search(query, k=100) for qid, query in topics.items()}
# 3. metrics = score_run(qrels, run)
# 4. append a row to docs/results/retrieval.json:
#    {dataset, split, n_queries, corpus_size, system, model, metrics, date, git_sha, seed}
# 5. render docs/results/retrieval.md from the JSON (never hand-edit numbers)
```

Use `PgDenseRetriever(exact=True)` for the headline numbers, then the same with `exact=False` and report **ANN recall** = overlap of the HNSW top-10 with the exact top-10.

Results table template (`docs/results/retrieval.md`):

| Dataset (split, n) | Corpus | System | nDCG@10 | R@10 | R@100 | MRR@10 |
|---|---|---|---|---|---|---|
| MIRACL-hi (dev, 350) | 50K subset | BM25 (ParadeDB ICU) | – | – | – | – |
| | | dense e5-small | – | – | – | – |
| | | hybrid RRF | – | – | – | – |
| | | hybrid + bge-reranker-v2-m3 | – | – | – | – |
| | | hosted config (bm25s + e5-ONNX) | – | – | – | – |
| IndicQA-hi | full | … | | | | |

Fill only with numbers you measured. MIRACL's own paper reports Hindi baselines you can cite as a sanity check ⚠️ (look them up; don't quote from memory).

## Definition of Done

- [ ] Coverage ≥ 90 % on `retrieve/`
- [ ] `docs/results/retrieval.md` generated from JSON, with n / corpus / model / date / git sha
- [ ] ADR-0004 "e5-small as main embedder" citing your own measured speed + quality vs bge-m3
- [ ] `make bench-quick` (IndicQA-hi, ~minutes) documented in the README

## Cursor prompt (S2)

> Read `docs/guide/sahayak/S2-retrieval-and-benchmarks.md`. Implement Step 2: create the test files exactly as given, run them red, then implement `fusion.py`, `hybrid.py`, `bm25_memory.py` to green. Keep `HybridRetriever` free of any database or model imports — it must only depend on the protocols in `retrieve/types.py`.
