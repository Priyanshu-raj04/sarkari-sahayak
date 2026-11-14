# 5. FastMCP 4 over the raw SDK
Date: 2026-11-14 · Status: Accepted

## Context
S4 exposes Sahayak as an MCP server (tools + resource) for Cursor (HTTP) and Claude Desktop
(stdio). We could wire the official `mcp` Python SDK by hand, or use FastMCP 4.x which sits on
that SDK and already implements Streamable HTTP (stateless, 2026-07-28 spec) and stdio.

Hand-rolling transports, JSON Schema for tools, and FastAPI mounting would cost days and drift
from the spec. FastMCP 4.1.6 is already pinned in `pyproject.toml` (see locked decisions).

## Decision
- Use **FastMCP 4** (`fastmcp==4.1.6`) for `build_mcp(...)`: three tools + `sahayak://docs/{doc_id}`.
- Mount with `http_app(path="/mcp", stateless_http=True)` into FastAPI, sharing `lifespan`.
- Stdio entry: `python -m sahayak.mcp_server` with logging on **stderr** only.
- Do **not** bump `fastmcp` / `mcp` casually (`AGENTS.md`).

## Consequences
- MCP tools stay thin wrappers over `SahayakService` (one budget / cite-or-refuse path).
- FastMCP structured content shape (`{"result": ...}`) is what clients and tests assert.
- Upstream FastMCP API changes require reading release notes before any pin bump.
