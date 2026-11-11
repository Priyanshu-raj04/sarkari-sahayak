"""One door to every LLM: provider fallbacks, JSON parsing, schema validation, repair."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import litellm
import regex
import structlog
from pydantic import BaseModel, ValidationError

log = structlog.get_logger()

_THINK_RE = regex.compile(r"<think>.*?</think>", flags=regex.DOTALL)
_FENCE_RE = regex.compile(r"^```(?:json)?\s*|\s*```$", flags=regex.MULTILINE)


class LLMError(RuntimeError):
    """Every configured model failed."""


class LLMClient(Protocol):
    def complete_json[T: BaseModel](
        self, *, system: str, user: str, schema: type[T], temperature: float = 0.0
    ) -> T: ...


def extract_json(text: str) -> Any:
    """Parse the first JSON object in a model reply (tolerates <think> blocks and ``` fences)."""
    cleaned = _FENCE_RE.sub("", _THINK_RE.sub("", text)).strip()
    start = cleaned.find("{")
    if start == -1:
        msg = "no JSON object in reply"
        raise ValueError(msg)
    obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    return obj


@dataclass
class LiteLLMGateway:
    models: list[str]  # primary first, then fallbacks
    repair_attempts: int = 1  # extra tries per model when the JSON is invalid
    timeout_s: float = 90.0
    completion: Callable[..., Any] = litellm.completion  # injectable for tests
    api_base: str | None = None  # e.g. settings.ollama_base_url for ollama_chat/*
    last_model: str | None = field(default=None, init=False)
    usage: list[dict[str, Any]] = field(default_factory=list, init=False)

    def complete_json[T: BaseModel](
        self, *, system: str, user: str, schema: type[T], temperature: float = 0.0
    ) -> T:
        schema_hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        system_msg = f"{system}\n\nReply with ONE JSON object matching this schema:\n{schema_hint}"
        errors: list[str] = []
        for model in self.models:
            messages: list[dict[str, str]] = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user},
            ]
            for attempt in range(self.repair_attempts + 1):
                try:
                    kwargs: dict[str, Any] = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "timeout": self.timeout_s,
                    }
                    if self.api_base is not None:
                        kwargs["api_base"] = self.api_base
                    resp = self.completion(**kwargs)
                except Exception as exc:  # provider down / rate-limited → next model
                    log.warning("llm_provider_error", model=model, error=type(exc).__name__)
                    errors.append(f"{model}: {type(exc).__name__}")
                    break
                content = resp.choices[0].message.content or ""
                self._record_usage(model, resp)
                try:
                    parsed = schema.model_validate(extract_json(content))
                except (ValueError, ValidationError) as exc:
                    log.info("llm_invalid_json", model=model, attempt=attempt)
                    errors.append(f"{model}: invalid JSON ({type(exc).__name__})")
                    messages += [
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": f"Invalid: {exc}. Return only the JSON."},
                    ]
                    continue
                self.last_model = model
                return parsed
        raise LLMError("; ".join(errors) or "no models configured")

    def _record_usage(self, model: str, resp: Any) -> None:
        usage = getattr(resp, "usage", None)
        if usage is not None:
            self.usage.append(
                {
                    "model": model,
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(usage, "completion_tokens", 0),
                }
            )
