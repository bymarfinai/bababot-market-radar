from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.persistence import initialize_sqlite
from market_radar.position_lifecycle import (
    _arbitrate,
    _early_invalidation_guard,
    _health_from_snapshot,
    _lifecycle_guards,
    _profit_protection_guard,
    _should_persist_fast_evaluation,
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
        self.assertAlmostEqual(_side_return("LONG", 100.0, 108.0), 8.0, places=9)

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

    def test_v3_early_invalidation_closes_wrong_direction_examples(self):
        with patch.dict(
            os.environ,
            {
                "STAGE12_EARLY_WINDOW_MINUTES": "30",
                "STAGE12_EARLY_MFE_MAX_PCT": "0.35",
                "STAGE12_EARLY_CLOSE_MAE_PCT": "1.0",
                "STAGE12_EARLY_CLOSE_PNL_PCT": "0.60",
                "STAGE12_EARLY_REDUCE_PNL_PCT": "0.35",
                "STAGE12_EARLY_MIN_CONTRADICTIONS": "2",
            },
            clear=False,
        ):
            aztec = _early_invalidation_guard(
                age_minutes=18.5,
                status="OPEN",
                mfe_pct=0.0,
                mae_pct=-1.572,
                current_pnl_pct=-1.519,
                contradiction_count=3,
            )
            rose = _early_invalidation_guard(
                age_minutes=18.5,
                status="OPEN",
                mfe_pct=0.0,
                mae_pct=-0.730,
                current_pnl_pct=-0.730,
                contradiction_count=3,
            )
            pha = _early_invalidation_guard(
                age_minutes=19.4,
                status="OPEN",
                mfe_pct=0.246,
                mae_pct=-1.822,
                current_pnl_pct=-1.571,
                contradiction_count=2,
            )
        self.assertEqual(aztec["action"], "CLOSE")
        self.assertEqual(rose["action"], "CLOSE")
        self.assertEqual(pha["action"], "CLOSE")

    def test_v3_single_contradiction_severe_mae_reduces_not_closes(self):
        result = _early_invalidation_guard(
            age_minutes=10.0,
            status="OPEN",
            mfe_pct=0.05,
            mae_pct=-1.17,
            current_pnl_pct=-0.87,
            contradiction_count=1,
        )
        self.assertEqual(result["action"], "REDUCE")
        self.assertIn("single_fresh_contradiction", result["reasons"])

    def test_v3_profit_protection_matches_giveback_examples(self):
        with patch.dict(
            os.environ,
            {
                "STAGE12_PROTECT_ARM_MFE_PCT": "0.50",
                "STAGE12_PROTECT_REDUCE_GIVEBACK_RATIO": "0.55",
                "STAGE12_PROTECT_CLOSE_GIVEBACK_RATIO": "0.80",
            },
            clear=False,
        ):
            nmr = _profit_protection_guard(
                status="OPEN",
                mfe_pct=2.147,
                current_pnl_pct=-0.245,
                contradiction_count=1,
            )
            opg = _profit_protection_guard(
                status="OPEN",
                mfe_pct=1.901,
                current_pnl_pct=0.060,
                contradiction_count=2,
            )
            bless = _profit_protection_guard(
                status="OPEN",
                mfe_pct=1.623,
                current_pnl_pct=0.602,
                contradiction_count=3,
            )
            plume = _profit_protection_guard(
                status="OPEN",
                mfe_pct=0.708,
                current_pnl_pct=-0.748,
                contradiction_count=1,
            )
        self.assertEqual(nmr["action"], "CLOSE")
        self.assertEqual(opg["action"], "CLOSE")
        self.assertEqual(bless["action"], "REDUCE")
        self.assertEqual(plume["action"], "CLOSE")

    def test_v3_layer_borderline_stays_with_thesis_health(self):
        guards = _lifecycle_guards(
            age_minutes=32.6,
            status="OPEN",
            mfe_pct=0.327,
            mae_pct=-0.330,
            current_pnl_pct=-0.281,
            contradiction_count=3,
        )
        self.assertEqual(guards["action"], "HOLD")

    def test_v3_already_reduced_escalates_second_protection_to_close(self):
        result = _profit_protection_guard(
            status="REDUCED",
            mfe_pct=1.50,
            current_pnl_pct=0.60,
            contradiction_count=1,
        )
        self.assertEqual(result["action"], "CLOSE")
        self.assertIn("already_reduced_escalate_close", result["reasons"])

    def test_v3_initial_fast_hold_is_persisted_for_monitoring_ux(self):
        self.assertTrue(
            _should_persist_fast_evaluation("HOLD", has_previous=False)
        )
        self.assertFalse(
            _should_persist_fast_evaluation("HOLD", has_previous=True)
        )
        self.assertTrue(
            _should_persist_fast_evaluation("REDUCE", has_previous=True)
        )
        self.assertTrue(
            _should_persist_fast_evaluation("CLOSE", has_previous=True)
        )

    def test_v3_healthy_profitable_position_does_not_overprotect(self):
        result = _profit_protection_guard(
            status="OPEN",
            mfe_pct=1.50,
            current_pnl_pct=1.20,
            contradiction_count=0,
        )
        self.assertEqual(result["action"], "HOLD")

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
