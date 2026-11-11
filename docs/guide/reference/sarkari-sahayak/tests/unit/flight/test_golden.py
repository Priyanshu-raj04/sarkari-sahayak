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
