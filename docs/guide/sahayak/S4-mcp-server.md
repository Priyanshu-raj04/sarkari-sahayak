# S4 — Service Layer, MCP Server, REST API and Rate Limiting

**Goal:** expose Sahayak as (a) an MCP server with `search_docs`, `get_passage`, `verify_claim` and a document resource, (b) a REST API for the UI, both on one port, behind a per-IP rate limiter and a daily LLM budget, and use it from Claude Desktop and Cursor.
**Time:** ~8 h. **Branches:** `feat/s4-service`, `feat/s4-mcp`, `feat/s4-api`, `feat/s4-ratelimit`.

## Issue text

> **S4: MCP + REST**
> - [ ] `SahayakService` is the only entry point used by REST and MCP; LLM operations consume the daily budget, search doesn't
> - [ ] FastMCP 4 server: 3 tools with validated arguments + `sahayak://docs/{doc_id}` resource
> - [ ] FastAPI `/health`, `/v1/ask`; MCP mounted at `/mcp` (streamable HTTP, stateless)
> - [ ] Token-bucket rate limit on `/v1` and `/mcp` → 429 + `Retry-After`
> - [ ] e2e tests over a real uvicorn port (SE-07, SE-08, SE-09, SE-12)
> - [ ] Works from Claude Desktop (stdio) and Cursor (HTTP)

## Concept primers

> 📘 **MCP in one paragraph.** The Model Context Protocol lets any AI client discover and call your **tools** (functions with JSON-schema arguments), read **resources** (addressable data, here `sahayak://docs/{doc_id}`) and use **prompts**. Transports: **stdio** (the client launches your server as a subprocess, local only) and **Streamable HTTP** (a URL; works remotely). The 2026-07-28 spec made HTTP stateless: no `initialize` handshake or session id; each request carries its protocol version and capabilities 📚. FastMCP 4.x implements this on top of the official SDK v2 ✅.

> 📘 **Why a service layer?** REST and MCP are two *doors* into the same house. If the budget check lived in the REST handler, an MCP client could bypass it. `SahayakService` holds every business rule once.

> 📘 **Token bucket.** Each client IP has a bucket of N tokens refilling at N per minute; a request costs one token. Bursts up to N are fine; sustained abuse gets 429 with `Retry-After`. Behind Render's proxy the real client IP is in `X-Forwarded-For`, so we trust that header **only** in the hosted profile.

## Step 1 — Service (TDD)

`src/sahayak/service.py` ✅

```python
"""Application service: the one place where retrieval, the agent and budgets meet.

Both the REST API and the MCP server call this — never the graph or the DB directly.
"""

import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, Field

from sahayak.agent.graph import build_graph
from sahayak.agent.prompts import GRADE_SYSTEM, format_passages
from sahayak.agent.schemas import EvidenceGrade
from sahayak.api.ratelimit import DailyBudget
from sahayak.llm.gateway import LLMClient
from sahayak.retrieve.types import Passage, PassageStore


class SearchPort(Protocol):
    def search(self, queries: Sequence[str], k: int) -> list[Passage]: ...


class BudgetExceededError(RuntimeError):
    """The global daily LLM budget is used up."""


class Verdict(BaseModel):
    supported: bool
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class AskResult(BaseModel):
    run_id: str
    answer: str
    citations: list[Passage]
    refused: bool
    refusal_reason: str | None = None
    degraded: bool = False  # all LLMs failed → retrieval-only result
    latency_ms: int


@dataclass
class SahayakService:
    retriever: SearchPort
    store: PassageStore
    llm: LLMClient
    budget: DailyBudget
    top_k: int = 6
    _graph: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._graph = build_graph(self.llm, self.retriever, k=self.top_k)

    # --- no-LLM operations (never budget-limited) ---------------------------------
    def search(self, query: str, k: int) -> list[Passage]:
        return self.retriever.search([query], k)

    def get_passage(self, chunk_id: str) -> Passage | None:
        return self.store.get_many([chunk_id]).get(chunk_id)

    # --- LLM operations --------------------------------------------------------------
    def verify_claim(self, claim: str, chunk_ids: list[str]) -> Verdict:
        self._spend()
        found = self.store.get_many(chunk_ids)
        if not found:
            return Verdict(supported=False)
        grade = self.llm.complete_json(
            system=GRADE_SYSTEM,
            user=f"Claim: {claim}\n\nPassages:\n"
            + format_passages([(p.chunk_id, p.text) for p in found.values()]),
            schema=EvidenceGrade,
        )
        ids = [c for c in grade.relevant_chunk_ids if c in found]
        return Verdict(supported=grade.sufficient, evidence_chunk_ids=ids)

    def ask(self, question: str) -> AskResult:
        self._spend()
        started = time.perf_counter()
        state = self._graph.invoke({"question": question})  # type: ignore[attr-defined]
        passages: list[Passage] = state.get("passages", [])
        by_id = {p.chunk_id: p for p in passages}
        degraded = bool(state.get("refused") and state.get("llm_failed") and passages)
        return AskResult(
            run_id=uuid.uuid4().hex,
            answer=state["answer"],
            citations=passages if degraded else [by_id[c] for c in state.get("citations", [])],
            refused=bool(state.get("refused")),
            refusal_reason=state.get("refusal_reason"),
            degraded=degraded,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def _spend(self) -> None:
        if not self.budget.try_spend():
            raise BudgetExceededError
```

