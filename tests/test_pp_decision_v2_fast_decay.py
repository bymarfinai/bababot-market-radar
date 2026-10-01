from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from market_radar.profit_protection_v2 import (
    _V2_STORE_READY,
    evaluate_pp_decision_v2,
)
from market_radar.position_lifecycle import (
    _v2_decay_samples,
    _v2_shadow_evaluation,
)


class PPDecisionV2FastDecayTests(unittest.TestCase):
    def test_runner_mode_preserves_158_to_131_retrace(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=1.58, current_pnl_pct=1.31, previous_pnl_pct=1.58,
            elapsed_seconds=30, danger_score=0, status="OPEN",
        )
        self.assertEqual(r["base_v1_action"], "HOLD")
        self.assertEqual(r["protection_mode"], "RUNNER_PRESERVATION")
        self.assertEqual(r["fast_gate"], "RUNNER_PRESERVE")
        self.assertEqual(r["final_action"], "HOLD")

    def test_runner_same_retrace_over_five_minutes_is_not_forced(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=1.58, current_pnl_pct=1.31, previous_pnl_pct=1.58,
            elapsed_seconds=300, danger_score=0, status="OPEN",
        )
        self.assertEqual(r["base_v1_action"], "HOLD")
        self.assertEqual(r["fast_gate"], "RUNNER_PRESERVE")
        self.assertEqual(r["final_action"], "HOLD")

    def test_runner_mode_does_not_escalate_moderate_fast_decay(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=1.58, current_pnl_pct=1.20, previous_pnl_pct=1.58,
            elapsed_seconds=45, danger_score=2, status="OPEN",
        )
        self.assertEqual(r["protection_mode"], "RUNNER_PRESERVATION")
        self.assertEqual(r["fast_gate"], "RUNNER_PRESERVE")
        self.assertEqual(r["final_action"], r["base_v1_action"])

    def test_runner_emergency_reduces_extreme_fast_collapse(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=2.00, current_pnl_pct=0.95, previous_pnl_pct=1.55,
            elapsed_seconds=20, danger_score=0, status="OPEN",
        )
        self.assertEqual(r["protection_mode"], "RUNNER_PRESERVATION")
        self.assertEqual(r["fast_gate"], "RUNNER_EMERGENCY")
        self.assertEqual(r["final_action"], "REDUCE")

    def test_runner_emergency_closes_already_reduced_lane(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=2.00, current_pnl_pct=0.95, previous_pnl_pct=1.55,
            elapsed_seconds=20, danger_score=0, status="REDUCED",
        )
        self.assertEqual(r["fast_gate"], "RUNNER_EMERGENCY")
        self.assertEqual(r["final_action"], "CLOSE")

    def test_sub1_fast_decay_can_reduce_before_v1_sub1_gate(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=0.80, current_pnl_pct=0.62, previous_pnl_pct=0.80,
            elapsed_seconds=30, danger_score=2, status="OPEN",
        )
        self.assertEqual(r["base_v1_action"], "HOLD")
        self.assertEqual(r["fast_gate"], "FAST_DECISION")
        self.assertEqual(r["final_action"], "REDUCE")

    def test_runner_small_fast_noise_is_preserved(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=1.58, current_pnl_pct=1.40, previous_pnl_pct=1.58,
            elapsed_seconds=30, danger_score=0, status="OPEN",
        )
        self.assertEqual(r["fast_gate"], "RUNNER_PRESERVE")
        self.assertEqual(r["overlay_action"], "HOLD")
        self.assertEqual(r["final_action"], "HOLD")

    def test_profit_recovery_has_zero_decay(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=1.58, current_pnl_pct=1.50, previous_pnl_pct=1.40,
            elapsed_seconds=15, danger_score=6, status="OPEN",
        )
        self.assertEqual(r["drop_pct_points"], 0.0)
        self.assertEqual(r["decay_ratio_per_min"], 0.0)
        self.assertEqual(r["overlay_action"], "HOLD")

    def test_cold_start_does_not_invent_decay(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=1.58, current_pnl_pct=1.20, previous_pnl_pct=None,
            elapsed_seconds=None, danger_score=6, status="OPEN",
        )
        self.assertEqual(r["fast_gate"], "COLD_START")
        self.assertEqual(r["overlay_action"], "HOLD")

    def test_below_one_percent_keeps_stage3_aggression(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=0.80, current_pnl_pct=0.62, previous_pnl_pct=0.80,
            elapsed_seconds=30, danger_score=2, status="OPEN",
        )
        self.assertEqual(r["protection_mode"], "AGGRESSIVE_PROTECTION")
        self.assertEqual(r["fast_gate"], "FAST_DECISION")
        self.assertEqual(r["final_action"], "REDUCE")

    def test_exact_one_percent_handoffs_to_runner_mode(self):
        r = evaluate_pp_decision_v2(
            mfe_pct=1.00, current_pnl_pct=0.78, previous_pnl_pct=1.00,
            elapsed_seconds=15, danger_score=3, status="OPEN",
        )
        self.assertEqual(r["protection_mode"], "RUNNER_PRESERVATION")
        self.assertEqual(r["fast_gate"], "RUNNER_PRESERVE")

    def test_runtime_shadow_flag_is_off_by_default(self):
        with patch.dict(os.environ, {"PP_DECISION_V2_STAGE3_ENABLED": "false"}, clear=False):
            r = _v2_shadow_evaluation(
                position_id="P1", opened_at_ms=900_000, status="OPEN", current_price=101.31,
                mfe_pct=1.58, current_pnl_pct=1.31,
                snapshot={"side_ret_3m_pct": -0.2, "opposite_micro_structure": False,
                          "flow_opposite": False, "positioning_opposite": False},
                evaluated_at_ms=1_000_000,
            )
        self.assertIsNone(r)

    def test_runtime_shadow_has_strict_prospective_boundary(self):
        _v2_decay_samples.clear()
        env = {
            "PP_DECISION_V2_STAGE3_ENABLED": "true",
            "PP_DECISION_V2_STAGE3_START_MS": "900000",
        }
        snapshot = {"side_ret_3m_pct": 0.1, "opposite_micro_structure": False,
                    "flow_opposite": False, "positioning_opposite": False}
        with patch.dict(os.environ, env, clear=False):
            at_boundary = _v2_shadow_evaluation(
                position_id="BOUNDARY", opened_at_ms=900_000, status="OPEN", current_price=101.0,
                mfe_pct=1.0, current_pnl_pct=1.0, snapshot=snapshot, evaluated_at_ms=1_000_000,
            )
        self.assertIsNone(at_boundary)

    def test_runtime_shadow_uses_consecutive_fast_samples_and_logs_every_observation(self):
        _v2_decay_samples.clear()
        _V2_STORE_READY.clear()
        snapshot = {"side_ret_3m_pct": 0.1, "opposite_micro_structure": False,
                    "flow_opposite": False, "positioning_opposite": False}
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "v2.sqlite")
            env = {
                "DATABASE_URL": "",
                "BABABOT_DB_PATH": db,
                "PP_DECISION_V2_STAGE3_ENABLED": "true",
                "PP_DECISION_V2_STAGE3_START_MS": "900000",
            }
            with patch.dict(os.environ, env, clear=False):
                first = _v2_shadow_evaluation(
                    position_id="P2", opened_at_ms=900_001, status="OPEN", current_price=100.80,
                    mfe_pct=0.80, current_pnl_pct=0.80,
                    snapshot=snapshot, evaluated_at_ms=1_000_000,
                )
                second = _v2_shadow_evaluation(
                    position_id="P2", opened_at_ms=900_001, status="OPEN", current_price=100.62,
                    mfe_pct=0.80, current_pnl_pct=0.62,
                    snapshot=snapshot, evaluated_at_ms=1_030_000,
                )
                with sqlite3.connect(db) as conn:
                    rows = conn.execute(
                        "select fast_gate,final_action from pp_decision_v2_observations order by evaluated_at_ms"
                    ).fetchall()
        self.assertEqual(first["fast_gate"], "COLD_START")
        self.assertEqual(second["fast_gate"], "FAST_DECISION")
        self.assertEqual(second["final_action"], "HOLD")
        self.assertAlmostEqual(second["elapsed_seconds"], 30.0)
        self.assertEqual(rows, [("COLD_START", "HOLD"), ("FAST_DECISION", "HOLD")])

    def test_v2_never_relaxes_v1_action(self):
        severity = {"HOLD": 0, "REDUCE": 1, "CLOSE": 2}
        cases = 0
        for mfe in (0.50, 0.80, 1.0, 1.58, 2.0, 5.0):
            for current_ratio in (1.0, 0.90, 0.80, 0.65, 0.50, 0.40, 0.0):
                current = mfe * current_ratio
                for previous_ratio in (1.0, 0.90, 0.80, 0.65, 0.50):
                    previous = mfe * previous_ratio
                    for elapsed in (15, 30, 60, 300):
                        for danger in range(7):
                            for status in ("OPEN", "REDUCED"):
                                r = evaluate_pp_decision_v2(
                                    mfe_pct=mfe, current_pnl_pct=current,
                                    previous_pnl_pct=previous, elapsed_seconds=elapsed,
                                    danger_score=danger, status=status,
                                )
                                self.assertGreaterEqual(
                                    severity[r["final_action"]],
                                    severity[r["base_v1_action"]],
                                )
                                cases += 1
        self.assertEqual(cases, 11760)


if __name__ == "__main__":
    unittest.main()
