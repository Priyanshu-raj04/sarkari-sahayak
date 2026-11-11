# 01 — Locked Decisions, Corrections & Pinned Versions

This file is the **single source of truth** for what we are building and with what. If any other file disagrees with this one, this one wins — and please fix the other file.

## 1. Scope

| Decision | Locked choice |
|---|---|
| Projects | **Sarkari Sahayak** (with the Flight Recorder living inside it as `evals/`) and **MCP Gatekeeper**. |
| Dropped for now | Bharat-τ (τ-bench Hindi study). Can return later as a third repo. |
| Repos | `Priyanshu-raj04/sarkari-sahayak`, `Priyanshu-raj04/mcp-gatekeeper` — public from day 1, MIT. Profile README later. |
| PyPI names | Gatekeeper → **`mcp-tool-gatekeeper`** (`mcp-gatekeeper` is taken on PyPI by an unrelated project ✅ checked 2026-11-10). Sahayak isn't published to PyPI (`sarkari-sahayak` was free). |
| Order | Phase 0 → Sahayak S1–S6 (v1.0) → Gatekeeper G1–G5 (v1.0) → Sahayak S7 (v1.1). |
| Story | "I build agents that are measured, secure, and work in Hindi." |
| Your level | 0–1 YoE, Python "solid basics", comfortable with git branches/PRs. |
| Way of working | You implement with Cursor, TDD, small PRs; Claude reviews/explains. You must be able to explain every line. |

## 2. Languages & data

| Decision | Locked choice |
|---|---|
| Languages | Hindi + English everywhere. Marathi only in Sahayak v1.1. |
| Demo corpus | RBI **Master Directions** + the circulars that amend them (a few hundred documents, not the archive). Small Maharashtra GR slice in v1.1. |
| Benchmarks | MIRACL-hi (dev: 350 queries, 3,494 judgments; corpus 506,264 passages in 2 shards) 📚 · NoMIRACL-hi (dev/test × relevant/non_relevant) 📚 · MTEB IndicQARetrieval `hi-*` and `mr-*` (CC0-1.0) 📚. Local only; never re-hosted. |
| Data rule | Public documents only, polite crawling (robots.txt, ≥3 s between requests), raw PDFs **not** committed to git — only a manifest with URLs + SHA-256. |

## 3. Local infrastructure (M1, 8 GB, ~50 GB free)

