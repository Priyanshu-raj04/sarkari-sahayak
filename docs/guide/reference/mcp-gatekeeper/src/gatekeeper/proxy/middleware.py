"""The firewall: FastMCP middleware for a proxy built with `create_proxy()`."""

from collections.abc import Sequence
from typing import Any

import structlog
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import Tool, ToolResult
from mcp.types import TextContent

from gatekeeper.fingerprint import Lockfile
from gatekeeper.models import ToolSpec
from gatekeeper.pii.redactor import redact
from gatekeeper.policy import Policy

audit = structlog.get_logger("gatekeeper.audit")


def _spec(tool: Tool) -> ToolSpec:
    return ToolSpec(
        name=tool.name, description=tool.description or "", input_schema=tool.parameters
    )


def _redact_obj(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_obj(v) for v in value]
    if isinstance(value, dict):
        return {k: _redact_obj(v) for k, v in value.items()}
    return value


class GatekeeperMiddleware(Middleware):
    def __init__(self, lock: Lockfile, policy: Policy) -> None:
        self.lock, self.policy = lock, policy
        self._verified: dict[str, str] = {}  # name → status from the last listing

    async def on_list_tools(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, Sequence[Tool]]
    ) -> Sequence[Tool]:
        # NOTE: on the 2026-07-28 HTTP path this also runs before every tools/call (FastMCP #5652),
        # so it must stay cheap: hashing a few small JSON blobs is fine.
        tools = await call_next(context)
        allowed: list[Tool] = []
        for tool in tools:
            status = self.lock.check(_spec(tool))
            self._verified[tool.name] = status
            if status == "ok":
                allowed.append(tool)
            else:
                audit.warning(f"tool_{status}", tool=tool.name)
        return allowed

    async def on_call_tool(
        self, context: MiddlewareContext[Any], call_next: CallNext[Any, ToolResult]
    ) -> ToolResult:
        name: str = context.message.name
        # Re-list upstream on every call (rug pulls can happen between list and call). The listing
        # runs through on_list_tools above, which records each tool's pin status.
        server = context.fastmcp_context.fastmcp  # type: ignore[union-attr]
        await server.list_tools()
        status = self._verified.get(name, "unpinned")
        if status != "ok":
            audit.warning("call_blocked", tool=name, reason=status)
            raise ToolError(f"tool '{name}' blocked by gatekeeper ({status})")
        args: dict[str, Any] = dict(context.message.arguments or {})
        problems = self.policy.violations(name, args)
        if problems:
            audit.warning("call_blocked", tool=name, reason="policy", problems=problems)
            raise ToolError("; ".join(problems))
        clean = _redact_obj(args)
        msg = context.message.model_copy(update={"arguments": clean})
        result = await call_next(context.copy(message=msg))
        return ToolResult(
            content=[
                TextContent(type="text", text=redact(c.text)) if isinstance(c, TextContent) else c
                for c in result.content
            ],
            structured_content=_redact_obj(result.structured_content),
            meta=result.meta,
        )