## Step 2 — Rate limiting (TDD)

`tests/unit/api/test_ratelimit.py` ✅

```python
from datetime import date

import httpx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from sahayak.api.ratelimit import DailyBudget, RateLimitMiddleware, TokenBucket


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_bucket_allows_burst_then_blocks_with_retry_after() -> None:
    clock = FakeClock()
    bucket = TokenBucket(per_minute=2, clock=clock)
    assert bucket.allow("ip")[0]
    assert bucket.allow("ip")[0]
    assert bucket.allow("ip") == (False, 30)
    clock.t = 30.0
    assert bucket.allow("ip")[0]


def test_bucket_is_per_key() -> None:
    bucket = TokenBucket(per_minute=1, clock=FakeClock())
    assert bucket.allow("a")[0]
    assert bucket.allow("b")[0]
    assert not bucket.allow("a")[0]


def test_daily_budget_resets_next_day() -> None:
    day = [date(2026, 11, 10)]
    budget = DailyBudget(limit=2, today=lambda: day[0])
    assert budget.try_spend()
    assert budget.try_spend()
    assert not budget.try_spend()
    day[0] = date(2026, 11, 11)
    assert budget.try_spend()


async def test_middleware_returns_429_only_on_protected_paths() -> None:
    async def ok(_request: object) -> PlainTextResponse:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/v1/ask", ok), Route("/health", ok)])
    bucket = TokenBucket(per_minute=1, clock=FakeClock())
    wrapped = RateLimitMiddleware(app, bucket=bucket, prefixes=("/v1",), trust_proxy=True)
    transport = httpx.ASGITransport(app=wrapped)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        hdr = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
        assert (await client.get("/v1/ask", headers=hdr)).status_code == 200
        blocked = await client.get("/v1/ask", headers=hdr)
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
        assert (
            await client.get("/v1/ask", headers={"x-forwarded-for": "5.6.7.8"})
        ).status_code == 200
        assert (await client.get("/health", headers=hdr)).status_code == 200
```

> ✋ **Try it yourself first.** You have the failing tests above. Spend 30–45 minutes making them pass on your own before reading the reference implementation below. Then compare: what did you do differently, and why?

`src/sahayak/api/ratelimit.py` ✅

```python
"""Per-client token bucket + global daily budget, as plain classes and an ASGI middleware."""

import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from starlette.types import ASGIApp, Receive, Scope, Send

Clock = Callable[[], float]


@dataclass
class TokenBucket:
    per_minute: int
    clock: Clock = time.monotonic
    _buckets: dict[str, tuple[float, float]] = field(default_factory=dict)  # key → (tokens, ts)

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = self.clock()
        rate = self.per_minute / 60.0
        tokens, last = self._buckets.get(key, (float(self.per_minute), now))
        tokens = min(float(self.per_minute), tokens + (now - last) * rate)
        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True, 0
        self._buckets[key] = (tokens, now)
        return False, max(1, math.ceil((1.0 - tokens) / rate))


@dataclass
class DailyBudget:
    limit: int
    today: Callable[[], date] = lambda: datetime.now(UTC).date()
    _day: date | None = None
    _used: int = 0

    def try_spend(self, cost: int = 1) -> bool:
        day = self.today()
        if day != self._day:
            self._day, self._used = day, 0
        if self._used + cost > self.limit:
            return False
        self._used += cost
        return True


class RateLimitMiddleware:
    """Applies the token bucket to requests whose path starts with one of `prefixes`."""

    def __init__(
        self, app: ASGIApp, *, bucket: TokenBucket, prefixes: tuple[str, ...], trust_proxy: bool
    ) -> None:
        self.app, self.bucket, self.prefixes, self.trust_proxy = app, bucket, prefixes, trust_proxy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.prefixes):
            await self.app(scope, receive, send)
            return
        allowed, retry_after = self.bucket.allow(self._client_key(scope))
        if allowed:
            await self.app(scope, receive, send)
            return
        body = json.dumps({"detail": "rate limit exceeded"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(retry_after).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    def _client_key(self, scope: Scope) -> str:
        if self.trust_proxy:
            for name, value in scope.get("headers", []):
                if name == b"x-forwarded-for":
                    return value.decode().split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"
```

