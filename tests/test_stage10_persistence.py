from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from market_radar.models import MarketScan, MovementDetection, SymbolSnapshot
from market_radar.persistence import (
    initialize_database,
    list_signals,
    get_entry_latency,
    persistence_summary,
    record_actionable_signals,
    update_entry_latency,
)


def candidate(symbol: str, decision: str, close_ms: int = 1_000) -> MovementDetection:
    return MovementDetection(
        symbol=symbol,
        detector_version="stage2-v1",
        candle_close_time_ms=close_ms,
        movement_state="EARLY_MOVEMENT",
        direction_hint="UP" if decision != "SHORT" else "DOWN",
        is_moving=True,
        ret_5m_pct=0.5,
        ret_15m_pct=1.0,
        ret_1h_pct=2.0,
        ret_24h_pct=4.0,
        median_abs_ret_5m_pct=0.1,
        return_expansion_ratio=5.0,
        volume_ratio=2.5,
        range_ratio=2.0,
        trades_ratio=2.0,
        directional_persistence=True,
        evidence_count=5,
        stage="IGNITION",
        long_score=82.0 if decision == "LONG" else 20.0,
        short_score=82.0 if decision == "SHORT" else 20.0,
        score_edge=62.0 if decision in {"LONG", "SHORT"} else 0.0,
        decision=decision,
        decision_context_balance=2,
        decision_reasons=("test_reason",),
        decision_version="stage6-v1",
    )


def snapshot(symbol: str, close: float) -> SymbolSnapshot:
    return SymbolSnapshot(
        symbol=symbol,
        candle_open_time_ms=700,
        candle_close_time_ms=1_000,
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        base_volume_5m=10,
        quote_volume_5m=100,
        trades_5m=10,
        taker_buy_base_volume_5m=6,
        taker_buy_quote_volume_5m=60,
        quote_volume_24h=1000,
        price_change_pct_24h=2,
    )


def sample_scan() -> MarketScan:
    rows = [
        candidate("SOLUSDT", "LONG"),
        candidate("ETHUSDT", "SHORT"),
        candidate("ENAUSDT", "NO TRADE"),
    ]
    return MarketScan(
        scan_started_at_ms=100,
        scan_finished_at_ms=200,
        binance_server_time_ms=150,
        interval="5m",
        universe_count=527,
        completed_count=527,
        failed_count=0,
        candle_close_time_ms=1_000,
        movement_detector_version="stage2-v1",
        movement_evaluated_count=527,
        movement_skipped_count=0,
        moving_candidate_count=3,
        movement_stage_version="stage3-v1",
        direction_score_version="stage4-v1",
        market_context_version="stage5-v1",
        context_complete_count=3,
        context_partial_count=0,
        decision_version="stage6-v1",
        long_decision_count=1,
        short_decision_count=1,
        no_trade_decision_count=1,
        ignition_count=3,
        expansion_count=0,
        exhaustion_count=0,
        symbols=[
            snapshot("SOLUSDT", 201.5),
            snapshot("ETHUSDT", 3200.0),
            snapshot("ENAUSDT", 0.8),
        ],
        moving_candidates=rows,
    )


class Stage10PersistenceTests(unittest.TestCase):
    def test_schema_contains_future_lifecycle_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "radar.sqlite3"
            initialize_database(db)
            with sqlite3.connect(db) as conn:
                names = {
                    row[0]
                    for row in conn.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
            self.assertTrue(
                {
                    "signals", "signal_outcomes", "ai_reviews", "positions",
                    "trade_events", "entry_latency",
                } <= names
            )

    def test_only_actionable_signals_are_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "radar.sqlite3"
            result = record_actionable_signals(sample_scan(), db)
            self.assertEqual(result, {"inserted": 2, "updated": 0})
            rows = list_signals(path=db)
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["symbol"] for row in rows}, {"SOLUSDT", "ETHUSDT"})
            sol = next(row for row in rows if row["symbol"] == "SOLUSDT")
            self.assertEqual(sol["signal_price"], 201.5)
            self.assertEqual(sol["side"], "LONG")

    def test_entry_latency_starts_with_signal_timing_and_derives_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "radar.sqlite3"
            record_actionable_signals(sample_scan(), db)
            rows = get_entry_latency(path=db)
            self.assertEqual(len(rows), 2)
            sol = next(row for row in rows if row["signal_id"].startswith("SOLUSDT:"))
            self.assertEqual(sol["candle_close_at_ms"], 1_000)
            self.assertEqual(sol["scan_started_at_ms"], 100)
            self.assertEqual(sol["scan_finished_at_ms"], 200)
            self.assertEqual(sol["signal_created_at_ms"], 200)
            self.assertEqual(sol["scan_duration_ms"], 100)
            self.assertEqual(sol["candle_to_signal_ms"], -800)

            update_entry_latency(
                sol["signal_id"],
                path=db,
                ai_queued_at_ms=300,
                ai_started_at_ms=350,
                ai_finished_at_ms=500,
                order_created_at_ms=550,
                position_opened_at_ms=600,
            )
            row = get_entry_latency(signal_id=sol["signal_id"], path=db)[0]
            self.assertEqual(row["signal_to_ai_queue_ms"], 100)
            self.assertEqual(row["ai_queue_wait_ms"], 50)
            self.assertEqual(row["ai_review_ms"], 150)
            self.assertEqual(row["approval_to_order_ms"], 50)
            self.assertEqual(row["order_to_fill_ms"], 50)
            self.assertEqual(row["signal_to_fill_ms"], 400)

    def test_replaying_same_scan_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "radar.sqlite3"
            first = record_actionable_signals(sample_scan(), db)
            second = record_actionable_signals(sample_scan(), db)
            self.assertEqual(first, {"inserted": 2, "updated": 0})
            self.assertEqual(second, {"inserted": 0, "updated": 2})
            summary = persistence_summary(db)
            self.assertEqual(summary["signal_count"], 2)
            self.assertEqual(summary["trade_event_count"], 2)
            self.assertEqual(summary["pending_outcomes"], 2)

    def test_history_filters_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "radar.sqlite3"
            record_actionable_signals(sample_scan(), db)
            self.assertEqual(len(list_signals(path=db, side="LONG")), 1)
            self.assertEqual(len(list_signals(path=db, symbol="ETHUSDT")), 1)
            summary = persistence_summary(db)
            self.assertEqual(summary["long_count"], 1)
            self.assertEqual(summary["short_count"], 1)
            self.assertEqual(summary["position_count"], 0)


if __name__ == "__main__":
    unittest.main()
