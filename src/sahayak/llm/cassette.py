"""Hash-cassette fallback when VCR cannot capture LiteLLM↔Ollama traffic (S3 SoT Step 5)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

Mode = Literal["record", "replay"]


def _key(model: str, messages: list[dict[str, str]]) -> str:
    payload = json.dumps({"model": model, "messages": messages}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def wrap_completion(
    completion: Callable[..., Any],
    *,
    cassette_dir: Path,
    mode: Mode,
) -> Callable[..., Any]:
    """Record or replay `completion` responses keyed by sha256(model+messages)."""

    cassette_dir.mkdir(parents=True, exist_ok=True)

    def wrapped(**kwargs: Any) -> Any:
        model = str(kwargs.get("model", ""))
        messages = list(kwargs.get("messages") or [])
        path = cassette_dir / f"{_key(model, messages)}.json"
        if mode == "replay":
            if not path.exists():
                msg = f"missing cassette: {path.name}"
                raise FileNotFoundError(msg)
            data = json.loads(path.read_text(encoding="utf-8"))
            msg = SimpleNamespace(content=data["content"])
            usage = SimpleNamespace(
                prompt_tokens=data.get("prompt_tokens", 0),
                completion_tokens=data.get("completion_tokens", 0),
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)

        resp = completion(**kwargs)
        content = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        path.write_text(
            json.dumps(
                {
                    "model": model,
                    "content": content,
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return resp

    return wrapped
