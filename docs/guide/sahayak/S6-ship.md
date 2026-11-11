# S6 — Ship v1.0: Docker, Neon, Render, Streamlit Cloud, README, release

**Goal:** a public, free, no-card deployment that survives sleeping hosts, plus a README that leads with results. Tag `v1.0.0`.
**Time:** ~10 h. **Branches:** `feat/s6-hosted-profile`, `chore/s6-docker`, `chore/s6-deploy`, `docs/s6-readme`.

## Issue text

> **S6: Ship v1.0**
> - [ ] Hosted profile: Neon (pgvector) + `InMemoryBM25` (bm25s) + `OnnxE5Embedder` + Groq→Gemini fallback
> - [ ] **Measured** peak RSS of the hosted process < 450 MB with the RBI corpus loaded (Render free = 512 MB)
> - [ ] The hosted configuration is benchmarked and its row is in the results table
> - [ ] Docker image builds in CI; Render deploy from `render.yaml`; Streamlit app on Community Cloud
> - [ ] README: results first, demo GIF/video, architecture, how to reproduce, limitations
> - [ ] `v1.0.0` tag + GitHub release

## Concept primers

> 📘 **Why a separate hosted profile?** Render's free web service has 512 MB RAM, 0.1 CPU, spins down after 15 minutes idle and takes about a minute to wake 📚. PyTorch alone wouldn't fit. So hosted = no torch (ONNX), no ParadeDB (Neon removed `pg_search` in 2026 📚 → BM25 in-process with bm25s), API LLMs instead of Ollama. Same code paths otherwise: only `bootstrap.py` changes.

> 📘 **Honest degradation.** The hosted demo is *weaker* than the local system (no reranker, smaller compute). That's fine if you **measure it and say so**: one extra row in the results table.

## Step 1 — ONNX embedder (TDD) + the 512 MB spike

`tests/unit/test_onnx_e5.py` ✅

```python
from types import SimpleNamespace
from typing import Any

import numpy as np

from sahayak.embed.onnx_e5 import OnnxE5Embedder


class FakeTokenizer:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def enable_truncation(self, max_length: int) -> None: ...
    def enable_padding(self) -> None: ...

    def encode_batch(self, texts: list[str]) -> list[SimpleNamespace]:
        self.texts += texts
        return [SimpleNamespace(ids=[1, 2, 0], attention_mask=[1, 1, 0]) for _ in texts]


class FakeSession:
    def get_inputs(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(name=n) for n in ("input_ids", "attention_mask", "token_type_ids")]

    def run(self, output_names: Any, feed: dict[str, np.ndarray], /) -> list[np.ndarray]:
        assert set(feed) == {"input_ids", "attention_mask", "token_type_ids"}
        batch = feed["input_ids"].shape[0]
        hidden = np.zeros((batch, 3, 384), dtype=np.float32)
        hidden[:, 0, 0] = 3.0  # token 1
        hidden[:, 1, 1] = 4.0  # token 2
        hidden[:, 2, 2] = 100.0  # padding — must be ignored by mean pooling
        return [hidden]


def test_mean_pooling_ignores_padding_and_normalises() -> None:
    tok = FakeTokenizer()
    emb = OnnxE5Embedder(tok, FakeSession())
    vec = emb.embed_query("केवाईसी")
    assert np.allclose(vec[:3], [0.6, 0.8, 0.0])  # (3,4)/2 normalised; padding ignored
    assert vec.dtype == np.float32
    assert emb.embed_passages(["a", "b"]).shape == (2, 384)
    assert tok.texts == ["query: केवाईसी", "passage: a", "passage: b"]
```

`src/sahayak/embed/onnx_e5.py` ✅

```python
"""Torch-free e5 embedder for the 512 MB hosted profile: tokenizers + onnxruntime + mean pooling."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np


class _Session(Protocol):  # the subset of onnxruntime.InferenceSession we use
    def run(self, output_names: Any, input_feed: Any, /) -> Any: ...
    def get_inputs(self) -> Any: ...


class OnnxE5Embedder:
    dim = 384

    def __init__(self, tokenizer: Any, session: _Session, max_length: int = 512) -> None:
        self.tokenizer, self.session = tokenizer, session
        self.tokenizer.enable_truncation(max_length=max_length)
        self.tokenizer.enable_padding()
        self._input_names = {i.name for i in session.get_inputs()}

    @classmethod
    def load(cls, model_dir: str | Path, threads: int = 1) -> "OnnxE5Embedder":
        import onnxruntime as ort  # noqa: PLC0415 - optional (extra "onnx")
        from tokenizers import Tokenizer  # noqa: PLC0415

        d = Path(model_dir)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads  # Render free = 0.1 CPU; more threads only thrash
        session = ort.InferenceSession(
            str(d / "model.onnx"), opts, providers=["CPUExecutionProvider"]
        )
        return cls(Tokenizer.from_file(str(d / "tokenizer.json")), session)

    def embed_query(self, query: str) -> np.ndarray:
        return self._encode([f"query: {query}"])[0]

    def embed_passages(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode([f"passage: {t}" for t in texts])

    def _encode(self, texts: list[str]) -> np.ndarray:
        enc = self.tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.zeros_like(ids)
        hidden = np.asarray(self.session.run(None, feed)[0])  # (batch, seq, dim) last_hidden_state
        summed = (hidden * mask[..., None]).sum(axis=1)
        pooled = summed / np.clip(mask.sum(axis=1, keepdims=True), 1, None)  # mean pooling (e5)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return (pooled / np.clip(norms, 1e-12, None)).astype(np.float32)
```

