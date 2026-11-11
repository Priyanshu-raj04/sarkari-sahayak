"""GE-12 shape: upstream MCP server wrapped by the Gatekeeper proxy, served over HTTP."""

import asyncio
from collections.abc import AsyncIterator

import pytest
import uvicorn
from fastmcp import Client, FastMCP
from fastmcp.server import create_proxy
from fastmcp.utilities.http import find_available_port

from gatekeeper.fingerprint import Lockfile
from gatekeeper.models import ToolSpec
from gatekeeper.policy import Policy
from gatekeeper.proxy.middleware import GatekeeperMiddleware

pytestmark = pytest.mark.e2e


@pytest.fixture
async def url() -> AsyncIterator[str]:
    upstream = FastMCP("sahayak-stub")

    @upstream.tool
    def search_docs(query: str) -> str:
        """Search RBI documents."""
        return f"result for {query}; contact 9876543210"

    specs = [
        ToolSpec(name=t.name, description=t.description or "", input_schema=t.parameters)
        for t in await upstream.list_tools()
    ]
    proxy = create_proxy(upstream, name="gatekeeper")
    proxy.add_middleware(GatekeeperMiddleware(Lockfile.from_tools("sahayak", specs), Policy()))
    app = proxy.http_app(path="/mcp", stateless_http=True)
    port = find_available_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    async with asyncio.timeout(10):
        while not server.started:  # noqa: ASYNC110 - uvicorn exposes a flag, not an Event
            await asyncio.sleep(0.05)
    yield f"http://127.0.0.1:{port}/mcp"
    server.should_exit = True
    await task


async def test_proxied_tool_works_over_http_with_redaction(url: str) -> None:
    async with Client(url) as client:
        assert [t.name for t in await client.list_tools()] == ["search_docs"]
        res = await client.call_tool("search_docs", {"query": "KYC"})
    assert "9876543210" not in res.content[0].text  # type: ignore[union-attr]
    assert "[REDACTED_IN_MOBILE]" in res.content[0].text  # type: ignore[union-attr]
