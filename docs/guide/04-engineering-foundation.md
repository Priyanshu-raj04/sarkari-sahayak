# 04 — Engineering Foundation (repo skeleton for both projects)

This is the **Phase-0 PR** for each repo (`chore: bootstrap project skeleton`). Everything in this file was assembled and run in a sandbox on 2026-11-09 with uv 0.11.32 / Python 3.13: `ruff check`, `ruff format --check`, `pyright`, `pytest --cov-fail-under=80`, `docker compose config`, and JSON-schema validation of the workflow and Dependabot files all passed ✅.

Shown for **Sahayak** (package `sahayak`). For **Gatekeeper**, replace `sarkari-sahayak`→`mcp-gatekeeper`, `sahayak`→`gatekeeper`, `SAHAYAK_`→`GATEKEEPER_`, and use the dependency list in `gatekeeper/00-story-and-architecture.md`.

## 1. Target layout after Phase 0

```
sarkari-sahayak/
├── .cursor/rules/            # Cursor project rules (context + TDD rule)
├── .devcontainer/devcontainer.json
├── .github/
│   ├── ISSUE_TEMPLATE/       # from 03-git-and-github-setup.md
│   ├── pull_request_template.md
│   ├── dependabot.yml
│   └── workflows/ci.yml
├── docs/
│   ├── adr/0001-record-architecture-decisions.md
│   ├── data-sources.md       # what you verified about each data source
│   └── guide/                # ← this guide lives here
├── evals/__init__.py
├── infra/postgres/init/01-init.sql
├── src/sahayak/{__init__,config,logging,cli}.py
├── tests/{conftest.py,unit/,integration/,e2e/,fixtures/,cassettes/}
├── .env.example  .gitignore  .editorconfig  .pre-commit-config.yaml
├── AGENTS.md  CHANGELOG.md  SECURITY.md  LICENSE  README.md
├── docker-compose.yml  Makefile  pyproject.toml  uv.lock
```

## 2. Bootstrap commands

```bash
cd ~/code/sarkari-sahayak
git switch -c chore/s0-bootstrap
uv init --package --name sarkari-sahayak --python 3.13 .     # then replace pyproject.toml with §3
rm -rf src/sarkari_sahayak && mkdir -p src/sahayak tests/{unit,integration,e2e,fixtures,cassettes} evals docs/adr infra/postgres/init
# ... create the files below ...
uv sync --all-extras --group dev     # first run downloads torch (~1 GB) because of the `ml` extra
uv run pre-commit install
uv run pre-commit autoupdate         # bumps hook revs to latest tags
make check
```

> If `uv sync --all-extras` is too heavy at first, run `uv sync --group dev` (core only) and add extras when the milestone needs them.

## 3. `pyproject.toml` ✅

This is the **final** v1.0 file (all extras listed up front so you see the whole dependency picture; install extras only when a milestone needs them). Notes:
* `-p no:deepeval` in `addopts`: DeepEval registers a pytest plugin that added ~35 s of start-up to *every* test run; the eval suite enables it explicitly (S5).
* `respx` (dev) mocks `httpx` in unit tests (downloader, Streamlit).

`pyproject.toml` ✅

