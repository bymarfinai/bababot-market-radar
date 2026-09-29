from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.persistence import _sqlite_connect, initialize_database
from market_radar.pipeline_cohort import (
    DEFAULT_BOUNDARY_MS,
    POST_COHORT,
    PRE_COHORT,
    backfill_position_cohorts,
    cohort_for_opened_at,
    cohort_summary,
    label_signal_cohort,
    list_cohorts,
)


def seed_signal(conn, signal_id: str, ts: int) -> None:
    conn.execute(
        """
        insert into signals (
            signal_id, symbol, side, signal_time_ms, signal_price,
            decision_reasons_json, snapshot_json, first_seen_at_ms,
            last_seen_at_ms, persistence_version
        ) values (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            signal_id, "TESTUSDT", "LONG", ts, 100.0,
            "[]", "{}", ts, ts, "test",
        ),
    )


class PipelineCohortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "cohort.sqlite3"
        self.env = patch.dict(
            os.environ,
            {
                "BABABOT_DB_PATH": str(self.db),
                "ENTRY_REBUILD_COHORT_BOUNDARY_MS": str(DEFAULT_BOUNDARY_MS),
            },
            clear=False,
        )
        self.env.start()
        os.environ.pop("DATABASE_URL", None)
        initialize_database()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_boundary_is_hard_on_opened_at(self):
        self.assertEqual(
            cohort_for_opened_at(DEFAULT_BOUNDARY_MS - 1),
            PRE_COHORT,
        )
        self.assertEqual(
            cohort_for_opened_at(DEFAULT_BOUNDARY_MS),
            POST_COHORT,
        )

    def test_label_persists_post_stack(self):
        with _sqlite_connect(self.db) as conn:
            seed_signal(conn, "TEST:POST:LONG", DEFAULT_BOUNDARY_MS)
        row = label_signal_cohort(
            "TEST:POST:LONG",
            opened_at_ms=DEFAULT_BOUNDARY_MS + 10,
        )
        self.assertEqual(row["cohort"], POST_COHORT)
        self.assertEqual(
            row["paper_trading_version"],
            "stage13-v2-event-driven",
        )
        rows = list_cohorts(cohort=POST_COHORT, limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["signal_id"], "TEST:POST:LONG")

    def test_backfill_separates_pre_and_post_positions(self):
        with _sqlite_connect(self.db) as conn:
            seed_signal(conn, "TEST:PRE:LONG", DEFAULT_BOUNDARY_MS - 10)
            seed_signal(conn, "TEST:POST:LONG", DEFAULT_BOUNDARY_MS + 10)
            conn.execute(
                """
                insert into positions (
                    position_id, signal_id, symbol, side, status,
                    opened_at_ms, realized_pnl, mode
                ) values (?,?,?,?,?,?,?,?)
                """,
                (
                    "PAPER:PRE", "TEST:PRE:LONG", "TESTUSDT", "LONG",
                    "CLOSED", DEFAULT_BOUNDARY_MS - 1, -5.0, "PAPER",
                ),
            )
            conn.execute(
                """
                insert into positions (
                    position_id, signal_id, symbol, side, status,
                    opened_at_ms, realized_pnl, mode
                ) values (?,?,?,?,?,?,?,?)
                """,
                (
                    "PAPER:POST", "TEST:POST:LONG", "TESTUSDT", "LONG",
                    "CLOSED", DEFAULT_BOUNDARY_MS, 5.0, "PAPER",
                ),
            )

        counts = backfill_position_cohorts()
        self.assertEqual(counts[PRE_COHORT], 1)
        self.assertEqual(counts[POST_COHORT], 1)

        summary = cohort_summary()
        by_name = {row["cohort"]: row for row in summary["cohorts"]}
        self.assertEqual(by_name[PRE_COHORT]["closed"], 1)
        self.assertEqual(by_name[POST_COHORT]["closed"], 1)
        self.assertEqual(float(by_name[PRE_COHORT]["net_pnl"]), -5.0)
        self.assertEqual(float(by_name[POST_COHORT]["net_pnl"]), 5.0)


if __name__ == "__main__":
    unittest.main()