Why our own ~80 lines instead of a library? It's a pure ASGI middleware, so it protects the mounted MCP app as well as FastAPI routes (route-decorator limiters don't see mounted sub-apps), and it's fully unit-testable with an injected clock. The trade-off: state is in-process memory, which is fine for one Render instance but not for a multi-instance deployment (ADR-0009 says so).

## Step 3 — MCP server and REST app

`src/sahayak/mcp_server/server.py` ✅

```python
"""MCP surface of Sahayak: three tools + one resource, thin wrappers over the service."""

import json
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from sahayak.retrieve.types import Passage
from sahayak.service import BudgetExceededError, SahayakService, Verdict

INSTRUCTIONS = (
    "Search and cite Reserve Bank of India (RBI) Master Directions in Hindi and English. "
    "Use search_docs to find passages, get_passage to read one, and verify_claim before "
    "asserting anything. Always cite chunk_ids."
)


def build_mcp(service: SahayakService) -> FastMCP:
    mcp = FastMCP("sarkari-sahayak", instructions=INSTRUCTIONS)

    @mcp.tool
    def search_docs(
        query: Annotated[str, Field(min_length=2, max_length=500, description="Hindi or English")],
        k: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> list[Passage]:
        """Hybrid (BM25 + dense) search over RBI documents. Returns passages, best first."""
        return service.search(query, k)

    @mcp.tool
    def get_passage(chunk_id: Annotated[str, Field(min_length=3, max_length=200)]) -> Passage:
        """Fetch one passage by its chunk_id (e.g. 'MD-KYC-2016#p4c0')."""
        found = service.get_passage(chunk_id)
        if found is None:
            raise ToolError(f"unknown chunk_id: {chunk_id}")
        return found

    @mcp.tool
    def verify_claim(
        claim: Annotated[str, Field(min_length=5, max_length=1000)],
        chunk_ids: Annotated[list[str], Field(min_length=1, max_length=10)],
    ) -> Verdict:
        """Check whether the given passages support the claim."""
        try:
            return service.verify_claim(claim, chunk_ids)
        except BudgetExceededError as exc:
            raise ToolError("daily budget exhausted; try search_docs instead") from exc

    @mcp.resource("sahayak://docs/{doc_id}", mime_type="application/json")
    def document(doc_id: str) -> str:
        """Metadata and first passage of a source document."""
        first = service.get_passage(f"{doc_id}#p1c0")
        if first is None:
            raise ToolError(f"unknown doc_id: {doc_id}")
        return json.dumps(
            {"doc_id": doc_id, "title": first.title, "source_url": first.source_url},
            ensure_ascii=False,
        )

    return mcp
```

`src/sahayak/api/app.py` ✅

```python
"""FastAPI app: REST endpoints + the MCP server mounted at /mcp, behind the rate limiter."""

from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sahayak.api.ratelimit import RateLimitMiddleware, TokenBucket
from sahayak.mcp_server.server import build_mcp
from sahayak.service import AskResult, BudgetExceededError, SahayakService


class AskRequest(BaseModel):
    question: Annotated[str, Field(min_length=2, max_length=1000)]


def build_app(
    service: SahayakService, *, per_minute: int = 10, trust_proxy: bool = False
) -> FastAPI:
    mcp_app = build_mcp(service).http_app(path="/mcp", stateless_http=True)
    app = FastAPI(title="Sarkari Sahayak", version="0.1.0", lifespan=mcp_app.lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/ask")
    def ask(req: AskRequest) -> AskResult:
        try:
            return service.ask(req.question)
        except BudgetExceededError as exc:
            raise HTTPException(503, "Daily demo budget used up — try again tomorrow.") from exc

    app.mount("/", mcp_app)  # after the routes above, so they take precedence
    app.add_middleware(
        RateLimitMiddleware,  # type: ignore[arg-type]
        bucket=TokenBucket(per_minute=per_minute),
        prefixes=("/v1", "/mcp"),
        trust_proxy=trust_proxy,
    )
    return app
```