Unit-tested with fakes ✅ (mean pooling ignores padding, L2-normalised, prefixes, `token_type_ids` handled). **Not yet run with the real model** ⚠️. Your spike (time-box 3 h):

1. Export the model locally on the Mac:
   ```bash
   uv run --with "optimum[onnxruntime]" optimum-cli export onnx \
     --model intfloat/multilingual-e5-small --task feature-extraction models/e5-small-onnx
   ```
   ⚠️ verify the CLI flags against the Optimum docs. Optionally quantise to int8 (`onnxruntime.quantization.quantize_dynamic`) and **re-run the IndicQA-hi benchmark** on both: quantisation can cost accuracy.
2. Parity test (`@pytest.mark.slow`, local only): for 20 Hindi/English sentences, cosine(ONNX vector, sentence-transformers vector) ≥ 0.99 (fp32) / ≥ 0.97 (int8).
3. Memory: run `SAHAYAK_PROFILE=hosted uv run sahayak serve`, load the RBI corpus, fire 20 requests, and read peak RSS (`/usr/bin/time -l` on macOS reports "maximum resident set size"). Target < 450 MB.
4. Fallback ladder if it doesn't fit (record the outcome in ADR-0010):
   1. int8 model + `intra_op_num_threads=1` + smaller BM25 corpus
   2. precompute **query** embeddings? No: queries are unknown. Instead drop dense retrieval on the hosted demo (BM25 + LLM rewrite only) and show that row in the table
   3. move the embedder to an API (e.g. a free embedding endpoint) ⚠️ only if it's no-card and allows the use

Ship the model files with the Docker image (download at build time from Hugging Face; don't commit `.onnx` files to git, they're in `.gitignore`).

Update `bootstrap._embedder`:

```python
def _embedder(settings: Settings) -> E5Embedder | OnnxE5Embedder:
    if settings.profile is Profile.HOSTED:
        return OnnxE5Embedder.load(settings.onnx_model_dir)
    return E5Embedder.load(settings.embed_model)
```

and move the `E5Embedder` import inside the non-hosted branch so `torch` is never imported on Render.

## Step 2 — Neon

1. Create a project in **AWS Asia Pacific (Singapore)**, Postgres 17 or 18, database `sahayak` 📚 (no card on the Free plan; compute scales to zero after 5 minutes 📚).
2. Copy the **pooled** connection string; add `?sslmode=require`.
3. From your Mac: `SAHAYAK_DATABASE_URL=<neon-url> uv run sahayak db migrate` → you should see `0002_bm25_paradedb.sql` **skipped** (no pg_search on Neon) and `0001`, `0003` applied.
4. Copy the RBI corpus (documents + chunks with embeddings) from local ParadeDB into Neon:
   ```bash
   docker compose exec -T db pg_dump -U sahayak --data-only -t documents -t chunks sahayak > /tmp/rbi.sql
   psql "<neon-url>" -f /tmp/rbi.sql
   ```
   ⚠️ The embeddings must come from **the same model weights** the hosted ONNX embedder uses (fp32 export ≈ same; int8 → re-embed passages with the ONNX model, or the query/passage spaces drift).
