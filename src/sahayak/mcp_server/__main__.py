"""Stdio MCP entry: `python -m sahayak.mcp_server` (Claude Desktop). Logs go to stderr."""

import sys

from sahayak.bootstrap import build_service
from sahayak.config import get_settings
from sahayak.logging import configure_logging
from sahayak.mcp_server.server import build_mcp

if __name__ == "__main__":
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.log_json, stream=sys.stderr)
    build_mcp(build_service(settings)).run(transport="stdio", show_banner=False)
