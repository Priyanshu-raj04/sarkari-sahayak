.PHONY: help install up down logs fmt lint typecheck test test-int test-e2e cov check clean ingest bench-quick

help:  ## Show targets
	@grep -E "^[a-zA-Z0-9_-]+:.*?## " $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Install deps + git hooks
	uv sync --group dev
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
	uv run pytest -m "not integration and not e2e and not llm and not slow" -q

test-int:  ## Integration tests (needs make up)
	uv run pytest -m "integration and not llm" -q

test-e2e:  ## End-to-end tests (needs make up + server)
	uv run pytest -m "e2e and not llm" -q

cov:  ## Unit tests with coverage gates
	uv run pytest -m "not integration and not e2e and not llm and not slow" --cov --cov-report=term --cov-fail-under=80 -q
	uv run coverage report --include="src/sahayak/retrieve/*" --fail-under=90

check: lint typecheck cov  ## Everything CI runs on every push

ingest:  ## Download + ingest the manifest
	uv run sahayak ingest

bench-quick:  ## IndicQA-hi BM25/dense/hybrid → docs/results/retrieval.json+.md
	uv run python -m evals.benchmarks.run_retrieval --dataset indicqa-hi --systems bm25,dense,hybrid

clean:  ## Remove caches
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml htmlcov
