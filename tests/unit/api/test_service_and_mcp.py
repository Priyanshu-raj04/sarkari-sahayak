"""Unit tests for SahayakService, MCP tools, and REST /v1/ask."""

import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

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

_SCHEMA_SNAP = Path(__file__).with_name("mcp_tool_schemas.json")

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


def test_verify_claim_uses_llm_grade_and_filters_ids() -> None:
    llm = FakeLLM(
        {
            EvidenceGrade: [
                EvidenceGrade(sufficient=True, relevant_chunk_ids=["MD-KYC#p1c0", "ghost#p1c0"])
            ]
        }
    )
    verdict = make(llm).verify_claim("KYC every 10 years", ["MD-KYC#p1c0"])
    assert verdict.supported is True
    assert verdict.evidence_chunk_ids == ["MD-KYC#p1c0"]


def test_verify_claim_empty_store_is_unsupported() -> None:
    llm = FakeLLM({})
    assert make(llm).verify_claim("x", ["missing#p1c0"]).supported is False


async def test_mcp_lists_exactly_three_tools_and_searches() -> None:
    async with Client(build_mcp(make(happy_llm()))) as client:
        names = sorted(t.name for t in await client.list_tools())
        assert names == ["get_passage", "search_docs", "verify_claim"]
        result = await client.call_tool("search_docs", {"query": "केवाईसी", "k": 1})
        assert result.structured_content == {"result": [KYC.model_dump()]}


async def test_mcp_tool_schemas_match_snapshot() -> None:
    """SE-07: committed input schemas stay stable for clients."""
    expected = json.loads(_SCHEMA_SNAP.read_text(encoding="utf-8"))
    async with Client(build_mcp(make(happy_llm()))) as client:
        tools = await client.list_tools()
        actual = {t.name: t.input_schema for t in tools}
    assert {k: actual[k] for k in sorted(actual)} == expected


async def test_mcp_get_passage_unknown_id_is_a_tool_error() -> None:
    async with Client(build_mcp(make(happy_llm()))) as client:
        with pytest.raises(ToolError, match="unknown chunk_id"):
            await client.call_tool("get_passage", {"chunk_id": "nope#p1c0"})


async def test_mcp_verify_claim_budget_is_tool_error() -> None:
    svc = make(happy_llm(), budget=0)
    async with Client(build_mcp(svc)) as client:
        with pytest.raises(ToolError, match="daily budget"):
            await client.call_tool(
                "verify_claim",
                {"claim": "KYC every ten years", "chunk_ids": ["MD-KYC#p1c0"]},
            )


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


async def test_root_discovery_lists_public_endpoints() -> None:
    app = build_app(make(happy_llm()), per_minute=100)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["service"] == "sarkari-sahayak"
        assert body["endpoints"]["health"] == "/health"
        assert body["endpoints"]["ask"] == "POST /v1/ask"
        assert body["endpoints"]["mcp"] == "POST /mcp"


async def test_get_mcp_explains_post_only_streamable_http() -> None:
    """Browsers/probes often GET /mcp; Streamable HTTP uses POST (FastMCP has no GET)."""
    app = build_app(make(happy_llm()), per_minute=100)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/mcp")
        assert r.status_code == 405
        assert "POST" in r.headers.get("allow", "")
        assert r.json()["transport"] == "streamable-http"
        assert (await c.get("/health")).status_code == 200
