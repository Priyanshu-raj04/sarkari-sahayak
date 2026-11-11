"""FastAPI app: REST endpoints + the MCP server mounted at /mcp, behind the rate limiter."""

from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from sahayak.api.ratelimit import RateLimitMiddleware, TokenBucket
from sahayak.mcp_server.server import build_mcp
from sahayak.service import AskResult, BudgetExceededError, SahayakService


class AskRequest(BaseModel):
    question: Annotated[str, Field(min_length=2, max_length=1000)]


def build_app(
    service: SahayakService, *, per_minute: int = 10, trust_proxy: bool = False
) -> FastAPI:
    mcp_app = build_mcp(service).http_app(path="/mcp", stateless_http=True)
    app = FastAPI(title="Sarkari Sahayak", version="0.1.0", lifespan=mcp_app.lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/ask")
    def ask(req: AskRequest) -> AskResult:
        try:
            return service.ask(req.question)
        except BudgetExceededError as exc:
            raise HTTPException(503, "Daily demo budget used up — try again tomorrow.") from exc

    app.mount("/", mcp_app)  # after the routes above, so they take precedence
    app.add_middleware(
        RateLimitMiddleware,  # type: ignore[arg-type]
        bucket=TokenBucket(per_minute=per_minute),
        prefixes=("/v1", "/mcp"),
        trust_proxy=trust_proxy,
    )
    return app
