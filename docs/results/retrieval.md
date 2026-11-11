# Retrieval benchmark results

Generated from `docs/results/retrieval.json`. **Do not hand-edit metric cells.**

| Dataset (split, n) | Corpus | System | Model | nDCG@10 | R@10 | R@100 | MRR@10 | Date | Git |
|---|---|---|---|---:|---:|---:|---:|---|---|
| indicqa-hi (test, 1544) | 261 | bm25 | bm25s+regex-tokenize | 0.7026 | 0.8494 | 0.9569 | 0.6558 | 2026-11-11 | `e28584fe` |
| indicqa-hi (test, 1544) | 261 | dense | intfloat/multilingual-e5-small | 0.6571 | 0.8112 | 0.9689 | 0.6083 | 2026-11-11 | `e28584fe` |
| indicqa-hi (test, 1544) | 261 | hybrid | intfloat/multilingual-e5-small | 0.7204 | 0.8698 | 0.9628 | 0.673 | 2026-11-11 | `e28584fe` |
| MIRACL-hi (dev, 350) | 50K subset | – | – | – | – | – | – | – | not measured |
| MIRACL-hi (dev, 350) | 506K full | – | – | – | – | – | – | – | overnight follow-up |

Notes: MIRACL rows are placeholders (Q1=A close-out). hybrid+rerank and hosted ONNX not run this session. Regenerate metric rows via `make bench-quick` / `run_retrieval` only.
