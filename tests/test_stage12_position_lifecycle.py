from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from market_radar.persistence import initialize_sqlite
from market_radar.position_lifecycle import (
    _arbitrate,
    _health_from_snapshot,
    _mfe_mae,
    _position_memory_penalties,
    _side_return,
)


class Stage12LifecycleTests(unittest.TestCase):
    def test_healthy_long_holds_even_if_profit_is_large(self):
        snapshot = {
            "ret_5m_pct": 0.4,
            "ret_15m_pct": 1.2,
            "ret_1h_pct": 3.0,
            "stage": "EXPANSION",
            "long_score": 90.0,
            "short_score": 12.0,
            "structure_status": "BREAKOUT",
            "taker_bias": "BUY",
            "oi_interpretation": "FRESH_LONG_PARTICIPATION",
            "market_regime": "BULL",
        }
        health = _health_from_snapshot("LONG", snapshot)
        self.assertEqual(health["deterministic_action"], "HOLD")
        self.assertGreaterEqual(health["health_score"], 90.0)
        self.assertEqual(_side_return("LONG", 100.0, 108.0), 8.0)

    def test_strong_reversal_closes_long(self):
        snapshot = {
            "ret_5m_pct": -0.8,
            "ret_15m_pct": -1.5,
            "ret_1h_pct": -3.0,
            "stage": "EXHAUSTION",
            "long_score": 15.0,
            "short_score": 85.0,
            "structure_status": "BREAKDOWN",
            "taker_bias": "SELL",
            "oi_interpretation": "FRESH_SHORT_PARTICIPATION",
            "market_regime": "BEAR",
        }
        health = _health_from_snapshot("LONG", snapshot)
        self.assertEqual(health["deterministic_action"], "CLOSE")
        self.assertGreaterEqual(len(health["contradictions"]), 4)

    def test_weakening_context_reduces_before_forced_close(self):
        snapshot = {
            "ret_5m_pct": -0.2,
            "ret_15m_pct": -0.3,
            "ret_1h_pct": 0.5,
            "stage": "EXHAUSTION",
            "long_score": 50.0,
            "short_score": 40.0,
            "structure_status": "NO_STRUCTURAL_BREAK",
            "taker_bias": "SELL",
            "oi_interpretation": "UNRESOLVED",
            "market_regime": "SIDEWAYS",
        }
        health = _health_from_snapshot("LONG", snapshot)
        self.assertEqual(health["deterministic_action"], "REDUCE")

    def test_adaptive_health_uses_giveback_when_base_health_weakens(self):
        snapshot = {
            "ret_5m_pct": 0.2,
            "ret_15m_pct": 0.3,
            "ret_1h_pct": -0.2,
            "stage": "EXPANSION",
            "long_score": 60.0,
            "short_score": 45.0,
            "structure_status": "NO_STRUCTURAL_BREAK",
            "taker_bias": "BALANCED",
            "oi_interpretation": "UNRESOLVED",
            "market_regime": "SIDEWAYS",
        }
        base = _health_from_snapshot("LONG", snapshot)
        adaptive = _health_from_snapshot(
            "LONG",
            snapshot,
            mfe_pct=1.4,
            mae_pct=-0.3,
            unrealized_pnl_pct=0.6,
        )
        self.assertEqual(base["health_score"], 61.0)
        self.assertEqual(base["deterministic_action"], "HOLD")
        self.assertEqual(adaptive["health_score"], 51.0)
        self.assertEqual(adaptive["deterministic_action"], "REDUCE")
        self.assertEqual(adaptive["position_memory"]["giveback_penalty"], 10.0)

    def test_strong_base_health_does_not_overreact_to_normal_giveback(self):
        memory = _position_memory_penalties(
            base_health_score=82.0,
            mfe_pct=1.4,
            mae_pct=-0.3,
            unrealized_pnl_pct=0.6,
        )
        self.assertEqual(memory["giveback_penalty"], 0.0)

    def test_deep_mae_only_penalizes_unrecovered_weak_position(self):
        weak = _position_memory_penalties(
            base_health_score=55.0,
            mfe_pct=0.2,
            mae_pct=-1.6,
            unrealized_pnl_pct=-1.2,
        )
        recovered = _position_memory_penalties(
            base_health_score=55.0,
            mfe_pct=1.8,
            mae_pct=-1.6,
            unrealized_pnl_pct=1.2,
        )
        self.assertEqual(weak["mae_penalty"], 15.0)
        self.assertEqual(recovered["mae_penalty"], 0.0)

    def test_ai_cannot_upgrade_deterministic_close(self):
        self.assertEqual(
            _arbitrate("CLOSE", "HOLD", 20.0, hard_risk=False),
            "CLOSE",
        )

    def test_hard_risk_always_closes(self):
        self.assertEqual(
            _arbitrate("HOLD", "HOLD", 95.0, hard_risk=True),
            "CLOSE",
        )

    def test_ai_can_only_make_borderline_hold_more_conservative(self):
        self.assertEqual(
            _arbitrate("HOLD", "CLOSE", 60.0, hard_risk=False),
            "REDUCE",
        )
        self.assertEqual(
            _arbitrate("HOLD", "CLOSE", 80.0, hard_risk=False),
            "HOLD",
        )

    def test_mfe_mae_accumulate_without_reset(self):
        mfe, mae = _mfe_mae(
            side="LONG",
            entry=100.0,
            high=105.0,
            low=98.0,
            previous_mfe=3.0,
            previous_mae=-1.0,
        )
        self.assertEqual(mfe, 5.0)
        self.assertEqual(mae, -2.0)

    def test_position_evaluation_table_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "radar.sqlite3"
            initialize_sqlite(db)
            with sqlite3.connect(db) as conn:
                names = {
                    row[0]
                    for row in conn.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
            self.assertIn("position_evaluations", names)


if __name__ == "__main__":
    unittest.main()