Verified with FastMCP 4.1.6 ✅: Pydantic return types become **structured content** (`result.structured_content == {"result": [...]}`) *and* text content; `Annotated[..., Field(...)]` constraints are enforced (k=99 → `ToolError`); `http_app(path="/mcp", stateless_http=True)` mounts into FastAPI as long as you pass `lifespan=mcp_app.lifespan` to `FastAPI(...)`.

`tests/unit/api/test_service_and_mcp.py` ✅

```python
from collections.abc import Sequence
from datetime import date

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from sahayak.agent.schemas import DraftAnswer, EvidenceGrade, Rewrites
from sahayak.api.app import build_app
from sahayak.api.ratelimit import DailyBudget
from sahayak.llm.gateway import LLMError
from sahayak.mcp_server.server import build_mcp
from sahayak.retrieve.types import Passage
from sahayak.service import BudgetExceededError, SahayakService
from tests.fakes import DictStore, FakeLLM, passage

KYC = passage("MD-KYC#p1c0", "केवाईसी हर दस साल में अद्यतन।")


class Search:
    def search(self, queries: Sequence[str], k: int) -> list[Passage]:
        return [KYC][:k]


def make(llm: FakeLLM, budget: int = 10) -> SahayakService:
    return SahayakService(
        retriever=Search(),
        store=DictStore({KYC.chunk_id: KYC}),
        llm=llm,
        budget=DailyBudget(limit=budget, today=lambda: date(2026, 11, 10)),
    )


def happy_llm() -> FakeLLM:
    return FakeLLM(
        {
            Rewrites: [Rewrites(hindi="h", english="e")],
            EvidenceGrade: [EvidenceGrade(sufficient=True)],
            DraftAnswer: [DraftAnswer(answer="दस साल [MD-KYC#p1c0]", citations=["MD-KYC#p1c0"])],
        }
    )


def test_ask_returns_cited_passages() -> None:
    result = make(happy_llm()).ask("केवाईसी?")
    assert result.refused is False
    assert [c.chunk_id for c in result.citations] == ["MD-KYC#p1c0"]


def test_ask_degrades_to_retrieval_only_when_llms_fail() -> None:
    llm = FakeLLM({Rewrites: [LLMError("x")] * 2, EvidenceGrade: [LLMError("x")] * 2})
    result = make(llm).ask("केवाईसी?")
    assert result.refused is True
    assert result.degraded is True
    assert [c.chunk_id for c in result.citations] == ["MD-KYC#p1c0"]


def test_budget_exhaustion_blocks_llm_calls_but_not_search() -> None:
    svc = make(happy_llm(), budget=1)
    svc.ask("केवाईसी?")
    with pytest.raises(BudgetExceededError):
        svc.ask("again")
    assert svc.search("केवाईसी", 3) == [KYC]


async def test_mcp_lists_exactly_three_tools_and_searches() -> None:
    async with Client(build_mcp(make(happy_llm()))) as client:
        names = sorted(t.name for t in await client.list_tools())
        assert names == ["get_passage", "search_docs", "verify_claim"]
        result = await client.call_tool("search_docs", {"query": "केवाईसी", "k": 1})
        assert result.structured_content == {"result": [KYC.model_dump()]}


async def test_mcp_get_passage_unknown_id_is_a_tool_error() -> None:
    async with Client(build_mcp(make(happy_llm()))) as client:
        with pytest.raises(ToolError, match="unknown chunk_id"):
            await client.call_tool("get_passage", {"chunk_id": "nope#p1c0"})


async def test_mcp_validates_arguments() -> None:
    async with Client(build_mcp(make(happy_llm()))) as client:
        with pytest.raises(ToolError):
            await client.call_tool("search_docs", {"query": "x", "k": 99})


async def test_mcp_resource_template() -> None:
    async with Client(build_mcp(make(happy_llm()))) as client:
        contents = await client.read_resource("sahayak://docs/MD-KYC")
        assert '"doc_id": "MD-KYC"' in contents[0].text  # type: ignore[union-attr]


async def test_rest_ask_validation_and_budget() -> None:
    app = build_app(make(happy_llm(), budget=1), per_minute=100)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/health")).json() == {"status": "ok"}
        assert (await c.post("/v1/ask", json={"question": "x"})).status_code == 422
        ok = await c.post("/v1/ask", json={"question": "केवाईसी?"})
        assert ok.status_code == 200
        assert ok.json()["citations"][0]["chunk_id"] == "MD-KYC#p1c0"
        assert (await c.post("/v1/ask", json={"question": "फिर से?"})).status_code == 503
```

