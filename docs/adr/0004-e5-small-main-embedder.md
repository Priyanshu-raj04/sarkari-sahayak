# 4. multilingual-e5-small as the main embedder
Date: 2026-11-11 · Status: Accepted

## Context
S2 needs a single dense embedder for ingest, hybrid retrieval, and benches. Candidates
were `intfloat/multilingual-e5-small` (384-d, ~118 M) and `BAAI/bge-m3` (heavier; optional
sparse). We measure before claiming.

## Decision
Use **`intfloat/multilingual-e5-small`** as the default dense embedder (`SAHAYAK_EMBED_MODEL`),
with mandatory `query:` / `passage:` prefixes (`E5Embedder`). Keep FakeEmbedder for unit tests.
bge-m3 remains optional for later sparse/ablation work, not the default path.

## Measured evidence (this machine, 2026-11-11)

### Encode speed (N=100 fixed HI/EN strings, device=mps)

Source: `docs/results/embed_microbench.json`

| Model | Load (s) | Encode (s) | ms / passage |
|---|---:|---:|---:|
| intfloat/multilingual-e5-small | 19.266 | 2.012 | 20.122 |
| BAAI/bge-m3 | 53.835 | 10.533 | 105.330 |

e5-small was ~**5.2×** faster per passage than bge-m3 on this microbench and loaded faster.

### IndicQA-hi quality (e5 + bm25s hybrid)

Source: `docs/results/retrieval.json` (n=1544 queries, corpus=261, git `e28584fe…`)

| System | nDCG@10 | R@10 | R@100 | MRR@10 |
|---|---:|---:|---:|---:|
| bm25 (bm25s + regex tokenize) | 0.7026 | 0.8494 | 0.9569 | 0.6558 |
| dense e5-small | 0.6571 | 0.8112 | 0.9689 | 0.6083 |
| hybrid RRF | **0.7204** | **0.8698** | 0.9628 | **0.673** |

Hybrid beat either alone on nDCG@10 / R@10 / MRR@10.

### Quality vs bge-m3

**Deferred.** We did not finish a full IndicQA dense run with bge-m3 in this close-out
(encode alone is ~5× slower; dual quality table left for a follow-up). Speed evidence above
is enough to prefer e5-small as the default; revisit if sparse lexical weights are needed.

## Consequences
- CLI ingest and `make bench-quick` load e5 (`uv sync --extra ml`); CI stays without `ml`.
- Hosted profile may later swap ONNX e5 (S6); same 384-d contract.
- MIRACL-hi 50K / full 506K numbers are not in this ADR — see `docs/results/retrieval.md`
  (IndicQA only so far; MIRACL = follow-up overnight).
