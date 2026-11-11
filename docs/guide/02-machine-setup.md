# 02 — Machine Setup (MacBook M1, 8 GB, macOS)

Time: ~2 hours (mostly downloads). Do this once. Each step ends with a **verify** command — don't continue until it passes.

## 0. RAM discipline on 8 GB (read first)

| Running | Approx. RAM |
|---|---|
| macOS + Cursor + 3–4 browser tabs | 3–4 GB |
| OrbStack + ParadeDB + Phoenix | ~0.8–1 GB (with the limit below) |
| Ollama + `qwen3:4b-instruct` loaded | ~2.5–3 GB |
| Python app + e5-small | ~0.5 GB |

Rules of thumb:
* Close Chrome tabs when running evals. Watch **Activity Monitor → Memory → Memory Pressure**; yellow is OK, red means swap (10× slower).
* Ollama unloads idle models after a few minutes; force it with `ollama stop <model>`.
* Never run bge-m3 + reranker + an LLM at the same time. Benchmark scripts load one model at a time.

## 1. Command-line basics

```bash
xcode-select --install          # Apple command line tools (git, compilers)
# Homebrew (https://brew.sh) — follow the official one-liner on the site, then:
brew --version
```

## 2. Core tools via Homebrew

```bash
brew install git gh jq make
brew install --cask orbstack            # Docker engine replacement (free for personal use)
brew install tesseract tesseract-lang   # OCR engine + language packs (incl. hin, mar) ⚠️ verify formula names
brew install node                       # for promptfoo (npx) and mcp-remote
brew install pre-commit gitleaks
```

Verify:

```bash
git --version && gh --version && docker version && node --version
tesseract --list-langs | grep -E '^(hin|mar|eng)$'   # must print hin, mar, eng
```

> If `hin`/`mar` are missing: `brew info tesseract-lang` shows where traineddata lives; you can also download `hin.traineddata`/`mar.traineddata` from the `tesseract-ocr/tessdata_best` GitHub repo into `$(brew --prefix)/share/tessdata/`.

### OrbStack setup

1. Open OrbStack once (menu bar icon). If Docker Desktop is installed, quit it and let OrbStack take over the `docker` context:
   ```bash
   docker context show        # should print: orbstack
   ```
2. OrbStack → Settings → System → **Memory limit ≈ 2.5 GB**, CPU limit 4. 📚 (docs.orbstack.dev/settings)
3. Verify host networking used by our containers:
   ```bash
   docker run --rm curlimages/curl -s http://host.docker.internal:11434/api/version || echo "start Ollama first"
   ```

## 3. uv + Python 3.13

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # official installer
uv --version                 # ≥ 0.11
uv python install 3.13
uv python list | grep 3.13
```

Never use `pip install` globally. Every project uses `uv sync` / `uv add` / `uv run`.

## 4. Ollama (native — for the Metal GPU)

Install the macOS app from ollama.com (or `brew install ollama && brew services start ollama`), then:

```bash
ollama --version
ollama pull qwen3:4b-instruct      # ~2.5 GB — main agent + judge   ⚠️ confirm tag on ollama.com/library
ollama pull gemma3:4b              # ~3 GB — comparison model
# later, only when needed (≈5 GB): ollama pull qwen3:8b
ollama run qwen3:4b-instruct "सिर्फ़ एक वाक्य में बताइए: KYC क्या है?"
curl -s http://localhost:11434/api/tags | jq '.models[].name'
```

Disk budget: models ~6–11 GB, MIRACL-hi corpus ~1.8 GB download 📚, embeddings/indexes ~3–6 GB, Docker images ~2 GB, venvs ~4 GB (torch). Keep **≥ 15 GB free** at all times.

## 5. Hugging Face account (free, no card)

MIRACL topics/qrels are downloaded from Hugging Face; some MIRACL repos ask you to accept terms/log in.

```bash
uv tool install "huggingface_hub[cli]"
hf auth login        # paste a READ token from huggingface.co/settings/tokens  ⚠️ CLI name may be `huggingface-cli` on older versions
```

## 6. Editors & clients

* **Cursor** — install, sign in, install extensions: Python, Ruff, even-better-toml, Docker, Mermaid preview.
  Settings → enable "Format on save" with Ruff as the Python formatter.
* **Claude Desktop** — used in S4 to connect to your local MCP server.
  Config file: `~/Library/Application Support/Claude/claude_desktop_config.json` 📚.
* **TablePlus / DBeaver** (optional) or just `psql` inside the container.

## 7. Accounts you will need (all free, no card)

| Account | Needed in | Notes |
|---|---|---|
| GitHub (existing) | Phase 0 | Enable 2FA. |
| Hugging Face | S2 | Read token. |
| Groq | S3 | console.groq.com → API key. Free plan, no card 📚. |
| Google AI Studio | S3/S5 | API key; pick a Flash model from your model list ⚠️. Never send personal data. |
| Neon | S6 | Choose region **AWS Asia Pacific (Singapore)**. |
| Render | S6 | Sign in with GitHub. Card not required per Render ⚠️ (one aggregator disagrees — if asked for a card, stop and tell me). |
| Streamlit Community Cloud | S6 | Sign in with GitHub. |
| PyPI + TestPyPI | G4 | Enable 2FA; use Trusted Publishing (no tokens). |

Store keys **only** in a password manager and in `.env` (gitignored) / GitHub Actions secrets / Render env vars.

## 8. Shell quality-of-life (optional)

```bash
# ~/.zshrc
export OLLAMA_KEEP_ALIVE=5m        # unload idle models sooner (default behaviour may differ ⚠️)
alias dc='docker compose'
alias ur='uv run'
```

## Done when

- [ ] `docker context show` → `orbstack`
- [ ] `uv python list` shows 3.13
- [ ] `ollama run qwen3:4b-instruct` answers in Hindi
- [ ] `tesseract --list-langs` includes `hin`, `mar`
- [ ] `gh auth status` → logged in (next file sets this up properly)
