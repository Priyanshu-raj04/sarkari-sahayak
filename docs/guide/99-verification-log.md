# 99 — Verification Log (grounding check)

Date of checks: **2026-11-09 / 2026-11-10**. Sources compared:
* **[R0]** your original report *"Free, Fork-and-Extend AI Engineer Portfolio"* (Oct 2026)
* **[R1]** the research report run in this conversation (*"Verified Stack Facts and Required Changes, November 2026"*)
* **[S]** my own sandbox runs (packages installed at the stated versions, code executed, tests run)
* **[W]** web/doc lookups made while writing (official docs, PyPI, schemas)

Legend: ✅ confirmed · 🔁 corrected (guide uses the corrected version) · ⚠️ unverified (the guide tells you how to check) · ⛔ not used by the plan anymore.

## A. Claims from the original report [R0], re-checked

| # | [R0] claim | Status | Evidence | Where it matters |
|---|---|---|---|---|
| 1 | MIRACL Hindi: 506,264 passages, 350 dev queries | ✅ | [W] MIRACL dataset card/paper: hi dev 350 queries, 3,494 judgments; corpus in 2 shards | S2 |
| 2 | multilingual-e5-small ~118M params, 384-d, needs `query:`/`passage:` prefixes | ✅ | [W] model card; prefixes enforced by our unit test [S] | S2, S6 |
| 3 | bge-m3: 568M, 1024-d, dense+sparse+ColBERT, MIT | ✅ | [W] model card; sparse via `BGEM3FlagModel.encode(return_sparse=True)` | S2 (optional) |
| 4 | Streamlit Cloud 690 MB–2.7 GB, sleeps after 12 h | ✅ | [R1] Streamlit docs | S6 |
| 5 | Render free 512 MB / 0.1 CPU, 15-min spin-down, 750 h/month, no card | ✅ (card: secondary sources) | [R1] | S6 |
| 6 | Groq free 30 RPM / 1K RPD / 8K TPM / 200K TPD | 🔁 true for `gpt-oss-20b/120b` and `qwen3.8-27b`; Llama 3.x no longer listed | [R1] Groq console | S6 budget maths |
| 7 | HF Gradio/Docker Spaces need a paid plan since July 2026 | ✅ | [R1] | ⛔ we don't use Spaces |
| 8 | Gemini free limits no longer published; free-tier data may be used by Google | ✅ (exact month unverified) | [R1] | S3/S5: no personal data to Gemini |
| 9 | OpenRouter 50 free requests/day until $10 credit | ✅ | [R1] | ⛔ not used |
| 10 | Supabase pauses after 1 week; Qdrant suspends/deletes | ⚠️ not re-verified | — | ⛔ replaced by Neon |
| 11 | promptfoo joined OpenAI (Mar 2026), stays open source | ✅ (announced 9 Mar 2026) | [R1] | G4 |
| 12 | Use FastMCP `as_proxy()` for the firewall | 🔁 removed in FastMCP 3.0 → `fastmcp.server.create_proxy()` | [R1] + [S] ran it on 4.1.6 | G3, G5 |
| 13 | MCP SDK 2.x renamed `FastMCP` → `MCPServer`, stateless 2026-07-28 spec | ✅ | [R1]; [S] `mcp` 2.3.0 installed under FastMCP 4.1.6 | S4 |
| 14 | fr2endly/mcp-scan (SARIF, `--fail-on`) as a base scanner | 🔁 not verified as maintained; replaced by Cisco `mcp-scanner` (offline) + optional Snyk Agent Scan; we emit our own SARIF | [R1] | G1 |
| 15 | Invariant mcp-scan → Snyk Agent Scan | ✅ + caveat: sends descriptions to Snyk, CI mode executes server commands | [R1] | G1 (sandbox it) |
| 16 | `PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true` + `ollama:chat:` is enough for local-only | 🔁 also need `PROMPTFOO_DISABLE_REMOTE_GENERATION`, telemetry off; some plugins remote-only | [R1] + [W] | G4 |
| 17 | DeepEval agent/MCP metrics; Ollama judge via `deepeval set-ollama` | ✅ | [S] DeepEval 4.3.3: `OllamaModel`, `FaithfulnessMetric`, `LLMTestCase` (has `mcp_*` fields), `assert_test`, `set-ollama` CLI | S5 |
| 18 | Phoenix + OpenInference LangGraph instrumentation | ✅ | [S] `arize-phoenix-otel` 0.17.3 `register(...)` signature, `LangChainInstrumentor` import | S5 |
| 19 | pgvector (or SQLite / Qdrant) locally | 🔁 ParadeDB (Postgres + pg_search BM25 + pgvector) locally by your decision | [W] ParadeDB docs (syntax), [S] pgvector SQL ran | S1–S2 |
| 20 | "Small judges produce malformed JSON; use JSON mode + retries" | ✅ | [S] gateway + judge implement parse-tolerance and one repair turn; tested | S3, G2 |
| 21 | MTEB leaderboard averaging caveat | ✅ advice kept: we report retrieval-only metrics on named datasets | [R0] | S2 |
| 22 | τ-bench 2.0 / Bharat-τ | ⛔ project dropped | — | — |
| 23 | Fork-and-extend framing | 🔁 both projects are built from scratch; no forks | your decision | all |

