from __future__ import annotations

import unittest

from market_radar.profit_protection_v1 import (
    PP_DECISION_V1_FINAL_POLICY,
    PP_DECISION_V1_VERSION,
    evaluate_pp_decision_v1,
)


class ProfitProtectionV1FrozenTests(unittest.TestCase):
    def test_policy_identity(self) -> None:
        self.assertEqual(PP_DECISION_V1_VERSION, "pp-decision-v1-final-frozen")
        self.assertEqual(PP_DECISION_V1_FINAL_POLICY["sub1_arm_min_roi_pct"], 0.50)
        self.assertEqual(PP_DECISION_V1_FINAL_POLICY["handoff_roi_pct"], 1.00)
        self.assertEqual(PP_DECISION_V1_FINAL_POLICY["ge1_hard_close_giveback_ratio"], 0.60)

    def test_sub1_thresholds(self) -> None:
        peak = 100.0
        cases = [
            (0.80, 0.2999, 6, "OPEN", "HOLD", "ARMED_SUB1"),
            (0.80, 0.30, 4, "OPEN", "REDUCE", "WATCH"),
            (0.80, 0.50, 1, "OPEN", "HOLD", "MANDATORY_DECISION"),
            (0.80, 0.50, 2, "OPEN", "REDUCE", "MANDATORY_DECISION"),
            (0.80, 0.50, 4, "OPEN", "CLOSE", "MANDATORY_DECISION"),
            (0.80, 1.00, 0, "OPEN", "CLOSE", "HARD_STOP"),
        ]
        for peak_roi, giveback, danger, status, expected_action, expected_gate in cases:
            action, meta = evaluate_pp_decision_v1(
                peak_roi=peak_roi,
                economic=peak * (1.0 - giveback),
                peak=peak,
                danger_score=danger,
                status=status,
            )
            self.assertEqual((action, meta["gate"], meta["zone"]), (expected_action, expected_gate, "SUB1"))

    def test_ge1_thresholds(self) -> None:
        peak = 100.0
        cases = [
            (1.58, 0.2499, 6, "OPEN", "HOLD", "ARMED_GE1"),
            (1.58, 0.25, 4, "OPEN", "REDUCE", "WATCH"),
            (1.58, 0.35, 1, "OPEN", "HOLD", "MANDATORY_DECISION"),
            (1.58, 0.35, 2, "OPEN", "REDUCE", "MANDATORY_DECISION"),
            (1.58, 0.50, 0, "OPEN", "REDUCE", "FORCE_PROTECT"),
            (1.58, 0.60, 0, "OPEN", "CLOSE", "HARD_CLOSE"),
            (1.58, 0.50, 0, "REDUCED", "CLOSE", "FORCE_PROTECT"),
        ]
        for peak_roi, giveback, danger, status, expected_action, expected_gate in cases:
            action, meta = evaluate_pp_decision_v1(
                peak_roi=peak_roi,
                economic=peak * (1.0 - giveback),
                peak=peak,
                danger_score=danger,
                status=status,
            )
            self.assertEqual((action, meta["gate"], meta["zone"]), (expected_action, expected_gate, "GE1"))

    def test_full_state_space_is_deterministic(self) -> None:
        peak_rois = [0.0, 0.49, 0.50, 0.75, 0.9999, 1.0, 1.58, 2.0, 5.0, 10.0]
        givebacks = [0.0, 0.2499, 0.25, 0.2999, 0.30, 0.3499, 0.35, 0.4999, 0.50, 0.5999, 0.60, 0.9999, 1.0, 1.25]
        actions = {"HOLD", "REDUCE", "CLOSE"}
        cases = 0
        for peak_roi in peak_rois:
            for giveback in givebacks:
                for danger in range(7):
                    for status in ("OPEN", "REDUCED"):
                        action, meta = evaluate_pp_decision_v1(
                            peak_roi=peak_roi,
                            economic=100.0 * (1.0 - giveback),
                            peak=100.0,
                            danger_score=danger,
                            status=status,
                        )
                        self.assertIn(action, actions)
                        self.assertIn(meta["zone"], {"SUB1", "GE1"})
                        self.assertEqual(meta["danger_score"], danger)
                        if status == "REDUCED":
                            self.assertNotEqual(action, "REDUCE")
                        cases += 1
        self.assertEqual(cases, 1960)


if __name__ == "__main__":
    unittest.main()