5. Check size: `select pg_size_pretty(pg_database_size('sahayak'));` (should be tens of MB; free storage per project is 0.5–1 GB ⚠️ check Neon's pricing page).

## Step 3 — Docker image

```dockerfile
# Dockerfile — hosted profile (no torch). Build: docker build -t sahayak .
FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app

FROM base AS builder
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra onnx
COPY src ./src
RUN uv sync --frozen --no-dev --extra onnx
# Model files: fetched at build time (pin a revision!) — see Step 1
COPY scripts/fetch_onnx_model.py ./scripts/
RUN uv run --no-dev python scripts/fetch_onnx_model.py models/e5-small-onnx

FROM base AS runtime
RUN useradd --create-home --uid 10001 app
COPY --from=builder --chown=app /app /app
USER app
ENV PATH="/app/.venv/bin:$PATH" SAHAYAK_PROFILE=hosted SAHAYAK_LOG_JSON=true
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["sh", "-c", "sahayak serve --host 0.0.0.0 --port ${PORT:-8000}"]
```

⚠️ Not built in the sandbox (no Docker daemon there): build it on your Mac (`docker build -t sahayak . && docker run --rm -p 8000:8000 --env-file .env.hosted sahayak`) and in CI (add a `docker build` job, no push). Check: the uv image tag `ghcr.io/astral-sh/uv:0.11` exists (uv's docs show this `COPY --from` pattern 📚), the image is < ~600 MB, and `python -c "import torch"` **fails** inside it.

## Step 4 — Render

```yaml
# render.yaml (Blueprint)
services:
  - type: web
    name: sarkari-sahayak
    runtime: docker
    plan: free
    region: singapore          # ⚠️ check Render's region list
    healthCheckPath: /health
    autoDeploy: false          # deploy from CI after tests pass (deploy hook)
    envVars:
      - key: SAHAYAK_PROFILE
        value: hosted
      - key: SAHAYAK_DATABASE_URL
        sync: false            # set in the dashboard (secret)
      - key: SAHAYAK_GROQ_API_KEY
        sync: false
      - key: SAHAYAK_GEMINI_API_KEY
        sync: false
      - key: SAHAYAK_AGENT_MODEL
        value: groq/openai/gpt-oss-20b
      - key: SAHAYAK_RATE_LIMIT_PER_MINUTE
        value: "6"
      - key: SAHAYAK_DAILY_REQUEST_BUDGET
        value: "300"           # well under Groq's 1,000 RPD free limit (each ask = 3–4 LLM calls)
```

⚠️ Verify the Blueprint field names against Render's docs, and that `SAHAYAK_FALLBACK_MODELS` parses as a JSON list (`'["gemini/<model>"]'`): pydantic-settings expects JSON for list fields.

Budget arithmetic: one `/v1/ask` = rewrite + grade (+ maybe rewrite + grade again) + generate = 3–5 LLM calls. Groq free: 1,000 requests/day and 8K tokens/min on `gpt-oss-20b` 📚. So 300 asks/day is the most you can safely promise, and the per-minute limit keeps you under the TPM cap.

Deploy: Render dashboard → New → Blueprint → select the repo. Then add a `deploy` job to CI that `curl`s the deploy hook (`RENDER_DEPLOY_HOOK_URL` secret) **after** `check` passes on `main`.

Smoke test after deploy (`tests/e2e/test_deployed.py`, marker `e2e`, run manually / nightly with `DEPLOYED_URL`): `/health` 200 within 90 s (cold start), MCP `list_tools` returns 3 tools, one Hindi `/v1/ask` returns citations or a refusal.

## Step 5 — Streamlit Community Cloud

* App file: `app/streamlit_app.py`; Python 3.13 in "Advanced settings"; secret `SAHAYAK_API_URL = "https://<render-app>.onrender.com"`.
* Dependencies: add `app/requirements.txt` with only what the UI needs (`streamlit`, `httpx`), so Cloud doesn't install torch. ⚠️ Check how Community Cloud chooses between `requirements.txt` and `pyproject.toml` when both exist (it looks for dependency files in the app's directory first, per its docs; verify).
* The UI reads secrets via env var; Streamlit Cloud exposes root-level secrets as environment variables ⚠️ verify, otherwise read `st.secrets` as a fallback.

## Step 6 — README (results first)

```markdown
# Sarkari Sahayak — सरकारी सहायक
Bilingual (Hindi/English) agentic-RAG MCP server over RBI Master Directions. Cites every answer — or refuses.

[▶ 2-min demo video] · [Live demo (free tier: first request may take ~1 min)] · [Eval reports]

## Results
| … retrieval table from docs/results/retrieval.md … |
| Refusal on out-of-corpus questions (NoMIRACL-hi non-relevant, n=…) | …% |
| Golden-set pass rate (n=…, local judge) | …% · judge agreement κ = … vs Gemini |
| Hosted latency p50 / p95 (warm) | … s / … s |

## How it works  (mermaid diagram + 5 bullets)
## Use it from Claude Desktop / Cursor  (config snippets)
## Reproduce  (make up → make ingest → make bench-quick → make test)
## Engineering  (TDD, coverage gates, CI, ADRs, cassettes, supply-chain pinning)
## Limitations  (small judge, hosted config is weaker, corpus is a subset, Hindi OCR errors, …)
## Acknowledgements & data sources  (RBI, MIRACL, NoMIRACL, IndicQA licences)
```

## Step 7 — Release

```bash
git switch main && git pull
# CHANGELOG: move Unreleased → [1.0.0] - 2026-xx-xx
git commit -am "chore(release): v1.0.0"   # via PR, as always
git tag -s v1.0.0 -m "v1.0.0" && git push --tags
gh release create v1.0.0 --generate-notes --title "Sarkari Sahayak v1.0.0"
```

## Definition of Done

- [ ] Live URLs in the repo "About" and README; cold-start note present
- [ ] Hosted-config benchmark row present; peak RSS recorded in ADR-0010
- [ ] Demo video #2 (2 min): Hindi question → cited answer; out-of-corpus → refusal; Claude Desktop using the MCP tools
- [ ] `v1.0.0` released; Projects board milestone closed

## Cursor prompt (S6)

> Read `docs/guide/sahayak/S6-ship.md`. Implement Step 1 test-first (`OnnxE5Embedder` with the fake tokenizer/session test), then write `scripts/fetch_onnx_model.py` that downloads a pinned revision with `huggingface_hub.snapshot_download`. Don't change any other module except `bootstrap._embedder`.
