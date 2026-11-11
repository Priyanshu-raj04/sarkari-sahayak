from datetime import date

import httpx
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from sahayak.api.ratelimit import DailyBudget, RateLimitMiddleware, TokenBucket


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_bucket_allows_burst_then_blocks_with_retry_after() -> None:
    clock = FakeClock()
    bucket = TokenBucket(per_minute=2, clock=clock)
    assert bucket.allow("ip")[0]
    assert bucket.allow("ip")[0]
    assert bucket.allow("ip") == (False, 30)
    clock.t = 30.0
    assert bucket.allow("ip")[0]


def test_bucket_is_per_key() -> None:
    bucket = TokenBucket(per_minute=1, clock=FakeClock())
    assert bucket.allow("a")[0]
    assert bucket.allow("b")[0]
    assert not bucket.allow("a")[0]


def test_daily_budget_resets_next_day() -> None:
    day = [date(2026, 11, 10)]
    budget = DailyBudget(limit=2, today=lambda: day[0])
    assert budget.try_spend()
    assert budget.try_spend()
    assert not budget.try_spend()
    day[0] = date(2026, 11, 11)
    assert budget.try_spend()


async def test_middleware_returns_429_only_on_protected_paths() -> None:
    async def ok(_request: object) -> PlainTextResponse:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/v1/ask", ok), Route("/health", ok)])
    bucket = TokenBucket(per_minute=1, clock=FakeClock())
    wrapped = RateLimitMiddleware(app, bucket=bucket, prefixes=("/v1",), trust_proxy=True)
    transport = httpx.ASGITransport(app=wrapped)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        hdr = {"x-forwarded-for": "1.2.3.4, 10.0.0.1"}
        assert (await client.get("/v1/ask", headers=hdr)).status_code == 200
        blocked = await client.get("/v1/ask", headers=hdr)
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
        assert (
            await client.get("/v1/ask", headers={"x-forwarded-for": "5.6.7.8"})
        ).status_code == 200
        assert (await client.get("/health", headers=hdr)).status_code == 200
