"""Append measured rows to retrieval.json and regenerate retrieval.md (never hand-edit numbers)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def append_result(path: Path, row: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
    rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rows


def render_markdown(rows: list[dict[str, Any]], md_path: Path) -> None:
    lines = [
        "# Retrieval benchmark results",
        "",
        "Generated from `docs/results/retrieval.json`. **Do not hand-edit metric cells.**",
        "",
        (
            "| Dataset (split, n) | Corpus | System | Model | nDCG@10 | R@10 |"
            " R@100 | MRR@10 | Date | Git |"
        ),
        "|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for r in rows:
        metrics = r.get("metrics") or {}
        n = r.get("n_queries", "–")
        ds = f"{r.get('dataset', '')} ({r.get('split', '')}, {n})"
        sha = (r.get("git_sha") or "unknown")[:8]
        cell = (
            f"| {ds} | {r.get('corpus_size', '–')} | {r.get('system', '–')} | "
            f"{r.get('model', '–')} | {metrics.get('ndcg@10', '–')} | "
            f"{metrics.get('recall@10', '–')} | {metrics.get('recall@100', '–')} | "
            f"{metrics.get('mrr@10', '–')} | {r.get('date', date.today().isoformat())} | "
            f"`{sha}` |"
        )
        lines.append(cell)
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
