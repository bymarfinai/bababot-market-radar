from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_radar.stage6_validation import (
    POLICIES,
    _evaluate_lane,
    _policy_ids_for_entry,
    _pp_decision_unified,
)


class PPDecisionV1FinalShadowTests(unittest.TestCase):
    def setUp(self):
        self.base = POLICIES["PP-DECISION-V1"]
        self.final = POLICIES["PP-DECISION-V1-FINAL"]

    def test_final_policy_is_exact_frozen_copy(self):
        self.assertEqual(self.final, self.base)

    def test_final_decision_parity_across_state_space(self):
        peak_rois = [0.0, 0.49, 0.50, 0.75, 0.9999, 1.0, 1.58, 2.0, 5.0, 10.0]
        givebacks = [0.0, 0.2499, 0.25, 0.2999, 0.30, 0.3499, 0.35, 0.4999, 0.50, 0.5999, 0.60, 0.9999, 1.0, 1.25]
        cases = 0
        for peak_roi in peak_rois:
            for giveback in givebacks:
                peak = 100.0
                economic = peak * (1.0 - giveback)
                for danger in range(7):
                    for status in ("OPEN", "REDUCED"):
                        evidence = {"danger_score": danger}
                        a1, m1 = _pp_decision_unified(
                            self.base, peak_roi=peak_roi, economic=economic, peak=peak,
                            evidence=evidence, status=status,
                        )
                        a2, m2 = _pp_decision_unified(
                            self.final, peak_roi=peak_roi, economic=economic, peak=peak,
                            evidence=evidence, status=status,
                        )
                        self.assertEqual((a2, m2), (a1, m1))
                        cases += 1
        self.assertEqual(cases, 1960)

    def test_final_lane_has_strict_clean_start_boundary(self):
        start = 9_999_000
        env = {
            "V5_0_SHADOW_ENABLED": "false",
            "PP_DECISION_STAGE2_ENABLED": "false",
            "PP_DECISION_STAGE3_ENABLED": "true",
            "PP_DECISION_STAGE3_START_MS": "1",
            "PP_DECISION_STAGE5_ENABLED": "true",
            "PP_DECISION_STAGE5_START_MS": str(start),
        }
        with patch.dict(os.environ, env, clear=False):
            at_boundary = _policy_ids_for_entry(start)
            after_boundary = _policy_ids_for_entry(start + 1)
        self.assertNotIn("PP-DECISION-V1-FINAL", at_boundary)
        self.assertIn("PP-DECISION-V1-FINAL", after_boundary)
        self.assertIn("PP-DECISION-V1", at_boundary)

    def test_final_lane_stateful_replay_matches_stage3_lane(self):
        trade = {
            "side": "LONG", "entry_price": 100.0, "initial_quantity": 5.0,
            "initial_notional": 500.0, "entry_fee_total": 0.375,
        }
        def lane(policy_id):
            return {
                "policy_id": policy_id, "status": "OPEN", "remaining_quantity": 5.0,
                "realized_gross": 0.0, "realized_net": 0.0, "allocated_entry_fee": 0.0,
                "exit_fees": 0.0, "policy_peak_pnl": 0.0, "policy_peak_at_ms": None,
                "profit_floor": None, "action_count": 0, "trigger_count": 0,
                "closed_at_ms": None, "exit_price": None, "close_reason": None,
            }
        features = [
            {"candle_close_ms": 1_000_000, "close": 100.90, "side_ret3": 0.20, "taker_strength": 0.10, "micro_against": False, "oi_change": 0.0, "rv15": 0.05},
            {"candle_close_ms": 1_060_000, "close": 101.80, "side_ret3": 0.25, "taker_strength": 0.10, "micro_against": False, "oi_change": 0.0, "rv15": 0.05},
            {"candle_close_ms": 1_120_000, "close": 101.10, "side_ret3": -0.20, "taker_strength": 0.00, "micro_against": False, "oi_change": 0.0, "rv15": 0.05},
            {"candle_close_ms": 1_180_000, "close": 100.65, "side_ret3": -0.30, "taker_strength": -0.10, "micro_against": True, "oi_change": 0.10, "rv15": 0.05},
        ]
        left = lane("PP-DECISION-V1")
        right = lane("PP-DECISION-V1-FINAL")
        for feature in features:
            left, ev_left = _evaluate_lane(trade=trade, lane=left, feature=feature)
            right, ev_right = _evaluate_lane(trade=trade, lane=right, feature=feature)
            for key in (
                "status", "remaining_quantity", "realized_gross", "realized_net",
                "allocated_entry_fee", "exit_fees", "policy_peak_pnl",
                "policy_peak_at_ms", "profit_floor", "action_count", "trigger_count",
                "closed_at_ms", "exit_price", "close_reason",
            ):
                self.assertEqual(right[key], left[key], msg=(key, feature))
            self.assertEqual(ev_right, ev_left)


if __name__ == "__main__":
    unittest.main()
