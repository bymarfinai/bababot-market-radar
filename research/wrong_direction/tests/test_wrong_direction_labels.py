from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.fresh_entry_gate import STAGE11C_VERSION
from market_radar.persistence import _sqlite_connect, initialize_database
from market_radar.pipeline_cohort import DEFAULT_BOUNDARY_MS, label_signal_cohort
from research.wrong_direction.wrong_direction_labels import (
    CORRECT_RUNNER,
    INSUFFICIENT_DATA,
    RECOVERED_DRAWDOWN,
    RIGHT_THEN_FAILURE,
    STALL_NO_EDGE,
    TRUE_WRONG_DIRECTION,
    backfill_wd1_labels,
    classify_trade_outcome,
    list_wd1_labels,
    wd1_summary,
)


OPENED = DEFAULT_BOUNDARY_MS + 10_000
CLOSED = OPENED + 60 * 60_000


def position(*, pnl: float, pnl_pct: float | None = None) -> dict:
    return {
        "position_id": "PAPER:TEST",
        "signal_id": "TEST:LONG",
        "symbol": "TESTUSDT",
        "side": "LONG",
        "opened_at_ms": OPENED,
        "closed_at_ms": CLOSED,
        "realized_pnl": pnl,
        "realized_pnl_pct": pnl_pct,
        "raw_json": json.dumps({"initial_notional_usdt": 500.0}),
    }


def ev(minutes: float, mfe: float, mae: float) -> dict:
    return {
        "evaluated_at_ms": OPENED + int(minutes * 60_000),
        "candle_close_time_ms": OPENED + int(minutes * 60_000),
        "mfe_pct": mfe,
        "mae_pct": mae,
    }


def seed_signal(conn, signal_id: str) -> None:
    conn.execute(
        """
        insert into signals (
            signal_id, symbol, side, signal_time_ms, signal_price,
            decision_reasons_json, snapshot_json, first_seen_at_ms,
            last_seen_at_ms, persistence_version
        ) values (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            signal_id, "TESTUSDT", "LONG", OPENED - 60_000, 100.0,
            "[]", "{}", OPENED - 60_000, OPENED - 60_000, "test",
        ),
    )


class WD1PureClassifierTests(unittest.TestCase):
    def test_true_wrong_direction(self):
        result = classify_trade_outcome(
            position(pnl=-4.0, pnl_pct=-0.8),
            [ev(3, 0.05, -0.40), ev(20, 0.20, -0.85)],
        )
        self.assertEqual(result["label"], TRUE_WRONG_DIRECTION)

    def test_recovered_drawdown_requires_adverse_before_recovery(self):
        result = classify_trade_outcome(
            position(pnl=3.0, pnl_pct=0.6),
            [ev(4, 0.10, -0.45), ev(18, 0.65, -0.45)],
        )
        self.assertEqual(result["label"], RECOVERED_DRAWDOWN)

    def test_right_then_failure_has_priority_over_recovered_drawdown(self):
        result = classify_trade_outcome(
            position(pnl=-1.0, pnl_pct=-0.2),
            [ev(4, 0.10, -0.45), ev(18, 0.80, -0.45)],
        )
        self.assertEqual(result["label"], RIGHT_THEN_FAILURE)

    def test_stall_no_edge(self):
        result = classify_trade_outcome(
            position(pnl=-0.5, pnl_pct=-0.1),
            [ev(5, 0.20, -0.15), ev(25, 0.30, -0.20)],
        )
        self.assertEqual(result["label"], STALL_NO_EDGE)

    def test_correct_runner(self):
        result = classify_trade_outcome(
            position(pnl=5.0, pnl_pct=1.0),
            [ev(5, 0.30, -0.10), ev(15, 1.20, -0.10)],
        )
        self.assertEqual(result["label"], CORRECT_RUNNER)
        self.assertTrue(result["reached_runner_1pct"])

    def test_future_evaluation_after_close_is_ignored(self):
        future = {
            "evaluated_at_ms": CLOSED + 1,
            "candle_close_time_ms": CLOSED + 1,
            "mfe_pct": 3.0,
            "mae_pct": -0.1,
        }
        result = classify_trade_outcome(
            position(pnl=-3.0, pnl_pct=-0.6),
            [ev(5, 0.10, -0.50), future],
        )
        self.assertEqual(result["label"], TRUE_WRONG_DIRECTION)
        self.assertAlmostEqual(result["max_mfe_pct"], 0.10)

    def test_missing_excursion_path_is_quarantined(self):
        result = classify_trade_outcome(position(pnl=-1.0), [])
        self.assertEqual(result["label"], INSUFFICIENT_DATA)


class WD1StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "wd1.sqlite3"
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

    def _seed_closed_trade(
        self,
        *,
        signal_id: str,
        position_id: str,
        gate_version: str,
        mfe: float,
        mae: float,
        pnl: float,
    ) -> None:
        with _sqlite_connect(self.db) as conn:
            seed_signal(conn, signal_id)
            conn.execute(
                """
                insert into positions (
                    position_id, signal_id, symbol, side, status,
                    opened_at_ms, closed_at_ms, entry_price, exit_price,
                    quantity, realized_pnl, realized_pnl_pct, mode, raw_json
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    position_id, signal_id, "TESTUSDT", "LONG", "CLOSED",
                    OPENED, CLOSED, 100.0, 99.0, 5.0,
                    pnl, 100.0 * pnl / 500.0, "PAPER",
                    json.dumps(
                        {
                            "stage11c_version": gate_version,
                            "initial_notional_usdt": 500.0,
                        }
                    ),
                ),
            )
            conn.execute(
                """
                insert into position_evaluations (
                    evaluation_id, position_id, evaluated_at_ms,
                    candle_close_time_ms, current_price, unrealized_pnl_pct,
                    mfe_pct, mae_pct, health_score, deterministic_action,
                    final_action, hard_risk_triggered, reasons_json,
                    contradictions_json, snapshot_json, lifecycle_version
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    position_id + ":E1", position_id, OPENED + 5 * 60_000,
                    OPENED + 5 * 60_000, 99.5, mae,
                    mfe, mae, 50.0, "HOLD", "HOLD", 0,
                    "[]", "[]", "{}", "test",
                ),
            )
        label_signal_cohort(
            signal_id,
            opened_at_ms=OPENED,
            metadata={"stage11c_version": gate_version},
        )

    def test_backfill_only_admits_proven_current_stage11c_v2(self):
        self._seed_closed_trade(
            signal_id="V2:LONG",
            position_id="PAPER:V2",
            gate_version=STAGE11C_VERSION,
            mfe=0.10,
            mae=-0.50,
            pnl=-3.0,
        )
        self._seed_closed_trade(
            signal_id="V1:LONG",
            position_id="PAPER:V1",
            gate_version="stage11c-v1-fresh-direction",
            mfe=0.10,
            mae=-0.50,
            pnl=-3.0,
        )

        result = backfill_wd1_labels()
        self.assertEqual(result["eligible_closed_positions"], 1)
        self.assertEqual(result["counts"][TRUE_WRONG_DIRECTION], 1)

        rows = list_wd1_labels(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["position_id"], "PAPER:V2")
        self.assertEqual(rows[0]["fresh_gate_version"], STAGE11C_VERSION)

        summary = wd1_summary()
        self.assertEqual(summary["usable_rows"], 1)
        self.assertEqual(
            summary["by_label"][TRUE_WRONG_DIRECTION]["trades"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
