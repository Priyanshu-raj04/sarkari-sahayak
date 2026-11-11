"""Argument policy: per-tool limits that are stricter than the upstream JSON schema."""

from pathlib import Path
from typing import Any

import regex
import yaml
from pydantic import BaseModel, Field


class ArgRule(BaseModel):
    max_length: int | None = None
    pattern: str | None = None
    allowed: list[Any] | None = None


class ToolPolicy(BaseModel):
    allow_extra_args: bool = False
    args: dict[str, ArgRule] = Field(default_factory=dict)


class Policy(BaseModel):
    default_max_string: int = 2000
    tools: dict[str, ToolPolicy] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Policy":
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})

    def violations(self, tool: str, arguments: dict[str, Any]) -> list[str]:
        rules = self.tools.get(tool, ToolPolicy(allow_extra_args=True))
        problems: list[str] = []
        for name, value in arguments.items():
            rule = rules.args.get(name)
            if rule is None and not rules.allow_extra_args:
                problems.append(f"argument '{name}' is not allowed")
                continue
            problems += _check(name, value, rule or ArgRule(), self.default_max_string)
        return problems


def _check(name: str, value: Any, rule: ArgRule, default_max: int) -> list[str]:
    problems: list[str] = []
    if isinstance(value, str):
        limit = rule.max_length or default_max
        if len(value) > limit:
            problems.append(f"argument '{name}' longer than {limit} chars")
        if rule.pattern and not regex.fullmatch(rule.pattern, value):
            problems.append(f"argument '{name}' does not match the allowed pattern")
    if rule.allowed is not None and value not in rule.allowed:
        problems.append(f"argument '{name}' has a value outside the allow-list")
    return problems
