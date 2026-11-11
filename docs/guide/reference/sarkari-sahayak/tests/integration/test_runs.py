import pytest

from sahayak.flight.runs import RunStore

pytestmark = pytest.mark.integration


def test_record_feedback_and_flagged(conn) -> None:  # type: ignore[no-untyped-def]
    conn.execute("TRUNCATE runs")
    store = RunStore(conn)
    store.record(
        run_id="r1",
        question="आज मौसम?",
        answer="माफ़ कीजिए",
        refused=True,
        degraded=False,
        citations=[],
        latency_ms=12,
        trace_id="t1",
    )
    assert store.set_feedback("r1", -1, "should refuse in Hindi — ok actually")
    assert not store.set_feedback("missing", -1)
    row = store.get("r1")
    assert row is not None
    assert row["feedback"] == -1
    assert row["citations"] == []
    assert [r["run_id"] for r in store.flagged()] == ["r1"]