## B. Claims from the research report [R1] that the guide depends on

| # | [R1] claim | Status | Evidence / note |
|---|---|---|---|
| 1 | Neon removed `pg_search` (new projects Mar 2026, existing Sep 2026); replacement `lakebase_text` | ✅ (trusted from [R1], Neon docs cited) | Guide: hosted BM25 = bm25s in-process; ParadeDB local only; migration `0002` auto-skips where `pg_search` is missing ([S] skip verified on plain Postgres) |
| 2 | LiteLLM malicious releases (1.82.7/1.82.8 Mar 2026; 1.107.0 Oct 2026) | ✅ (trusted) | `litellm==1.108.3` installs and works [S]; exact pin + hash lock + Dependabot ignore |
| 3 | FastMCP 4.x (latest 4.1.6) on MCP SDK 2.3.0 | ✅ | [S] installed both; all MCP code ran |
| 4 | `create_proxy` + `Middleware.on_list_tools / on_call_tool` | ✅ | [S] 5 proxy tests + HTTP dogfood test pass |
| 5 | FastMCP #5652: listing runs before every HTTP tool call | ⚠️ not reproduced; design is safe either way (`on_list_tools` is cheap) | G3 note |
| 6 | Cisco `mcp-scanner` offline YARA/static on saved tools JSON | ⚠️ CLI flags/format from [R1], not executed | G1 says check `--help` |
| 7 | MCPTox: 45 servers, 353 tools; case counts conflict (1,312 / 1,348 / 1,497) | ✅ conflict surfaced in G1 | cite the version you download |
| 8 | pg_search 0.26.5, AGPL-3.0; pgvector 0.8.7 | ✅ (trusted) | ParadeDB query syntax re-checked in docs [W]: `USING paradedb`, `(col::pdb.icu)`, `|||`, `pdb.score()`, `key_field` deprecated |
| 9 | Groq free model table | ✅ (trusted) | S6 budget = 300 asks/day |
| 10 | Neon Free: no card, scale-to-zero 5 min, 100 CU-h; storage 0.5 vs 1 GB conflict | ✅ / ⚠️ storage | we need < 100 MB |
| 11 | Presidio India recognizers exist | ✅ [S] imports; disabled by default since 2.2.359 [W] | optional comparison in G3 |
| 12 | Gemini free tier: data may be used for product improvement outside EEA/UK/CH | ✅ (trusted) | no personal data to Gemini; only scheduled judge job on synthetic content |

## C. Facts I verified independently while writing [S]/[W]

