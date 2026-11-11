"""Timed encode microbench: e5-small vs bge-m3 on a fixed N passages (ADR-0004 evidence)."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "docs" / "results" / "embed_microbench.json"

PASSAGES = [
    "केवाईसी नियमों का पालन सभी विनियमित संस्थाओं के लिए अनिवार्य है।",
    "Reserve Bank of India issues Master Directions on KYC for commercial banks.",
    "पूर्वदत्त भुगतान लिखतों पर मास्टर निदेश में ग्राहक सुरक्षा प्रावधान हैं।",
    "Fraud risk management frameworks must include early warning signals.",
    "ब्याज दर निर्धारण में पारदर्शिता आवश्यक है।",
] * 20  # N=100


def _device() -> str | None:
    if platform.system() == "Darwin":
        try:
            import torch  # type: ignore[import-not-found]  # noqa: PLC0415

            if torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            return None
    return None


def _time_e5(n: int) -> dict[str, float | str]:
    from sahayak.embed.e5 import E5Embedder  # noqa: PLC0415

    t0 = time.perf_counter()
    emb = E5Embedder.load("intfloat/multilingual-e5-small", device=_device())
    load_s = time.perf_counter() - t0
    texts = PASSAGES[:n]
    t1 = time.perf_counter()
    emb.embed_passages(texts)
    enc_s = time.perf_counter() - t1
    return {
        "model": "intfloat/multilingual-e5-small",
        "load_s": round(load_s, 3),
        "encode_s": round(enc_s, 3),
        "ms_per_passage": round(1000 * enc_s / max(n, 1), 3),
    }


def _time_bge(n: int) -> dict[str, float | str]:
    from FlagEmbedding import BGEM3FlagModel  # type: ignore[import-not-found]  # noqa: PLC0415

    t0 = time.perf_counter()
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    load_s = time.perf_counter() - t0
    texts = PASSAGES[:n]
    t1 = time.perf_counter()
    model.encode(texts, return_dense=True, return_sparse=False)
    enc_s = time.perf_counter() - t1
    return {
        "model": "BAAI/bge-m3",
        "load_s": round(load_s, 3),
        "encode_s": round(enc_s, 3),
        "ms_per_passage": round(1000 * enc_s / max(n, 1), 3),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--skip-bge", action="store_true")
    args = p.parse_args()
    results = {
        "date": date.today().isoformat(),
        "n": args.n,
        "device": _device() or "cpu",
        "e5": _time_e5(args.n),
    }
    if not args.skip_bge:
        try:
            results["bge_m3"] = _time_bge(args.n)
        except Exception as exc:
            results["bge_m3"] = {"error": str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
