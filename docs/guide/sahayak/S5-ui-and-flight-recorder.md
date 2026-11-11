# S5 — Streamlit UI + the Flight Recorder

**Goal:** a small bilingual UI, full tracing in Phoenix, persisted runs with 👍/👎 feedback, a versioned golden set built from real failures, and a CI gate that re-runs the golden set with a local LLM judge, plus a weekly judge-agreement job and a latency/cost report on GitHub Pages.
**Time:** ~12–14 h. **Branches:** `feat/s5-ui`, `feat/s5-tracing`, `feat/s5-runs`, `feat/s5-golden`, `feat/s5-eval-gate`, `feat/s5-report`.

## Issue text

> **S5: UI + Flight Recorder**
> - [ ] Streamlit app (AppTest unit tests + one Playwright e2e) handles answer / refusal / degraded / 429 / 503 / cold-start timeout
> - [ ] Phoenix traces every graph node and LLM call (OpenInference LangChain instrumentor)
> - [ ] `runs` table + `POST /v1/feedback`; `sahayak golden add <run_id>` appends to `evals/golden/golden.jsonl`
> - [ ] `evals/test_regression.py`: deterministic checks + DeepEval faithfulness with an Ollama judge; runs on PRs touching `agent/ llm/ prompts` or labelled `run-evals`
> - [ ] Weekly job: local judge vs Gemini judge agreement (Cohen's κ) → Pages report
> - [ ] Nightly job: latency p50/p95 and token usage per commit → Pages report

## Concept primers

> 📘 **Tracing (OpenTelemetry / OpenInference).** A *trace* is one request; *spans* are its steps (each LangGraph node, each LLM call) with inputs, outputs and timings. OpenInference is a set of OpenTelemetry conventions for LLM apps; Phoenix stores and visualises them. With `register(...)` + `LangChainInstrumentor().instrument(...)`, LangGraph nodes become spans automatically ✅ (packages installed and imported in the sandbox).

> 📘 **The Flight Recorder loop.** *Observe* (traces + runs) → *flag* (👎 or automatic rules) → *promote* (golden case with the expected behaviour) → *gate* (every PR re-runs the golden set). A bug you fixed once can never silently return. This is what "LLMOps maturity" means in practice.

> 📘 **LLM-as-judge and why we measure the judge.** Faithfulness ("is every claim supported by the retrieved context?") can't be checked with string matching, so a model judges it. Small judges are noisy, so we (1) keep deterministic checks separate (refused? cited the right document?), (2) use the judge only for the fuzzy part, and (3) **measure** the small judge against a stronger one with **Cohen's κ** (agreement corrected for chance; > 0.6 is usually called substantial). If κ is low, say so in the README. Honesty is the signal.

## Step 1 — Streamlit UI (TDD with AppTest + respx)

`tests/unit/ui/test_streamlit_app.py` ✅

```python
"""SE-17 / SE-19: UI behaviour with the API mocked (respx)."""

from pathlib import Path

import httpx
import pytest
import respx
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[3] / "app" / "streamlit_app.py")
ANSWER = {
    "run_id": "r1",
    "answer": "दस साल [MD-KYC#p1c0]",
    "citations": [{"chunk_id": "MD-KYC#p1c0", "text": "केवाईसी...", "source_url": ""}],
    "refused": False,
    "degraded": False,
    "latency_ms": 5,
}


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("SAHAYAK_API_URL", "http://api.test")
    return AppTest.from_file(APP, default_timeout=10).run()


@respx.mock
def test_shows_answer_and_citation_expander(app: AppTest) -> None:
    respx.post("http://api.test/v1/ask").mock(return_value=httpx.Response(200, json=ANSWER))
    app.text_input(key="question").input("केवाईसी?").run()
    app.button[0].click().run()
    assert not app.exception
    assert any("दस साल" in m.value for m in app.markdown)
    assert app.expander[0].label == "📄 MD-KYC#p1c0"


@respx.mock
def test_cold_start_timeout_shows_wake_up_message(app: AppTest) -> None:
    respx.post("http://api.test/v1/ask").mock(side_effect=httpx.ReadTimeout("slow"))
    app.text_input(key="question").input("केवाईसी?").run()
    app.button[0].click().run()
    assert "waking up" in app.warning[0].value


@respx.mock
def test_rate_limit_message(app: AppTest) -> None:
    respx.post("http://api.test/v1/ask").mock(
        return_value=httpx.Response(429, headers={"retry-after": "30"}, json={})
    )
    app.text_input(key="question").input("केवाईसी?").run()
    app.button[0].click().run()
    assert "30" in app.warning[0].value
```

`app/streamlit_app.py` ✅

```python
"""Sarkari Sahayak — Streamlit UI. Talks to the REST API only (never imports server code)."""

import os

import httpx
import streamlit as st

API_URL = os.environ.get("SAHAYAK_API_URL", "http://localhost:8000")
TIMEOUT = httpx.Timeout(90.0, connect=10.0)  # free-tier cold starts take ~1 minute

st.set_page_config(page_title="Sarkari Sahayak", page_icon="📜")
st.title("सरकारी सहायक · Sarkari Sahayak")
st.caption("RBI Master Directions से उत्तर — हर उत्तर स्रोत के साथ, या साफ़ इनकार।")

question = st.text_input("अपना प्रश्न लिखें / Ask a question", key="question", max_chars=1000)

if st.button("पूछें / Ask", type="primary", disabled=not question):
    with st.spinner("खोज रहे हैं… (free server may take ~1 min to wake up)"):
        try:
            resp = httpx.post(f"{API_URL}/v1/ask", json={"question": question}, timeout=TIMEOUT)
        except httpx.TimeoutException:
            st.warning("Server is waking up (free tier). Please try again in a few seconds.")
            st.stop()
    if resp.status_code == 429:
        st.warning(f"Too many requests. Retry after {resp.headers.get('retry-after', '60')} s.")
    elif resp.status_code == 503:
        st.warning(resp.json().get("detail", "Service temporarily unavailable."))
    elif resp.status_code != 200:
        st.error(f"Error {resp.status_code}")
    else:
        data = resp.json()
        st.session_state["last_run_id"] = data["run_id"]
        if data["refused"]:
            st.info(data["answer"])
        else:
            st.markdown(data["answer"])
        if data.get("degraded"):
            st.caption("⚠️ LLM unavailable — showing the most relevant passages instead.")
        for cite in data["citations"]:
            with st.expander(f"📄 {cite['chunk_id']}"):
                st.write(cite["text"])
                if cite.get("source_url"):
                    st.link_button("Source (rbi.org.in)", cite["source_url"])
```

Verified with Streamlit's `AppTest` ✅. Gotcha found: `st.write` inside the citation expander creates a *later* markdown element, so assert "any markdown contains the answer" rather than "the last one does".

Add a 👍/👎 pair after the answer that calls `POST /v1/feedback {"run_id", "value"}` (write the test first, like the others).

**Playwright e2e (SE-18), one test only.** Start the API with a FakeLLM-backed service on a port, start Streamlit with `SAHAYAK_API_URL` pointing at it (`streamlit run app/streamlit_app.py --server.headless true --server.port 8599`), then:

```python
# tests/e2e/test_ui_playwright.py  (marker: e2e; needs `uv run playwright install chromium` once)
from playwright.sync_api import Page, expect

def test_ask_and_see_citation(page: Page, ui_url: str) -> None:
    page.goto(ui_url)
    page.get_by_label("अपना प्रश्न लिखें / Ask a question").fill("केवाईसी?")
    page.get_by_role("button", name="पूछें / Ask").click()
    expect(page.get_by_text("MD-KYC#p1c0")).to_be_visible(timeout=20_000)
```

⚠️ Streamlit's DOM labels/roles can change between versions; if a locator fails, inspect with `uv run playwright codegen http://localhost:8599`.

## Step 2 — Tracing with Phoenix

```bash
make up TRACING=1            # starts Phoenix at http://localhost:6006 (stores in Postgres db "phoenix")
```

```python
# src/sahayak/flight/tracing.py
from openinference.instrumentation.langchain import LangChainInstrumentor
from phoenix.otel import register

def enable_tracing(endpoint: str = "http://localhost:6006/v1/traces",
                   project: str = "sarkari-sahayak") -> None:
    provider = register(project_name=project, endpoint=endpoint, batch=True,
                        set_global_tracer_provider=True)
    LangChainInstrumentor().instrument(tracer_provider=provider)
```

`register(...)` keyword names (`endpoint`, `project_name`, `batch`, `set_global_tracer_provider`, `auto_instrument`, `protocol`, …) were checked against `arize-phoenix-otel` 0.17.3 ✅. Call `enable_tracing()` in `serve` when `SAHAYAK_TRACING=true`. To link a run to its trace, read the current trace id inside the request (`opentelemetry.trace.get_current_span().get_span_context().trace_id`, formatted as 32 hex chars) and store it in `runs.trace_id` ⚠️ (verify that LangGraph's root span is active at that point; if not, create a parent span yourself with `tracer.start_as_current_span("ask")` in `SahayakService.ask`).

Also record LiteLLM token usage on the span (`gateway.usage`) so the cost report can sum it.

## Step 3 — Runs + feedback

`src/sahayak/store/migrations/0003_runs.sql` ✅

```sql
-- Flight Recorder: every /v1/ask run, with the user's feedback and the Phoenix trace id.
CREATE TABLE IF NOT EXISTS runs (
    run_id      text PRIMARY KEY,
    question    text NOT NULL,
    answer      text NOT NULL,
    refused     boolean NOT NULL,
    degraded    boolean NOT NULL DEFAULT false,
    citations   jsonb NOT NULL DEFAULT '[]'::jsonb,   -- list of chunk_ids
    model       text,
    trace_id    text,
    latency_ms  int NOT NULL,
    feedback    smallint CHECK (feedback IN (-1, 0, 1)),
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS runs_feedback_idx ON runs (feedback) WHERE feedback = -1;
```

`src/sahayak/flight/runs.py` ✅

```python
"""Persist runs and feedback so failures can be promoted into the golden set."""

from typing import Any, Literal

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class RunStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def record(
        self,
        *,
        run_id: str,
        question: str,
        answer: str,
        refused: bool,
        degraded: bool,
        citations: list[str],
        latency_ms: int,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO runs (run_id, question, answer, refused, degraded, citations,
                                 latency_ms, model, trace_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                run_id,
                question,
                answer,
                refused,
                degraded,
                Jsonb(citations),
                latency_ms,
                model,
                trace_id,
            ),
        )
        self.conn.commit()

    def set_feedback(self, run_id: str, value: Literal[-1, 0, 1], note: str | None = None) -> bool:
        cur = self.conn.execute(
            "UPDATE runs SET feedback = %s, note = %s WHERE run_id = %s", (value, note, run_id)
        )
        self.conn.commit()
        return cur.rowcount == 1

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            return cur.execute("SELECT * FROM runs WHERE run_id = %s", (run_id,)).fetchone()

    def flagged(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(
                "SELECT * FROM runs WHERE feedback = -1 ORDER BY created_at DESC LIMIT %s",
                (limit,),
            ).fetchall()
```

`tests/integration/test_runs.py` ✅

```python
import pytest

from sahayak.flight.runs import RunStore

pytestmark = pytest.mark.integration


def test_record_feedback_and_flagged(conn) -> None:  # type: ignore[no-untyped-def]
    conn.execute("TRUNCATE runs")
    store = RunStore(conn)
    store.record(
        run_id="r1",
        question="आज मौसम?",
        answer="माफ़ कीजिए",
        refused=True,
        degraded=False,
        citations=[],
        latency_ms=12,
        trace_id="t1",
    )
    assert store.set_feedback("r1", -1, "should refuse in Hindi — ok actually")
    assert not store.set_feedback("missing", -1)
    row = store.get("r1")
    assert row is not None
    assert row["feedback"] == -1
    assert row["citations"] == []
    assert [r["run_id"] for r in store.flagged()] == ["r1"]
```

Verified on real Postgres ✅. Wire it in: `SahayakService.ask` → `RunStore.record(...)` (inject `RunStore` as an optional dependency so unit tests don't need a DB), and add

```python
class Feedback(BaseModel):
    run_id: str
    value: Literal[-1, 1]
    note: Annotated[str | None, Field(max_length=500)] = None

@app.post("/v1/feedback", status_code=204)
def feedback(fb: Feedback) -> None:
    if not runs.set_feedback(fb.run_id, fb.value, fb.note):
        raise HTTPException(404, "unknown run_id")
```

Never store IP addresses or user identities in `runs` (privacy by design).

## Step 4 — The golden set

`tests/unit/flight/test_golden.py` ✅

```python
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from sahayak.flight.golden import GoldenCase, append_case, load_cases, next_id


def case(i: str, run: str | None = None) -> GoldenCase:
    return GoldenCase(
        id=i,
        question="आज मौसम?",
        lang="hi",
        expect="refuse",
        source_run_id=run,
        added_on=date(2026, 11, 10),
    )


def test_append_and_load_roundtrip_keeps_devanagari(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    append_case(path, case("G0001", "r1"))
    append_case(path, case("G0002"))
    assert [c.id for c in load_cases(path)] == ["G0001", "G0002"]
    assert "आज मौसम" in path.read_text(encoding="utf-8")  # not \\u-escaped
    assert next_id(load_cases(path)) == "G0003"


def test_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "golden.jsonl"
    append_case(path, case("G0001", "r1"))
    with pytest.raises(ValueError, match="duplicate"):
        append_case(path, case("G0001"))
    with pytest.raises(ValueError, match="already in the golden set"):
        append_case(path, case("G0002", "r1"))


def test_schema_validation() -> None:
    with pytest.raises(ValidationError):
        GoldenCase(id="X1", question="q?", lang="hi", expect="refuse", added_on=date.today())
    assert load_cases(Path("does-not-exist.jsonl")) == []
    assert next_id([]) == "G0001"
```

> ✋ **Try it yourself first.** You have the failing tests above. Spend 30–45 minutes making them pass on your own before reading the reference implementation below. Then compare: what did you do differently, and why?

`src/sahayak/flight/golden.py` ✅

```python
"""The golden set: a versioned JSONL file of cases that must keep passing (Flight Recorder)."""

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class GoldenCase(BaseModel):
    id: str = Field(pattern=r"^G\d{4}$")  # G0001, G0002, ...
    question: str = Field(min_length=2)
    lang: Literal["hi", "en", "hinglish"]
    expect: Literal["answer", "refuse"]
    must_cite_doc_ids: list[str] = Field(default_factory=list)  # any one of these must be cited
    reference_answer: str | None = None
    source_run_id: str | None = None  # the flagged production run this came from
    failure_mode: str | None = None  # e.g. "wrong_refusal", "uncited_claim", "wrong_language"
    added_on: date


def load_cases(path: Path) -> list[GoldenCase]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [GoldenCase.model_validate_json(line) for line in lines if line.strip()]


def next_id(cases: list[GoldenCase]) -> str:
    return f"G{max((int(c.id[1:]) for c in cases), default=0) + 1:04d}"


def append_case(path: Path, case: GoldenCase) -> None:
    cases = load_cases(path)
    if any(c.id == case.id for c in cases):
        msg = f"duplicate golden id {case.id}"
        raise ValueError(msg)
    if case.source_run_id and any(c.source_run_id == case.source_run_id for c in cases):
        msg = f"run {case.source_run_id} is already in the golden set"
        raise ValueError(msg)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(case.model_dump_json(exclude_none=True) + "\n")
```

Workflow:

```bash
uv run sahayak golden add 3f2a… --expect refuse --failure-mode wrong_answer_out_of_corpus
uv run sahayak golden add 9b7c… --expect answer --must-cite MD-KYC-2016-HI --failure-mode wrong_language
git add evals/golden/golden.jsonl && git commit -m "test(evals): add G0007 from run 9b7c (wrong language)"
```

Seed the file with ~20 hand-written cases before you have real failures: 8 Hindi, 6 English, 4 Hinglish answerable questions over your RBI corpus, plus ~10 out-of-corpus questions that must be refused. Grow it to 30–50 from flagged runs.

## Step 5 — The regression gate (DeepEval + Ollama judge)

```python
# evals/test_regression.py
"""Golden-set regression gate. Run: uv run pytest evals -m llm -p deepeval"""
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.models import OllamaModel
from deepeval.test_case import LLMTestCase

from sahayak.bootstrap import build_service
from sahayak.config import get_settings
from sahayak.flight.golden import load_cases

CASES = load_cases(Path("evals/golden/golden.jsonl"))
JUDGE = OllamaModel(model="qwen3:4b-instruct", base_url="http://localhost:11434", temperature=0)


@pytest.fixture(scope="session")
def service():
    return build_service(get_settings())


@pytest.mark.llm
@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_golden(case, service) -> None:
    result = service.ask(case.question)
    # 1) deterministic checks — no judge involved
    assert result.refused == (case.expect == "refuse"), result.answer
    if case.expect == "refuse":
        return
    cited_docs = {c.doc_id for c in result.citations}
    if case.must_cite_doc_ids:
        assert cited_docs & set(case.must_cite_doc_ids), cited_docs
    # 2) fuzzy check — local judge
    test_case = LLMTestCase(input=case.question, actual_output=result.answer,
                            retrieval_context=[c.text for c in result.citations])
    assert_test(test_case, [FaithfulnessMetric(threshold=0.7, model=JUDGE, async_mode=False)])
```

`OllamaModel(model=, base_url=, temperature=)`, `FaithfulnessMetric(threshold=, model=, async_mode=, …)`, `LLMTestCase(input, actual_output, retrieval_context, …)` and `assert_test(test_case, metrics)` were checked against DeepEval 4.3.3 ✅. The CLI alternative `deepeval set-ollama` also exists ✅. ⚠️ Not executed end-to-end in the sandbox (no Ollama there): run it locally first and expect to tune the threshold.

**CI workflow** (`.github/workflows/evals.yml`), triggered on PRs that touch `src/sahayak/agent/**`, `src/sahayak/llm/**`, `evals/golden/**`, or carry the `run-evals` label, plus nightly:

```yaml
name: evals
on:
  pull_request:
    types: [opened, synchronize, labeled]
    paths: ["src/sahayak/agent/**", "src/sahayak/llm/**", "evals/**"]
  schedule: [{ cron: "30 21 * * *" }]     # 03:00 IST
  workflow_dispatch:
permissions: { contents: read }
jobs:
  golden:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    services:
      db:
        image: paradedb/paradedb:latest-pg18     # same pinned tag as docker-compose.yml
        env:
          POSTGRES_USER: sahayak
          POSTGRES_PASSWORD: sahayak
          POSTGRES_DB: sahayak
        ports: ["5432:5432"]
        options: >-
          --shm-size=1g --health-cmd "pg_isready -U sahayak" --health-interval 5s --health-retries 20
    env:
      SAHAYAK_DATABASE_URL: postgresql://sahayak:sahayak@localhost:5432/sahayak
      SAHAYAK_PROFILE: ci
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v7
        with: { enable-cache: true }
      - uses: actions/cache@v4
        with: { path: ~/.ollama/models, key: cache-ollama-qwen3-4b-instruct }
      - name: Install and start Ollama
        run: |
          curl -fsSL https://ollama.com/install.sh | sh
          (ollama serve > /tmp/ollama.log 2>&1 &)
          sleep 5 && ollama pull qwen3:4b-instruct
      - run: uv sync --all-extras --group dev
      - run: uv run sahayak db migrate && uv run python -m evals.seed_ci_corpus   # small fixture corpus
      - run: uv run pytest evals -m llm -p deepeval -q
```

GitHub's public-repo runners have 4 vCPU / 16 GB RAM and no GPU 📚, so a 4B model runs on CPU: keep the gate to ~30–50 cases and expect 10–30 minutes ⚠️ measure. The `ollama.com/install.sh` script is Ollama's documented Linux installer 📚; the `~/.ollama/models` cache path applies when Ollama runs as your user (the installer may set it up as a system service with a different model directory; check with `ollama show --modelfile` or the service config, and adjust the cache path) ⚠️. `evals/seed_ci_corpus.py` ingests your **synthetic** fixture corpus (`tests/fixtures/corpus/`) so CI never downloads RBI PDFs. Golden questions used in CI must be answerable from that fixture corpus; keep real-RBI golden cases in a second file (`golden.rbi.jsonl`) run only locally/nightly on your Mac.

## Step 6 — Judge agreement (weekly)

`evals/agreement.py` ✅

```python
"""Judge-agreement statistics."""

from collections.abc import Sequence


def cohens_kappa(a: Sequence[bool], b: Sequence[bool]) -> float:
    """Cohen's kappa for two binary raters. 1 = perfect agreement, 0 = chance level."""
    if len(a) != len(b) or not a:
        msg = "need two non-empty label lists of equal length"
        raise ValueError(msg)
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1 - expected)
```

Job: sample 40 (question, answer, context) triples from the golden run, score faithfulness pass/fail with the local judge and with Gemini (`GeminiModel` or LiteLLM via a custom `DeepEvalBaseLLM` ⚠️ check DeepEval's Gemini integration), compute κ and raw agreement, append to `docs/results/judge-agreement.json`. Gemini runs only on a schedule with the `GEMINI_API_KEY` secret (never on fork PRs), and only on synthetic/public content.

## Step 7 — Reports on GitHub Pages

`evals/report.py` turns `docs/results/*.json` into a static `site/index.html` (a table per metric + a simple line chart per commit, e.g. using Chart.js from a CDN). Publish with a dedicated workflow:

```yaml
# .github/workflows/pages.yml
name: pages
on:
  push:
    branches: [main]
    paths: ["docs/results/**", "evals/report.py"]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: astral-sh/setup-uv@v7
      - run: uv run --no-project --with jinja2 python evals/report.py --out site
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

⚠️ Action major versions: check the current ones on GitHub Marketplace; Dependabot will keep them updated.

## Definition of Done

- [ ] Demo video #1 (60–90 s): a prompt change makes CI red on a golden case → open the trace in Phoenix → fix → green
- [ ] Golden set ≥ 30 cases with `failure_mode` labels; the README shows counts per failure mode
- [ ] Judge-agreement number in the README, whatever it is
- [ ] Pages report live

## Cursor prompt (S5)

> Read `docs/guide/sahayak/S5-ui-and-flight-recorder.md`. Implement Step 3 (runs + feedback): migration, `RunStore`, the integration test, then inject an optional `RunStore` into `SahayakService.ask` with a unit test using an in-memory fake, then add `POST /v1/feedback` test-first.