| Fact | How |
|---|---|
| Python `re` `\w` splits Devanagari words; `regex` `[\p{L}\p{M}\p{N}]+` doesn't | ran it; pinned by a test |
| NFC turns precomposed क़ (U+0958) into क + nukta (composition exclusion) | test initially failed → corrected and documented |
| bm25s 0.3.16 + our tokenizer retrieves Hindi correctly | unit tests |
| LangGraph 1.2.20 `StateGraph`, conditional edges, `START`/`END` | graph tests (7 paths) |
| FastMCP 4.1.6: structured output, `Annotated[Field]` validation, resource templates, `http_app(stateless_http=True)` mounted in FastAPI with `lifespan`, `custom_route`, `find_available_port` in `fastmcp.utilities.http`, `ToolResult` in `fastmcp.tools` | unit + e2e tests over real uvicorn |
| Redacting only `content` leaks PII through `structured_content` | test caught it; middleware redacts both |
| Verhoeff implementation correct (`check_digit("236") == "3"`) | known test vector |
| SARIF output valid | validated against the official OASIS 2.1.0 JSON schema |
| GitHub workflow / action / Dependabot files valid | `check-jsonschema` built-in schemas (ci ×2, evals, pages, release, mcp-security, action.yml, dependabot) |
| promptfoo config valid | validated against promptfoo's published config schema (caught missing `prompts`) |
| pgvector SQL, migrations, repository, runs table | ran against a real PostgreSQL with pgvector (embedded server) |
| Streamlit UI behaviour | `streamlit.testing.v1.AppTest` + respx |
| Gatekeeper wheel + console script | `uv build`, `uvx --from <wheel> gatekeeper …` |
| PyPI name `mcp-gatekeeper` already taken | PyPI JSON API → 200 (unrelated "quality gate" project) → we use `mcp-tool-gatekeeper` (404 = free at check time) |

## D. Bugs the verification caught (and the guide now avoids)

1. Typer collapses a single command into the root → `sahayak version` failed → added `@app.callback()`.
2. Makefile help regex missed `test-e2e` (digits) → fixed.
3. pytest honours only the last `-m` → combined marker expressions.
4. The autouse env-isolation fixture deleted `SAHAYAK_TEST_DATABASE_URL` → integration tests silently **skipped** → renamed to `TEST_DATABASE_URL`, and CI now fails instead of skipping.
5. Splitting unit and integration into two CI jobs hid DB code from the coverage gate → merged into one `check` job.
6. DeepEval's pytest plugin added ~35 s to every test run → `-p no:deepeval` by default.
7. Gatekeeper reported a rug pull as "unpinned" instead of "drift" → use the status recorded during listing.
8. Output redaction initially only covered text content → now also structured content.
9. LLM call inside a LangGraph router (invisible in traces) → moved into a `grade` node.
10. `\uXXXX` escapes can be turned into invisible characters by tooling → named `\N{...}` escapes.
11. S5 Pages snippet was invalid YAML → replaced with a complete, schema-valid workflow.

## E. Open items you must verify yourself (all marked ⚠️ in the guide)

| Item | Milestone | How |
|---|---|---|
| RBI Master Directions URLs, Hindi pairing, robots.txt/terms, font encoding of Hindi PDFs | S1 | spike, recorded in `docs/data-sources.md` |
| Exact MIRACL/NoMIRACL/IndicQA file paths and split names on Hugging Face | S2 | list repo files before writing loaders |
| Ollama tag for Qwen3-4B *instruct* | Phase 0 | ollama.com/library/qwen3 tags |
| ParadeDB / Phoenix Docker tags; ParadeDB BM25 + ICU on Hindi | Phase 0 / S1 | Docker Hub; `test_paradedb_bm25_with_icu_tokenizer` |
| Real OCR quality on legacy-font Hindi PDFs | S1 | one real PDF |
| Reranker + bge-m3 behaviour and speed on the M1 | S2 | slow tests + timing |
| VCR capture of LiteLLM→Ollama traffic | S3 | record one cassette; else gateway-level cassette |
| Cursor `mcp.json` format; Claude Desktop stdio logging to stderr | S4 | try both clients |
| Ollama install/caching on GitHub runners; eval-gate runtime | S5 | first workflow run |
| Trace-id capture inside LangGraph | S5 | Phoenix UI |
| ONNX export flags, parity, peak RSS < 450 MB | S6 | spike |
| Dockerfile build; `uv` image tag; Render Blueprint fields & region; Streamlit Cloud dependency resolution | S6 | build + first deploy |
| Supersession wording in RBI documents; Maharashtra GR portal terms | S7 | collect 20 real examples first |
| Cisco scanner CLI/output; MCPTox licence | G1 | `--help`, repo LICENSE |
| promptfoo plugins that work fully locally | G4 | first run |
| PyPI name still free; Marketplace publishing flow | G4 | right before release |

**Bottom line:** every piece of code in this guide marked ✅ was executed. Every version, limit and API it depends on was confirmed by [R1], [W] or [S], or is listed above as something to check, with a fallback. Two [R0] recommendations were factually outdated (Neon BM25, `as_proxy()`), plus one naming collision on PyPI; the guide uses the corrected versions.
