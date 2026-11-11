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
