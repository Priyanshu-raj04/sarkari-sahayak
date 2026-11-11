"""Shared data types."""

from typing import Any, Literal

from pydantic import BaseModel, Field

Label = Literal["benign", "poisoned"]
Severity = Literal["low", "medium", "high"]


class ToolSpec(BaseModel):
    """What an MCP server advertises for one tool (the attack surface)."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    tool: str
    rule_id: str
    severity: Severity
    message: str
    detector: str