## Step 4 — End-to-end over a real port

`tests/e2e/test_http_stack.py` ✅

```python
"""SE-07/08/12: the deployed shape — FastAPI + MCP on one port, behind the rate limiter."""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn
from fastmcp import Client
from fastmcp.utilities.http import find_available_port

from sahayak.api.app import build_app
from tests.unit.api.test_service_and_mcp import happy_llm, make

pytestmark = pytest.mark.e2e


@pytest.fixture
async def base_url() -> AsyncIterator[str]:
    port = find_available_port()
    app = build_app(make(happy_llm()), per_minute=3)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    async with asyncio.timeout(10):
        while not server.started:  # noqa: ASYNC110 - uvicorn exposes a flag, not an Event
            await asyncio.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    await task


async def test_mcp_over_http_lists_tools(base_url: str) -> None:
    async with Client(f"{base_url}/mcp") as client:
        assert {t.name for t in await client.list_tools()} == {
            "search_docs",
            "get_passage",
            "verify_claim",
        }


async def test_rate_limit_applies_to_rest(base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, trust_env=False) as http:
        codes = [(await http.get("/v1/does-not-exist")).status_code for _ in range(4)]
        assert codes[-1] == 429
        assert (await http.get("/health")).status_code == 200
```

Verified ✅ (uvicorn on a free port; `fastmcp.Client("http://…/mcp")`). Gotcha: `find_available_port` is exported from `fastmcp.utilities.http`, not `fastmcp.utilities.tests` (pyright caught it).

## Step 5 — Composition root and `serve`

`src/sahayak/bootstrap.py` ✅

```python
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
```

```bash
make up && uv run sahayak serve            # http://127.0.0.1:8000/health
curl -s localhost:8000/v1/ask -H 'content-type: application/json' \
  -d '{"question":"केवाईसी कितने साल में अपडेट करनी होती है?"}' | jq
```

## Step 6 — Use it from Claude Desktop and Cursor

**Cursor (HTTP).** Create `.cursor/mcp.json` in any project ⚠️ (format as documented by Cursor when written):

```json
{ "mcpServers": { "sarkari-sahayak": { "url": "http://127.0.0.1:8000/mcp" } } }
```

**Claude Desktop (stdio).** Claude Desktop launches local servers as subprocesses from
`~/Library/Application Support/Claude/claude_desktop_config.json` 📚. Add a stdio entry point first:

```python
# src/sahayak/mcp_server/__main__.py   →  `python -m sahayak.mcp_server`
from sahayak.bootstrap import build_service
from sahayak.config import get_settings
from sahayak.mcp_server.server import build_mcp

if __name__ == "__main__":
    build_mcp(build_service(get_settings())).run(transport="stdio", show_banner=False)
```

```json
{
  "mcpServers": {
    "sarkari-sahayak": {
      "command": "/Users/<you>/.local/bin/uv",
      "args": ["--directory", "/Users/<you>/code/sarkari-sahayak", "run", "python", "-m", "sahayak.mcp_server"],
      "env": { "SAHAYAK_PROFILE": "local" }
    }
  }
}
```

Use absolute paths (Claude Desktop doesn't load your shell `PATH`). **stdio rule:** nothing may print to stdout except MCP messages, so configure logging to **stderr** in this entry point ⚠️ (our `configure_logging` writes to stdout; add a `stream` parameter). Restart Claude Desktop, then ask it: *"Use sarkari-sahayak to find what RBI says about video-KYC, and cite chunk ids."* Record a 30-second clip for the README.

## Definition of Done

- [ ] All unit + e2e tests green; coverage gates pass
- [ ] Tool schemas snapshot test (SE-07) committed
- [ ] Works in Claude Desktop **and** Cursor (screenshots in `docs/img/`)
- [ ] ADR-0005 "FastMCP 4 over the raw SDK" and ADR-0009 "own ASGI rate limiter"

## Cursor prompt (S4)

> Read `docs/guide/sahayak/S4-mcp-server.md`. Implement Steps 1–3 test-first. The MCP server must only call `SahayakService`; it must not import anything from `retrieve/`, `store/` or `agent/` directly.