| Component | Where it runs | Notes |
|---|---|---|
| Container engine | **OrbStack** (free for personal use) 📚 | Set memory limit to ~2.5 GB in OrbStack settings. |
| Database | **ParadeDB** in Docker = Postgres + `pg_search` (BM25, AGPL-3.0) + `pgvector` | pg_search 0.26.5 (2026-11-04) 📚; pgvector 0.8.7 📚. Image tag ⚠️ pin exact `paradedb/paradedb:<ver>-pg18` from Docker Hub. |
| Tracing | **Arize Phoenix** in Docker, storing into a separate `phoenix` database on the same Postgres | `PHOENIX_SQL_DATABASE_URL` 📚; Postgres ≥14 supported 📚; Phoenix license is **Elastic License 2.0** (free to self-host) 📚. |
| LLM runtime | **Ollama, native** (Metal GPU) | Docker on macOS cannot use the Apple GPU 📚. Containers reach it at `host.docker.internal:11434`. |
| Main local model | `qwen3:4b-instruct` (~2.5 GB Q4) | Use the *instruct* tag — plain `qwen3:4b` is a thinking variant 📚. ⚠️ check exact tag on ollama.com/library. |
| Second local model | `gemma3:4b` (~3 GB) — writing quality comparison | Weak native tool-call format 📚 (we don't depend on native tool calls). |
| Overnight comparison | `qwen3:8b` (~5 GB) — only with everything else closed | |
| Embeddings | `intfloat/multilingual-e5-small` (384-d, needs `query:`/`passage:` prefixes) main; `BAAI/bge-m3` (1024-d dense + sparse "lexical weights") benchmarked | bge-m3 sparse via `FlagEmbedding.BGEM3FlagModel(...).encode(..., return_sparse=True)` 📚 |
| Reranker | `BAAI/bge-reranker-v2-m3` (568 M params, ~2.27 GB fp32) local only; int8 ONNX variant `BAAI/bge-reranker-v2-m3-int8` exists in fastembed ✅ | |
| App code | Native, `uv`-managed venv, **Python 3.13** | |
| LLM access layer | **LiteLLM 1.108.3, hash-locked** + our own thin wrapper | See supply-chain note below. |

## 4. Hosting & deployment (all no-card)

| Component | Where | Hard facts |
|---|---|---|
| MCP + REST API (Sahayak **behind** Gatekeeper, one service) | **Render free web service** (Docker) | 512 MB RAM / 0.1 CPU; spins down after 15 min idle; ~1 min spin-up; 750 free instance-hours/month per workspace; ephemeral filesystem 📚 |
| Hosted DB | **Neon Free** (pgvector) in **AWS Singapore** `aws-ap-southeast-1` (nearest region to India; there is no Mumbai region) 📚 | Free plan: no card, scale-to-zero after 5 min, 100 CU-hours/project/month 📚; storage per project 0.5 GB vs 1 GB is contested ⚠️ (we need < 100 MB). |
| UI | **Streamlit Community Cloud** | 690 MB–2.7 GB RAM, sleeps after 12 h without traffic 📚 |
| Reports / leaderboards | **GitHub Pages** (deployed by Actions) | |
| CI/CD | **GitHub Actions** — public repos get 4 vCPU / 16 GB RAM / 14 GB SSD `ubuntu-latest`, free and unlimited 📚 | |
| Abuse protection | Per-IP token bucket + daily global budget, in our own ASGI middleware | |

## 5. Corrections to the original research report (important!)

| Report said | Reality (verified 2026-11-09) | What we do |
|---|---|---|
| Host hybrid search on Neon with pg_search | **Neon removed `pg_search`**: blocked for new projects March 2026, removed from existing projects in September 2026; replacement is Neon's `lakebase_text` (BM25 over a `tsvector`) 📚 | Hosted BM25 = **`bm25s` in-process** (index built from Neon rows at startup). ParadeDB stays for local + benchmarks. `lakebase_text` documented as an alternative in an ADR. |
| FastMCP `as_proxy()` | Removed in FastMCP 3.0; use `from fastmcp.server import create_proxy` ✅ | Gatekeeper uses `create_proxy()` + a `Middleware` subclass ✅ |
| Official SDK `FastMCP` class | MCP Python SDK 2.x renamed it to `MCPServer` (no alias) 📚 | We use **FastMCP 4.1.6** (built on SDK `mcp` 2.3.0) ✅ |
| Groq free sample limits apply to "llama" | Free table lists `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b` at 30 RPM / 1K RPD / 8K TPM / 200K TPD 📚 | Hosted LLM = `groq/openai/gpt-oss-20b`; fallback Gemini (Flash tier from your AI Studio model list) |
| LiteLLM — no caveat | Malicious LiteLLM releases hit PyPI on 2026-03-24 (1.82.7/1.82.8) and 2026-10-21 (1.107.0 + Docker tags) 📚 | Pin `litellm==1.108.3`, `uv lock` hashes, never floating Docker tags, review every Dependabot bump by hand. |
| `PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION` is enough for local-only | Fully local also needs `PROMPTFOO_DISABLE_REMOTE_GENERATION=true`, local `redteam.provider`, telemetry off, and avoiding remote-only plugins (`harmful:*`, bias, several jailbreak strategies) 📚 | Gatekeeper G4 config sets all of these. |
| e5-small fits easily on Render | fastembed does **not** ship `multilingual-e5-small` natively (only e5-large, 2.24 GB) ✅; community ONNX "quantized" copies are ~470 MB ⚠️ | Own torch-free `OnnxE5Embedder` (onnxruntime + tokenizers, unit-tested ✅) + a measured "fits in 512 MB?" spike with a documented fallback ladder (S6). |
| Python `\w` regex tokenization is fine | **Python's `re` `\w` breaks Devanagari words** (matras are category `Mn/Mc`): `किताबें` → `['क','त','ब']` ✅ | Use the `regex` package with `[\p{L}\p{M}\p{N}]+` ✅ |
| MCP output redaction = rewrite `content` | FastMCP results carry **both** `content` and `structured_content`; redacting only `content` leaks PII ✅ | Gatekeeper redacts both (and has a test proving it). |

## 6. Pinned versions (as of 2026-11-09)

Pin these in `pyproject.toml` with `==` for the risky ones and compatible ranges for the rest; `uv lock` records hashes.

| Package | Version | Status |
|---|---|---|
| Python | 3.13.x | ✅ |
| uv | ≥ 0.11 (latest seen 0.11.20) | 📚 |
| fastmcp | 4.1.6 | ✅ |
| mcp (SDK) / mcp-types | 2.3.0 | ✅ |
| langgraph | 1.2.20 | ✅ |
| langgraph-checkpoint-postgres | 3.2.0 (only if we need persistence) | 📚 |
| litellm | **==1.108.3** | ✅ |
| pydantic / pydantic-settings | 2.14.3 / 2.16.2 | ✅/📚 |
| fastapi / uvicorn | 0.162.2 / 0.54.0 | 📚 |
| psycopg / pgvector (python) | 3.3.8 / 0.5.1 | 📚 |
| sentence-transformers / FlagEmbedding | 6.2.0 / 1.4.2 (local only) | 📚 |
| onnxruntime / tokenizers (hosted embedder) | 1.31.1 / 0.23.3 | ✅ |
| fastembed (optional, int8 reranker listing) | 0.9.1 | ✅ |
| bm25s / ranx / regex | 0.3.16 / 0.3.21 / latest | ✅ |
| pymupdf / pytesseract / krutiextract | 2.1 / 0.3.13 / 1.6.1 | ✅/📚/📚 |
| deepeval | 4.3.3 | ✅ |
| arize-phoenix (server image) / arize-phoenix-otel / openinference-instrumentation-langchain | 21.0.0 / 0.17.3 / 0.1.82 | 📚/✅/✅ |
| streamlit / playwright / respx | 1.67.0 / 1.64.1 / latest | ✅ (AppTest) / 📚 / ✅ |
| pytest / pytest-asyncio / pytest-cov / hypothesis | 9.2.0 / 1.4.1.post1 / 7.1.0 / 6.170.x | ✅/📚 |
| vcrpy / pytest-recording | 9.4.2 / 0.14.1 (httpx 2.x supported since vcrpy 8.2.0) | 📚 |
| structlog / typer | 26.1.0 / 0.28.0 | 📚 |
| presidio-analyzer (optional) | 2.2.366 — India recognizers are **disabled by default** since 2.2.359 | ✅/📚 |
| cisco-ai-mcp-scanner / snyk-agent-scan | 4.8.7 / 0.6.11 | 📚 |
| promptfoo (npm) | 0.125.1 | 📚 |
| ruff-pre-commit | v0.15.22 | 📚 |

> Re-run `uv lock --upgrade-package <name>` deliberately; never bump LiteLLM, FastMCP or MCP in the same PR as feature work.

## 7. Model & provider strings (LiteLLM)

| Purpose | Model string | Where |
|---|---|---|
| Local agent | `ollama_chat/qwen3:4b-instruct` | Mac |
| Local judge (CI + dev) | `qwen3:4b-instruct` via DeepEval `OllamaModel` | Mac, CI runner |
| Hosted agent | `groq/openai/gpt-oss-20b` | Render |
| Hosted fallback / strong judge | `gemini/<flash model from your AI Studio list>` ⚠️ (Google no longer publishes a fixed limits table) | Render, weekly CI job |

Never send personal data to the Gemini free tier: outside the EEA/UK/CH, prompts may be used to improve Google products and seen by human reviewers 📚.
