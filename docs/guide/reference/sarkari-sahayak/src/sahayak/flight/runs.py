"""Persist runs and feedback so failures can be promoted into the golden set."""

from typing import Any, Literal

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class RunStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def record(
        self,
        *,
        run_id: str,
        question: str,
        answer: str,
        refused: bool,
        degraded: bool,
        citations: list[str],
        latency_ms: int,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.conn.execute(
            """INSERT INTO runs (run_id, question, answer, refused, degraded, citations,
                                 latency_ms, model, trace_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                run_id,
                question,
                answer,
                refused,
                degraded,
                Jsonb(citations),
                latency_ms,
                model,
                trace_id,
            ),
        )
        self.conn.commit()

    def set_feedback(self, run_id: str, value: Literal[-1, 0, 1], note: str | None = None) -> bool:
        cur = self.conn.execute(
            "UPDATE runs SET feedback = %s, note = %s WHERE run_id = %s", (value, note, run_id)
        )
        self.conn.commit()
        return cur.rowcount == 1

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            return cur.execute("SELECT * FROM runs WHERE run_id = %s", (run_id,)).fetchone()

    def flagged(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(
                "SELECT * FROM runs WHERE feedback = -1 ORDER BY created_at DESC LIMIT %s",
                (limit,),
            ).fetchall()
