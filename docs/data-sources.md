# Data sources

Checked: **2026-11-11**.

## Summary table

| Source | URL | Licence / terms | Date checked | Findings |
|---|---|---|---|---|
| RBI Master Directions (EN) | https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx | Public regulatory text; reuse terms not fully verified — we never re-host PDFs | 2026-11-11 | Listing is the SoT index. Individual MDs expose a PDF on `rbidocs.rbi.org.in` (e.g. KYC CB → `…/PDFs/169MD.PDF`). |
| RBI Master Directions (HI) | https://www.rbi.org.in/Hindi/scripts/MasterDirections.aspx | Same | 2026-11-11 | Hindi is often **Unicode HTML** (not a PDF). Devanagari text layer is real Unicode on sampled pages. |
| RBI robots.txt | https://www.rbi.org.in/robots.txt | n/a | 2026-11-11 | Browser GET returned **“Unauthorised Access”** (WAF). Automated `curl` from this machine was blocked (proxy/403). Treat bulk scripted download as **not clearly permitted**; prefer polite downloader only when a fetch is allowed, else **manual** PDF save into `data/raw/`. |
| RBI Disclaimer / terms | Footer “Disclaimer” on rbi.org.in | Site terms | 2026-11-11 | Disclaimer link present site-wide; content pages are behind CMS paths that change. Conservative rule: **do not re-host**, cite + deep-link to rbi.org.in / rbidocs only. |
| MIRACL-hi topics/qrels | https://huggingface.co/datasets/miracl/miracl | Research / dataset card | 2026-11-11 | Local only; never re-host. Paths below. |
| MIRACL-hi corpus | https://huggingface.co/datasets/miracl/miracl-corpus | Research / dataset card | 2026-11-11 | `docs-*.jsonl.gz` shards; full 506K overnight embed. |
| IndicQARetrieval hi | https://huggingface.co/datasets/mteb/IndicQARetrieval | CC0-1.0 (dataset card) | 2026-11-11 | Configs `hi-corpus` / `hi-queries` / `hi-qrels`, split `test`. |
| NoMIRACL | https://huggingface.co/datasets/miracl/nomiracl | Research / dataset card | 2026-11-11 | Verify `relevant` / `non_relevant` split names before live use (S3 refusal). |

## How RBI publishes EN / HI

1. **English:** Notifications → Master Directions listing. Each direction page includes a size link (e.g. “701 kb”) pointing at a PDF under `https://rbidocs.rbi.org.in/rdocs/notification/PDFs/…`.
2. **Hindi:** parallel listing under `/Hindi/scripts/MasterDirections.aspx?ID=…`. Many entries are **HTML bodies with Unicode Devanagari**; PDF attachments are uncommon.
3. **Entity split (2025+):** KYC / Outsourcing / Deposits etc. are now per regulated-entity family (Commercial Banks, NBFC, …). Hindi often still has the older consolidated instrument (e.g. KYC Direction, 2016). Manifest `pair_doc_id` links the closest bilingual counterparts and notes version skew in the title when needed.

## Corpus selection (~30 EN/HI pairs)

**Curated must-haves** (fintech / NBFC / banking demo story): KYC, Digital Lending, Fraud Risk Management, Outsourcing (IT + managing risks), Interest Rate on Deposits, PPI, Payment Aggregator, Digital Payment Security / Cyber Resilience, MSME lending, Priority Sector Lending, Co-Lending, Account Aggregator, Scale-Based NBFC, Credit Information, Cards, Governance / Digital Banking, Internal Ombudsman, LRS, Deposits & Accounts (FEMA), P2P.

**Fill from listing:** Commercial Banks + NBFC + payment-system directions that still have a usable Hindi page.

Full rows: [`data_manifest/rbi_manifest.csv`](../data_manifest/rbi_manifest.csv) (URLs + empty `sha256` until first successful download). **No PDFs in git.**

## Hindi text-layer spot check (3 pages)

| Doc | Check | Result |
|---|---|---|
| HI KYC 2016 (`MasterDirections.aspx?ID=6316`) | HTML body script mix | **Unicode Devanagari** present (thousands of Devanagari code points). Not legacy-font Latin gibberish. |
| HI PPI (`?ID=6905`) | same | **Unicode Devanagari** ✅ |
| HI IT Outsourcing (`?ID=7333`) | same | **Unicode Devanagari** ✅ |

Implication: Hindi HTML sources need an HTML extract path or a manual “Save as PDF” before `pymupdf` ingest. Legacy-font **PDF** OCR (`hin+eng`) remains required when a Hindi PDF’s text layer is Latin gibberish / Kruti Dev — unit tests cover that path with fakes.

## Download policy (locked)

- Honour robots / WAF reality: if automated GET is blocked or disallowed, **download manually** into ignored `data/raw/`.
- `PoliteDownloader` still implements User-Agent, ≥3 s spacing, robots check, and URL cache for when access is allowed (and for tests with `respx`).
- Manifest commits **URLs + SHA-256 only**; never commit raw PDFs or `.env`.

### 2026-11-11 download spike note

`rbidocs.rbi.org.in` PDF URLs often return an **HTML captcha / Akamai interstitial** to
non-interactive clients (and sometimes even to a fresh browser tab). `PoliteDownloader`
detects this and raises `DisallowedError` instead of caching garbage.

**Workaround for local ingest:** open the Master Direction HTML page in a browser, use
Print → Save as PDF, then place the file at:

- `data/raw/<sha256(url)[:24]>.pdf` (preferred), or
- `data/raw/<sha256(url)[:24]>.html` (same basename — used when the manifest URL is `.aspx`)

Then re-run `sahayak ingest --only <doc_id>`. Never commit PDFs. CI/unit tests never hit the live site.

## Benchmark HF paths (S2, local only — never commit under `data/bench/`)

**MIRACL topics/qrels** (`miracl/miracl`):

- `miracl-v1.0-hi/topics/topics.miracl-v1.0-hi-dev.tsv`
- `miracl-v1.0-hi/qrels/qrels.miracl-v1.0-hi-dev.tsv`

**MIRACL corpus** (`miracl/miracl-corpus`): Hindi `docs-*.jsonl.gz` shards (list with `huggingface-cli` before coding a full download). Practical subset: all judged hi-dev passages + 50K random distractors (`evals.benchmarks.miracl.build_miracl_hi_50k_subset`). Full 506K e5 embed = overnight follow-up.

**IndicQA-hi** (`mteb/IndicQARetrieval`): `load_dataset(..., "hi-corpus"|"hi-queries"|"hi-qrels", split="test")`.

**NoMIRACL** (`miracl/nomiracl`): fixture loader in `evals.benchmarks.nomiracl`; confirm live split names before S3.

### Manual HI smoke set (DoD)

Ingested 2026-11-11 locally (`script_mismatch=False`, 0 OCR). Print→PDF text layers can
mangle Devanagari glyphs; `detect_script` still reports `hi`. Prefer official PDFs when WAF allows.

| doc_id | Cache basename | pages / chunks | sha256 (prefix) |
|---|---|---|---|
| `MD-KYC-CB-2025-HI` | `8f2bda425b107c27df6f240c` | 23 / 223 | `ba4426a973c8…` |
| `MD-PPI-HI` | `0291c4b0886ff62bffab511a` | 1 / 3 (truncated print) | `e5cedde51a33…` |
| `MD-FRAUD-CB-HI` | `25a987ce71597f68201905e1` | 8 / 69 | `bf75de89fbf0…` |