```toml
[project]
name = "sarkari-sahayak"
version = "0.1.0"
description = "Bilingual (Hindi/English) agentic-RAG MCP server over RBI regulations."
readme = "README.md"
license = "MIT"
authors = [{ name = "Priyanshu Raj" }]
requires-python = ">=3.13,<3.14"
dependencies = [
  "fastmcp==4.1.6",
  "mcp==2.3.0",
  "fastapi>=0.162,<0.163",
  "uvicorn>=0.54",
  "pydantic>=2.14,<3",
  "pydantic-settings>=2.16,<3",
  "structlog>=26.1",
  "httpx>=0.28",
  "regex>=2025.1.1",
  "litellm==1.108.3",
  "langgraph>=1.2.20,<1.3",
  "bm25s>=0.3.16,<0.4",
  "psycopg[binary,pool]>=3.3,<3.4",
  "pgvector>=0.5,<0.6",
  "numpy>=2",
]

[project.optional-dependencies]
ml = ["sentence-transformers>=6.2,<7", "FlagEmbedding>=1.4,<2"]
onnx = ["onnxruntime>=1.20", "tokenizers>=0.21"]  # hosted embedder (S6), no torch
ingest = ["pymupdf>=2.1,<3", "pytesseract>=0.3.13", "krutiextract>=1.6", "pillow"]
evals = ["deepeval==4.3.3", "ranx>=0.3.21,<0.4", "huggingface_hub>=0.30", "pandas", "pyarrow"]
tracing = ["arize-phoenix-otel>=0.17", "openinference-instrumentation-langchain>=0.1.82"]
ui = ["streamlit>=1.67,<2"]

[project.scripts]
sahayak = "sahayak.cli:app"

[dependency-groups]
dev = [
  "pytest>=9.2",
  "pytest-asyncio>=1.4",
  "pytest-cov>=7.1",
  "pytest-recording>=0.14",
  "vcrpy>=9.4",
  "hypothesis>=6.170",
  "ruff>=0.15",
  "pyright>=1.1.400",
  "pre-commit>=4",
  "typer>=0.28",
  "respx>=0.23.1",
]

[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "sahayak"

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "RUF", "S", "N", "PT", "ASYNC", "PL"]
ignore = ["PLR0913", "PLR2004", "RUF001", "RUF002", "RUF003"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004", "S105", "S106"]
"evals/**" = ["S101"]

[tool.pyright]
include = ["src", "tests", "evals"]
pythonVersion = "3.13"
typeCheckingMode = "standard"
venvPath = "."
venv = ".venv"

[tool.pytest.ini_options]
minversion = "9.0"
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config -p no:deepeval"
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
markers = [
  "integration: needs the docker compose stack (make up)",
  "e2e: end-to-end through API / MCP / UI",
  "llm: calls a real LLM (Ollama/Groq) — excluded from default PR run",
  "slow: > 5 s",
]

[tool.coverage.run]
source = ["sahayak"]
branch = true

[tool.coverage.report]
show_missing = true
skip_covered = true
exclude_also = ["if TYPE_CHECKING:", "raise NotImplementedError", "@overload"]
```

## 4. Source files ✅

### `src/sahayak/__init__.py`

```python
"""Sarkari Sahayak — bilingual agentic-RAG MCP server over RBI regulations."""

__version__ = "0.1.0"
```

### `src/sahayak/config.py`

> 📘 **Concept primer — pydantic-settings.** A `BaseSettings` class reads typed values from environment variables (and `.env`). Validation happens at startup, so a typo'd config crashes immediately instead of at 2 a.m. `SecretStr` hides secrets from `repr()` and logs.

