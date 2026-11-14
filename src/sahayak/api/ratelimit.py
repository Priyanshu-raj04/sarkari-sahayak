"""Per-client token bucket + global daily budget, as plain classes and an ASGI middleware."""

import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from starlette.types import ASGIApp, Receive, Scope, Send

Clock = Callable[[], float]


@dataclass
class TokenBucket:
    per_minute: int
    clock: Clock = time.monotonic
    _buckets: dict[str, tuple[float, float]] = field(default_factory=dict)  # key → (tokens, ts)

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = self.clock()
        rate = self.per_minute / 60.0
        tokens, last = self._buckets.get(key, (float(self.per_minute), now))
        tokens = min(float(self.per_minute), tokens + (now - last) * rate)
        if tokens >= 1.0:
            self._buckets[key] = (tokens - 1.0, now)
            return True, 0
        self._buckets[key] = (tokens, now)
        return False, max(1, math.ceil((1.0 - tokens) / rate))


@dataclass
class DailyBudget:
    limit: int
    today: Callable[[], date] = lambda: datetime.now(UTC).date()
    _day: date | None = None
    _used: int = 0

    def try_spend(self, cost: int = 1) -> bool:
        day = self.today()
        if day != self._day:
            self._day, self._used = day, 0
        if self._used + cost > self.limit:
            return False
        self._used += cost
        return True


class RateLimitMiddleware:
    """Applies the token bucket to requests whose path starts with one of `prefixes`."""

    def __init__(
        self, app: ASGIApp, *, bucket: TokenBucket, prefixes: tuple[str, ...], trust_proxy: bool
    ) -> None:
        self.app, self.bucket, self.prefixes, self.trust_proxy = app, bucket, prefixes, trust_proxy

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.prefixes):
            await self.app(scope, receive, send)
            return
        allowed, retry_after = self.bucket.allow(self._client_key(scope))
        if allowed:
            await self.app(scope, receive, send)
            return
        body = json.dumps({"detail": "rate limit exceeded"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(retry_after).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    def _client_key(self, scope: Scope) -> str:
        if self.trust_proxy:
            for name, value in scope.get("headers", []):
                if name == b"x-forwarded-for":
                    return value.decode().split(",")[0].strip()
        client = scope.get("client")
        return client[0] if client else "unknown"
