"""Stable SHA-256 fingerprints of tool definitions, and the pin lockfile."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel

from gatekeeper.models import ToolSpec


def fingerprint(tool: ToolSpec) -> str:
    """Hash of name + description + input schema, canonical JSON (sorted keys, UTF-8)."""
    payload = json.dumps(
        {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Lockfile(BaseModel):
    version: int = 1
    server: str
    tools: dict[str, str]  # tool name → fingerprint

    @classmethod
    def from_tools(cls, server: str, tools: list[ToolSpec]) -> "Lockfile":
        return cls(server=server, tools={t.name: fingerprint(t) for t in tools})

    def check(self, tool: ToolSpec) -> str:
        """Return 'ok', 'unpinned' or 'drift'."""
        pinned = self.tools.get(tool.name)
        if pinned is None:
            return "unpinned"
        return "ok" if pinned == fingerprint(tool) else "drift"

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Lockfile":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