```python
"""Typed application settings loaded from environment variables / .env."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Profile(StrEnum):
    LOCAL = "local"  # Mac: ParadeDB + Ollama + full models
    CI = "ci"  # GitHub Actions: replayed LLM calls, small models
    HOSTED = "hosted"  # Render: Neon + bm25s + ONNX e5 + Groq
    CODESPACES = "codespaces"  # like LOCAL but CPU-only, API LLMs


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SAHAYAK_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    profile: Profile = Profile.LOCAL
    log_level: str = "INFO"
    log_json: bool = False

    database_url: str = "postgresql://sahayak:sahayak@localhost:5432/sahayak"

    ollama_base_url: str = "http://localhost:11434"
    agent_model: str = "ollama_chat/qwen3:4b-instruct"
    fallback_models: list[str] = Field(default_factory=list)

    groq_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    embed_model: str = "intfloat/multilingual-e5-small"
    top_k: int = Field(default=8, ge=1, le=50)

    rate_limit_per_minute: int = Field(default=10, ge=1)
    daily_request_budget: int = Field(default=800, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### `src/sahayak/logging.py`

```python
"""Structured logging. JSON in hosted/CI, pretty console locally."""

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", *, json: bool = False) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # request_id, trace_id bound per request
        structlog.processors.add_log_level,
        timestamper,
    ]
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer(ensure_ascii=False)  # keep Devanagari readable
        if json
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[*shared, structlog.processors.format_exc_info, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
```

### `src/sahayak/cli.py`

```python
"""`sahayak` command-line entry point."""

import typer

from sahayak import __version__

app = typer.Typer(no_args_is_help=True, help="Sarkari Sahayak CLI")


@app.callback()
def main() -> None:
    """Sarkari Sahayak: ingest, index, benchmark and serve."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)
```

> Gotcha found while verifying: with a single `@app.command()` and no `@app.callback()`, Typer collapses the command into the root and `sahayak version` fails with "unexpected extra argument". The callback keeps sub-commands working ✅.

## 5. Tests that ship with the skeleton ✅ (your first TDD reps)

### `tests/conftest.py`

`tests/conftest.py` ✅

```python
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from sahayak.config import get_settings


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every test starts with no SAHAYAK_* env vars and no .env file in cwd."""
    for key in list(os.environ):
        if key.startswith("SAHAYAK_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
```

### `tests/unit/test_config.py`

```python
import pytest

from sahayak.config import Profile, Settings


def test_defaults_are_local_profile() -> None:
    s = Settings()
    assert s.profile is Profile.LOCAL
    assert s.top_k == 8


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAHAYAK_PROFILE", "hosted")
    monkeypatch.setenv("SAHAYAK_TOP_K", "5")
    monkeypatch.setenv("SAHAYAK_GROQ_API_KEY", "gsk_test")
    s = Settings()
    assert s.profile is Profile.HOSTED
    assert s.top_k == 5
    assert s.groq_api_key is not None
    assert s.groq_api_key.get_secret_value() == "gsk_test"
    assert "gsk_test" not in repr(s)  # secrets never leak into logs


def test_rejects_invalid_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAHAYAK_TOP_K", "0")
    with pytest.raises(ValueError, match="top_k"):
        Settings()
```

### `tests/unit/test_logging.py`

```python
import json

import pytest
import structlog

from sahayak.logging import configure_logging


def test_json_logs_keep_devanagari_and_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json=True)
    structlog.contextvars.bind_contextvars(request_id="r-1")
    structlog.get_logger().info("query_received", q="केवाईसी नियम")
    structlog.contextvars.clear_contextvars()
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["q"] == "केवाईसी नियम"
    assert line["request_id"] == "r-1"
    assert line["level"] == "info"


def test_debug_is_filtered_at_info(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO", json=True)
    structlog.get_logger().debug("noisy")
    assert "noisy" not in capsys.readouterr().out
```

### `tests/unit/test_cli.py`

```python
from typer.testing import CliRunner

from sahayak import __version__
from sahayak.cli import app


def test_version_command_prints_package_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
```

## 6. `Makefile` ✅

Makefiles need **tab** indentation. Later milestones add `ingest`, `bench`, `serve`, `ui`, `record`, `evals` targets.

`Makefile` ✅

```makefile
.PHONY: help install up down logs fmt lint typecheck test test-int test-e2e cov check clean

help:  ## Show targets
	@grep -E "^[a-zA-Z0-9_-]+:.*?## " $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install deps + git hooks
	uv sync --all-extras --group dev
	uv run pre-commit install

up:  ## Start ParadeDB (+ Phoenix with TRACING=1)
	docker compose $(if $(TRACING),--profile tracing,) up -d --wait

down:  ## Stop containers (keeps data)
	docker compose --profile tracing down

logs:  ## Tail container logs
	docker compose --profile tracing logs -f --tail=100

fmt:  ## Auto-format + autofix
	uv run ruff format . && uv run ruff check --fix .

lint:  ## Lint (no changes)
	uv run ruff check . && uv run ruff format --check .

typecheck:  ## Static types
	uv run pyright

test:  ## Fast unit tests
	uv run pytest -m "not integration and not e2e and not llm" -q

test-int:  ## Integration tests (needs make up)
	uv run pytest -m "integration and not llm" -q

test-e2e:  ## End-to-end tests (needs make up + server)
	uv run pytest -m "e2e and not llm" -q

cov:  ## Unit tests with coverage gates
	uv run pytest -m "not integration and not e2e and not llm" --cov --cov-report=term --cov-fail-under=80 -q

check: lint typecheck cov  ## Everything CI runs on every PR

clean:  ## Remove caches
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml htmlcov
```

(The help regex includes digits so `test-e2e` shows up — a bug caught during verification.)

## 7. `docker-compose.yml` ✅ (`docker compose config` validated)

> 📘 **Concept primer — Docker Compose.** One YAML file declares the services your app depends on. `make up` starts them; data lives in a named volume (`pgdata`) that survives restarts. Only *services* run in Docker here — Ollama and your Python app run natively (GPU + fast reload).

`docker-compose.yml` ✅

```yaml
name: sahayak

services:
  db:
    # Pin the exact tag from https://hub.docker.com/r/paradedb/paradedb/tags (pg18 line).
    image: paradedb/paradedb:${PARADEDB_TAG:-latest-pg18}
    environment:
      POSTGRES_USER: sahayak
      POSTGRES_PASSWORD: sahayak
      POSTGRES_DB: sahayak
    ports: ["5432:5432"]
    shm_size: 1g            # parallel queries fail with Docker's 64 MB default /dev/shm
    volumes:
      - pgdata:/var/lib/postgresql
      - ./infra/postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sahayak -d sahayak"]
      interval: 5s
      timeout: 3s
      retries: 20
    deploy:
      resources:
        limits: { memory: 768m }

  phoenix:
    image: arizephoenix/phoenix:${PHOENIX_TAG:-latest}
    depends_on:
      db: { condition: service_healthy }
    environment:
      PHOENIX_SQL_DATABASE_URL: postgresql://sahayak:sahayak@db:5432/phoenix
    ports:
      - "6006:6006"   # UI + OTLP/HTTP (/v1/traces)
      - "4317:4317"   # OTLP/gRPC
    deploy:
      resources:
        limits: { memory: 512m }
    profiles: ["tracing"]

volumes:
  pgdata:
```

⚠️ **Pin tags before S1 ends.** Look up the newest `paradedb/paradedb:<version>-pg18` (pg_search 0.26.x line) and `arizephoenix/phoenix:version-21.0.0` on Docker Hub, put them in `.env` as `PARADEDB_TAG`/`PHOENIX_TAG`, and use the same tags in CI. Verify the volume path: PG18 images store data under `/var/lib/postgresql/18/...`, which is why we mount the parent `/var/lib/postgresql` (as ParadeDB's own PG18 example does) 📚.

### `infra/postgres/init/01-init.sql`

```sql
-- Runs once, on first start of an empty volume.
CREATE DATABASE phoenix;
\connect sahayak
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;
```

## 8. `.env.example` (commit) / `.env` (never commit)

```dotenv
SAHAYAK_PROFILE=local
SAHAYAK_LOG_LEVEL=INFO
SAHAYAK_DATABASE_URL=postgresql://sahayak:sahayak@localhost:5432/sahayak
SAHAYAK_OLLAMA_BASE_URL=http://localhost:11434
SAHAYAK_AGENT_MODEL=ollama_chat/qwen3:4b-instruct
# SAHAYAK_GROQ_API_KEY=
# SAHAYAK_GEMINI_API_KEY=
PARADEDB_TAG=latest-pg18
PHOENIX_TAG=latest
```

Append to `.gitignore`:

```gitignore
.env
data/                 # raw PDFs, datasets, indexes (manifests live in data_manifest/)
*.onnx
.cache/
coverage.xml
htmlcov/
playwright-report/
test-results/
```

## 9. `.pre-commit-config.yaml` ✅ (`pre-commit validate-config` passed)

`.pre-commit-config.yaml` ✅

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: ["--maxkb=800"]
      - id: detect-private-key
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.22
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.2
    hooks:
      - id: gitleaks
  - repo: local
    hooks:
      - id: pyright
        name: pyright
        entry: uv run pyright
        language: system
        types: [python]
        pass_filenames: false
      - id: uv-lock
        name: uv lock is up to date
        entry: uv lock --check
        language: system
        files: ^(pyproject\.toml|uv\.lock)$
        pass_filenames: false
```

Run `uv run pre-commit autoupdate` once — the `rev`s above are known-good but may not be the newest ⚠️. Note the Ruff hook id is `ruff-check` (renamed from `ruff`) 📚.

## 10. CI — `.github/workflows/ci.yml` ✅ (schema-validated)

> 📘 **Concept primer — CI gates.** Every PR runs the same `make check` you run locally, on a clean machine. The job name `check` is what the ruleset requires, so a red `check` makes merging impossible.

`.github/workflows/ci.yml` ✅

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

env:
  SAHAYAK_PROFILE: ci
  UV_FROZEN: "1"          # fail if uv.lock is out of date

jobs:
  check:                  # the ruleset requires this exact job name
    runs-on: ubuntu-latest
    timeout-minutes: 25
    services:
      db:
        image: paradedb/paradedb:latest-pg18   # pin the same tag as docker-compose.yml
        env:
          POSTGRES_USER: sahayak
          POSTGRES_PASSWORD: sahayak
          POSTGRES_DB: sahayak
        ports: ["5432:5432"]
        options: >-
          --shm-size=1g
          --health-cmd "pg_isready -U sahayak -d sahayak"
          --health-interval 5s --health-timeout 3s --health-retries 20
    env:
      TEST_DATABASE_URL: postgresql://sahayak:sahayak@localhost:5432/sahayak
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true
      - run: uv python install 3.13
      - run: uv sync --all-extras --group dev
      - name: Lint
        run: uv run ruff check . && uv run ruff format --check .
      - name: Types
        run: uv run pyright
      - name: Tests (unit + integration + e2e, no live LLM) with coverage gates
        run: |
          uv run pytest -m "not llm" --cov --cov-report=term --cov-report=xml --cov-fail-under=80
          uv run coverage report --include="src/sahayak/retrieve/*,src/sahayak/agent/*" --fail-under=90
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage-xml
          path: coverage.xml
```

Notes:
* **One job, one gate.** Unit, integration (against the ParadeDB service container) and replayed e2e tests run together, so the coverage gate sees *all* code — including the DB adapters. An earlier draft split them into two jobs; that hid `store/` from coverage, so it was merged.
* The 90 % gate on `retrieve/` and `agent/` only starts passing once those packages exist (S2/S3). Until then, comment that line out — don't lower the number.
* `TEST_DATABASE_URL` deliberately has **no** `SAHAYAK_` prefix: the autouse `isolated_env` fixture deletes every `SAHAYAK_*` variable (bug caught during verification — integration tests were silently skipping).
* When `CI` is set (GitHub sets it), integration tests **fail** instead of skipping if Postgres is unreachable.
* pytest only honours the **last** `-m` flag, so combine markers in one expression (bug caught during verification).
* ⚠️ `actions/checkout@v5`, `astral-sh/setup-uv@v7`, `actions/upload-artifact@v4` were current majors when checked; Dependabot (`github-actions` ecosystem) will propose bumps. For extra supply-chain safety, pin actions by full commit SHA.
* With `--all-extras`, CI downloads torch. To speed things up later, split extras per job.

## 11. `.github/dependabot.yml` ✅

`.github/dependabot.yml` ✅

```yaml
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    schedule: { interval: "weekly" }
    open-pull-requests-limit: 5
    groups:
      dev-tools:
        dependency-type: "development"
    ignore:
      # Security-sensitive / breaking-prone: bump by hand in a dedicated PR.
      - dependency-name: "litellm"
      - dependency-name: "fastmcp"
      - dependency-name: "mcp"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
  - package-ecosystem: "docker"
    directory: "/"
    schedule: { interval: "weekly" }
```

## 12. Codespaces — `.devcontainer/devcontainer.json`

```jsonc
{
  "name": "sarkari-sahayak",
  "image": "mcr.microsoft.com/devcontainers/python:1-3.13-bookworm",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/node:1": {}
  },
  "hostRequirements": { "cpus": 2, "memory": "8gb" },
  "containerEnv": { "SAHAYAK_PROFILE": "codespaces" },
  "postCreateCommand": "curl -LsSf https://astral.sh/uv/install.sh | sh && ~/.local/bin/uv sync --group dev --extra evals && ~/.local/bin/uv run pre-commit install",
  "forwardPorts": [8000, 8501, 6006],
  "customizations": {
    "vscode": { "extensions": ["ms-python.python", "charliermarsh.ruff", "tamasfe.even-better-toml"] }
  }
}
```

The Codespaces profile has no GPU and no Ollama by default: it uses `groq/openai/gpt-oss-20b` for the agent and replays cassettes in tests. ⚠️ Codespaces free quota is 120 core-hours + 15 GB-month per month for personal accounts 📚 — stop codespaces when done.

## 13. Cursor context — `AGENTS.md` + `.cursor/rules/`

### `AGENTS.md` (repo root; Cursor and other coding agents read it)

```markdown
# AGENTS.md — Sarkari Sahayak

## What this is
A bilingual (Hindi/English) agentic-RAG MCP server over RBI Master Directions. Every answer must cite
chunk ids from retrieved passages, or the system must refuse. See docs/guide/sahayak/00-story-and-architecture.md.

## Golden rules
1. TDD: write/adjust a failing test first, then the minimum code to pass, then refactor.
2. Never call a real LLM or the network in unit tests. Use FakeLLM / cassettes / fixtures.
3. Python 3.13, type hints everywhere, pyright must pass. Pydantic models at every boundary.
4. Tokenize Hindi with the `regex` package `[\p{L}\p{M}\p{N}]+` — never `re`'s `\w` (it splits Devanagari).
5. All config through `sahayak.config.Settings`; no os.environ reads elsewhere.
6. Small functions, pure where possible; I/O at the edges (adapters), logic in the core.
7. Don't add dependencies without asking; never bump litellm/fastmcp/mcp casually.
8. Conventional commit messages. Don't commit data/, .env, PDFs, model files.

## Commands
make up | make check | make test-int | make test-e2e | uv run sahayak --help
```

### `.cursor/rules/tdd.mdc`

```markdown
---
description: TDD and testing conventions for this repo
globs: ["src/**/*.py", "tests/**/*.py", "evals/**/*.py"]
alwaysApply: true
---
- When asked to implement something, first propose/write the failing test(s) in tests/unit (or tests/integration
  if it needs Postgres), show them, then implement.
- Test names describe behaviour: test_<unit>_<does_what>_<when_condition>.
- Use the fixtures in tests/conftest.py. Use FakeLLM (tests/fakes.py) for any LLM-dependent code.
- Mark tests: @pytest.mark.integration (needs docker), @pytest.mark.e2e, @pytest.mark.llm (real model).
- Keep coverage ≥ 80% overall and ≥ 90% for src/sahayak/retrieve and src/sahayak/agent.
```

### `.cursor/rules/project-context.mdc`

```markdown
---
description: Architecture and domain context for Sarkari Sahayak
alwaysApply: true
---
Read docs/guide/sahayak/00-story-and-architecture.md for the story, component diagram and data model.
Domain: RBI Master Directions (EN + HI). Users ask in Hindi, English or Hinglish. Answers must be in the
user's language with [chunk_id] citations; if evidence is insufficient, refuse in both languages.
```

⚠️ Cursor's rule-file frontmatter (`description`, `globs`, `alwaysApply`) is what Cursor used when this guide was written; if Cursor shows the rule as invalid, recreate it from **Cursor Settings → Rules**.

## 14. Docs skeleton

### `docs/adr/0001-record-architecture-decisions.md`

```markdown
# 1. Record architecture decisions
Date: 2026-11-10 · Status: Accepted

## Context
We need a lightweight, reviewable record of why the system looks the way it does.

## Decision
We use Architecture Decision Records (Michael Nygard format): Context → Decision → Consequences.
One file per decision in docs/adr/, numbered, never edited after Accepted (supersede instead).

## Consequences
Every non-obvious choice (DB, model, hosting, protocol) gets an ADR in the PR that introduces it.
```

ADRs you will write (Sahayak): `0002-paradedb-local-neon-hosted`, `0003-bm25s-for-hosted-bm25` (because Neon removed pg_search), `0004-e5-small-main-embedder`, `0005-fastmcp-4`, `0006-litellm-pinned-gateway`, `0007-cite-or-refuse-policy`, `0008-replay-llm-in-pr-ci`, `0009-own-rate-limiter`.

### `SECURITY.md`

```markdown
# Security Policy
Report vulnerabilities privately via GitHub → Security → "Report a vulnerability".
Do not open public issues for security problems. Expect an acknowledgement within 7 days.
Supported versions: the latest minor release.
```

### `CHANGELOG.md` — "Keep a Changelog" format with an `## [Unreleased]` section at the top.

### `docs/data-sources.md` — a table you fill as you verify things: source, URL, licence/terms, date checked, findings.

## Phase-0 Definition of Done

- [ ] `make check` green locally; CI `check` green on the PR
- [ ] Ruleset created (now that `check` exists) and enforced
- [ ] README has a one-paragraph description + "🚧 under active development" + roadmap list
- [ ] `AGENTS.md`, `.cursor/rules/*`, ADR-0001, SECURITY.md, CHANGELOG.md committed
- [ ] PR squash-merged as `chore: bootstrap project skeleton`; tag `v0.1.0`

### Cursor prompt (Phase 0)

> Read `AGENTS.md` and `docs/guide/04-engineering-foundation.md`. Create exactly the files listed in sections 3–14 with the given contents. Don't add anything else. Then run `make check` and show me the output.
