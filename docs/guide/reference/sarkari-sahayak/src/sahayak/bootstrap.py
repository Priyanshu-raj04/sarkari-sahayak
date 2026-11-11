"""Composition root: builds the object graph per Profile. The only module that knows adapters."""

from sahayak.api.ratelimit import DailyBudget
from sahayak.config import Profile, Settings
from sahayak.embed.e5 import E5Embedder
from sahayak.llm.gateway import LiteLLMGateway
from sahayak.retrieve.bm25_memory import InMemoryBM25
from sahayak.retrieve.hybrid import HybridRetriever
from sahayak.retrieve.types import Retriever
from sahayak.service import SahayakService
from sahayak.store.migrate import has_extension
from sahayak.store.repo import ParadeBM25Retriever, PgDenseRetriever, PgRepository, connect


def build_service(settings: Settings) -> SahayakService:
    conn = connect(settings.database_url)
    repo = PgRepository(conn)
    embedder = _embedder(settings)
    retrievers: list[Retriever] = [PgDenseRetriever(conn, embedder.embed_query)]
    if settings.profile is Profile.LOCAL and has_extension(conn, "pg_search"):
        retrievers.append(ParadeBM25Retriever(conn))
    else:  # Neon / Codespaces: BM25 in-process (Neon removed pg_search in 2026)
        ids, texts = zip(*repo.iter_chunks(), strict=True) if _has_chunks(repo) else ((), ())
        retrievers.append(InMemoryBM25(list(ids), list(texts)))
    models = [settings.agent_model, *settings.fallback_models]
    return SahayakService(
        retriever=HybridRetriever(retrievers, repo),
        store=repo,
        llm=LiteLLMGateway(models=models),
        budget=DailyBudget(limit=settings.daily_request_budget),
        top_k=settings.top_k,
    )


def _has_chunks(repo: PgRepository) -> bool:
    return repo.conn.execute("SELECT EXISTS (SELECT 1 FROM chunks)").fetchone() == (True,)


def _embedder(settings: Settings) -> E5Embedder:
    # S6 adds: if settings.profile is Profile.HOSTED: return OnnxE5Embedder.load(...)
    return E5Embedder.load(settings.embed_model)
