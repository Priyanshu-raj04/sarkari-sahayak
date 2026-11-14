# 9. Own ASGI rate limiter
Date: 2026-11-14 · Status: Accepted

## Context
REST (`/v1/*`) and MCP (`/mcp`) share one ASGI app. Route-decorator rate limiters only see
FastAPI routes and would **miss** the mounted MCP sub-app, letting tool calls bypass limits.
Third-party limiters often assume Redis or multi-worker state we do not have on a single
Render free instance.

## Decision
- Ship a small **in-process** `TokenBucket` + `RateLimitMiddleware` (~80 lines) in
  `sahayak.api.ratelimit`.
- Protect path prefixes `("/v1", "/mcp")`; leave `/health` unlimited for probes.
- Trust `X-Forwarded-For` **only** when `profile == hosted` (Render proxy).
- Keep a separate `DailyBudget` on `SahayakService` for LLM ops (search is free).

## Consequences
- One limiter covers REST and MCP; unit-testable with an injected clock.
- State is process-local — fine for one instance; multi-instance would need shared storage later.
- 429 responses include `Retry-After` (seconds).
