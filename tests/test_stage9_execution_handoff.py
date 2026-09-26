from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_radar.execution_handoff import (
    EXECUTION_HANDOFF_VERSION,
    EXECUTION_MODE,
    build_execution_handoff,
    load_execution_handoff,
    write_execution_handoff_atomic,
)
from market_radar.models import MarketScan, MovementDetection


def candidate(symbol: str, decision: str) -> MovementDetection:
    return MovementDetection(
        symbol=symbol,
        detector_version="stage2-v1",
        candle_close_time_ms=1_000,
        movement_state="EARLY_MOVEMENT",
        direction_hint="UP" if decision != "SHORT" else "DOWN",
        is_moving=True,
        ret_5m_pct=0.5,
        ret_15m_pct=1.0,
        ret_1h_pct=2.0,
        ret_24h_pct=4.0,
        median_abs_ret_5m_pct=0.1,
        return_expansion_ratio=5.0,
        volume_ratio=2.0,
        range_ratio=2.0,
        trades_ratio=2.0,
        directional_persistence=True,
        evidence_count=5,
        stage="IGNITION",
        long_score=82.0 if decision == "LONG" else 20.0,
        short_score=82.0 if decision == "SHORT" else 20.0,
        score_edge=62.0 if decision in {"LONG", "SHORT"} else 0.0,
        decision=decision,
        decision_reasons=("test_reason",),
        decision_version="stage6-v1",
    )


def scan() -> MarketScan:
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
        moving_candidates=rows,
    )


class Stage9ExecutionHandoffTests(unittest.TestCase):
    def test_only_long_and_short_become_execution_intents(self):
        result = build_execution_handoff(scan())
        self.assertEqual(result["intent_count"], 2)
        self.assertEqual(
            [x["symbol"] for x in result["intents"]],
            ["SOLUSDT", "ETHUSDT"],
        )

    def test_handoff_is_blocked_and_non_executable_by_default(self):
        result = build_execution_handoff(scan())
        for intent in result["intents"]:
            self.assertEqual(intent["handoff_version"], EXECUTION_HANDOFF_VERSION)
            self.assertEqual(intent["execution_mode"], EXECUTION_MODE)
            self.assertEqual(intent["risk_confirmation"], "PENDING")
            self.assertEqual(intent["execution_status"], "BLOCKED")
            self.assertFalse(intent["executable"])
            self.assertIsNone(intent["entry_price"])
            self.assertIsNone(intent["quantity"])
            self.assertIsNone(intent["stop_loss"])
            self.assertIsNone(intent["take_profit"])
        self.assertFalse(result["live_order_submission_enabled"])

    def test_intent_id_is_deterministic_and_candle_scoped(self):
        result = build_execution_handoff(scan())
        self.assertEqual(
            result["intents"][0]["intent_id"],
            "SOLUSDT:1000:LONG",
        )
        self.assertEqual(
            result["intents"][1]["intent_id"],
            "ETHUSDT:1000:SHORT",
        )

    def test_no_trade_never_becomes_execution_intent(self):
        result = build_execution_handoff(scan())
        self.assertNotIn(
            "ENAUSDT",
            [x["symbol"] for x in result["intents"]],
        )

    def test_atomic_handoff_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "execution_intents.json"
            written = write_execution_handoff_atomic(scan(), path)
            self.assertEqual(written, path)
            loaded = load_execution_handoff(path)
            self.assertEqual(loaded["intent_count"], 2)
            self.assertFalse(loaded["live_order_submission_enabled"])


if __name__ == "__main__":
    unittest.main()
