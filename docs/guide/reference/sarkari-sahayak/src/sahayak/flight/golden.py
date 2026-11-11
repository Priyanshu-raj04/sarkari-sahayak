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
