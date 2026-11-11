"""Unit-level checks for migration helpers (no live Postgres)."""

from types import SimpleNamespace

from sahayak.store.migrate import OPTIONAL_PREFIX, has_extension


class _Conn:
    def __init__(self, row: tuple[int] | None) -> None:
        self._row = row

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> SimpleNamespace:
        assert "pg_available_extensions" in query
        assert params == ("pg_search",)
        return SimpleNamespace(fetchone=lambda: self._row)


def test_has_extension_true_when_row_present() -> None:
    assert has_extension(_Conn((1,)), "pg_search") is True  # type: ignore[arg-type]


def test_has_extension_false_when_missing() -> None:
    assert has_extension(_Conn(None), "pg_search") is False  # type: ignore[arg-type]


def test_optional_prefix_marks_bm25_migration() -> None:
    assert OPTIONAL_PREFIX in "0002_bm25_paradedb.sql"
