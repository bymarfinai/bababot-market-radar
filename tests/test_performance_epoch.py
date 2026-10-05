from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.paper_store import initialize_paper_store, paper_summary
from market_radar.performance_epoch import get_performance_epoch, start_performance_epoch
from market_radar.persistence import _sqlite_connect, initialize_database


class PerformanceEpochTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "epoch.sqlite3"
        self.env = patch.dict(
            os.environ,
            {"BABABOT_DB_PATH": str(self.db)},
            clear=False,
        )
        self.env.start()
        os.environ.pop("DATABASE_URL", None)
        initialize_database()
        initialize_paper_store()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_epoch_persists_without_deleting_history(self):
        boundary = 2_000
        with _sqlite_connect(self.db) as conn:
            conn.execute(
                """
                insert into positions (
                    position_id, symbol, side, status, opened_at_ms,
                    realized_pnl, mode
                ) values (?,?,?,?,?,?,?)
                """,
                ("OLD", "OLDUSDT", "LONG", "CLOSED", 1_000, -10.0, "PAPER"),
            )
            conn.execute(
                """
                insert into positions (
                    position_id, symbol, side, status, opened_at_ms,
                    realized_pnl, mode
                ) values (?,?,?,?,?,?,?)
                """,
                ("NEW_WIN", "NEWUSDT", "LONG", "CLOSED", 2_100, 4.0, "PAPER"),
            )
            conn.execute(
                """
                insert into positions (
                    position_id, symbol, side, status, opened_at_ms,
                    realized_pnl, mode
                ) values (?,?,?,?,?,?,?)
                """,
                ("NEW_OPEN", "OPENUSDT", "SHORT", "OPEN", 2_200, 1.5, "PAPER"),
            )

        epoch = start_performance_epoch(
            label="NEW_DETECTOR_BASELINE",
            note="test",
            started_at_ms=boundary,
        )
        self.assertEqual(epoch["started_at_ms"], boundary)
        self.assertEqual(get_performance_epoch()["label"], "NEW_DETECTOR_BASELINE")

        summary = paper_summary()
        self.assertEqual(summary["closed_positions"], 2)
        self.assertEqual(float(summary["net_pnl"]), -6.0)

        run = summary["current_run"]
        self.assertEqual(run["closed_positions"], 1)
        self.assertEqual(run["open_positions"], 1)
        self.assertEqual(run["wins"], 1)
        self.assertEqual(run["losses"], 0)
        self.assertEqual(float(run["net_pnl"]), 4.0)
        self.assertEqual(run["win_rate_pct"], 100.0)
        self.assertEqual(run["by_side"]["LONG"]["closed_positions"], 1)
        self.assertEqual(run["by_side"]["LONG"]["wins"], 1)
        self.assertEqual(run["by_side"]["LONG"]["win_rate_pct"], 100.0)
        self.assertEqual(float(run["by_side"]["LONG"]["net_pnl"]), 4.0)
        self.assertEqual(run["by_side"]["SHORT"]["open_positions"], 1)
        self.assertEqual(run["by_side"]["SHORT"]["closed_positions"], 0)
        self.assertIsNone(run["by_side"]["SHORT"]["win_rate_pct"])
        self.assertEqual(float(run["by_side"]["SHORT"]["net_pnl"]), 0.0)

        with _sqlite_connect(self.db) as conn:
            self.assertEqual(conn.execute("select count(*) from positions").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
