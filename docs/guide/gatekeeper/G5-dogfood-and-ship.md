# G5 — Dogfood: Sahayak's public endpoint through Gatekeeper, and ship v1.0

**Goal:** the public Render service serves Sahayak's MCP tools **through** the Gatekeeper proxy in one process, plus a results-first README and `v1.0.0` of Gatekeeper.
**Time:** ~5–6 h.

## Step 1 — One process, two layers

Verified shape ✅ (upstream FastMCP server → `create_proxy` → `GatekeeperMiddleware` → `http_app(stateless_http=True)` → real uvicorn port → `fastmcp.Client` over HTTP; PII in the upstream result was redacted):

`tests/e2e/test_dogfood_http.py` ✅

```python
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
```

In the **sahayak** repo (it depends on Gatekeeper; Gatekeeper never depends on Sahayak):

```toml
# sarkari-sahayak/pyproject.toml
dependencies = [ …, "mcp-tool-gatekeeper==1.0.0" ]
```

```python
# sarkari-sahayak/src/sahayak/api/app.py  (hosted profile)
from gatekeeper.proxy.app import build_proxy

def build_app(service, *, per_minute=10, trust_proxy=False, gatekeeper_lock: Path | None = None):
    mcp = build_mcp(service)
    if gatekeeper_lock is not None:
        mcp = build_proxy(mcp, gatekeeper_lock, Path("gatekeeper.policy.yaml"), name="sarkari-sahayak")
    mcp_app = mcp.http_app(path="/mcp", stateless_http=True)
    …
```

* Commit `gatekeeper.lock.json` (generated from Sahayak's own `tools/list`) and `gatekeeper.policy.yaml` in the Sahayak repo.
* Add a **contract test** in Sahayak: build the MCP server, list its tools, and assert they match the lockfile. If you change a tool's description, this test fails until you re-pin consciously (`gatekeeper pin …`). That's the rug-pull defence applied to your own releases.
* Add an `x-gatekeeper: <version>` response header via a small middleware, so GE-12 can check the deployed endpoint really runs through the proxy.
* Memory: the proxy adds little, but re-measure peak RSS on the hosted profile (S6 target < 450 MB).

## Step 2 — Gatekeeper README (results first)

```markdown
# MCP Gatekeeper
A firewall for MCP tools: catches poisoned tool descriptions (incl. Hindi/Hinglish), pins tools against rug pulls,
enforces argument policies and redacts Indian PII.

## Results (test split, n = …)
| detector table from docs/results/detectors.md |
| red-team attack success: without vs with Gatekeeper |

## Quick start
pip install mcp-tool-gatekeeper
gatekeeper scan --tools tools.json --format sarif --output gk.sarif
gatekeeper pin --tools tools.json --server my-server
gatekeeper proxy --target https://my-server/mcp --lockfile gatekeeper.lock.json --port 8100

## GitHub Action  (uses: Priyanshu-raj04/mcp-gatekeeper@v1)
## How it works (diagram) · Threat model (table) · Limitations · Corpus provenance & licences
```

## Step 3 — Release

Tag `v1.0.0` → the release workflow publishes to PyPI and creates the GitHub release; move the `v1` tag; then bump Sahayak to depend on `mcp-tool-gatekeeper==1.0.0`, redeploy, and run GE-12 against the live URL.

## Definition of Done (Gatekeeper v1.0)

- [ ] Live Sahayak `/mcp` runs through Gatekeeper (header check + a blocked call demo)
- [ ] Demo video #3 (2 min): poisoned PR → red CI + Security alert → rug pull blocked live → PII redacted
- [ ] PyPI + Marketplace published; both READMEs cross-link; Projects milestone closed
