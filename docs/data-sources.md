# Data sources

Checked: **2026-11-11**.

## Summary table

| Source | URL | Licence / terms | Date checked | Findings |
|---|---|---|---|---|
| RBI Master Directions (EN) | https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx | Public regulatory text; reuse terms not fully verified — we never re-host PDFs | 2026-11-11 | Listing is the SoT index. Individual MDs expose a PDF on `rbidocs.rbi.org.in` (e.g. KYC CB → `…/PDFs/169MD.PDF`). |
| RBI Master Directions (HI) | https://www.rbi.org.in/Hindi/scripts/MasterDirections.aspx | Same | 2026-11-11 | Hindi is often **Unicode HTML** (not a PDF). Devanagari text layer is real Unicode on sampled pages. |
| RBI robots.txt | https://www.rbi.org.in/robots.txt | n/a | 2026-11-11 | Browser GET returned **“Unauthorised Access”** (WAF). Automated `curl` from this machine was blocked (proxy/403). Treat bulk scripted download as **not clearly permitted**; prefer polite downloader only when a fetch is allowed, else **manual** PDF save into `data/raw/`. |
| RBI Disclaimer / terms | Footer “Disclaimer” on rbi.org.in | Site terms | 2026-11-11 | Disclaimer link present site-wide; content pages are behind CMS paths that change. Conservative rule: **do not re-host**, cite + deep-link to rbi.org.in / rbidocs only. |
| MIRACL-hi | Hugging Face | Research / dataset card | — | Local only; never re-host (S2+). |

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
Print → Save as PDF (or solve the captcha and download), then place the file at the
cache path `data/raw/<sha256(url)[:24]>.pdf` and re-run `sahayak ingest --only …`.
For CI/unit tests we never hit the live site.
