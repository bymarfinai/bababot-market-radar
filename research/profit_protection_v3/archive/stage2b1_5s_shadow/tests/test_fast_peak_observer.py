from __future__ import annotations

import unittest

from research.profit_protection_v3.archive.stage2b1_5s_shadow.profit_protection_v3_fast_observer import (
    PeakState,
    advance_peak_state,
    side_return_pct,
)


class PPV3Stage2B1FastPeakObserverTests(unittest.TestCase):
    def test_side_return_long_short_symmetry(self) -> None:
        self.assertAlmostEqual(side_return_pct("LONG", 100.0, 101.0), 1.0)
        self.assertAlmostEqual(side_return_pct("SHORT", 100.0, 99.0), 1.0)

    def test_first_sample_sets_running_peak(self) -> None:
        state, metrics = advance_peak_state(
            current_pnl_pct=0.40,
            observed_at_ms=10_000,
            arm_pct=0.30,
            previous=None,
        )
        self.assertAlmostEqual(state.running_peak_pct, 0.40)
        self.assertEqual(state.running_peak_at_ms, 10_000)
        self.assertTrue(metrics["armed"])
        self.assertAlmostEqual(metrics["giveback_ratio"], 0.0)

    def test_new_high_ratchets_peak_timestamp(self) -> None:
        previous = PeakState(
            running_peak_pct=0.40,
            running_peak_at_ms=10_000,
            previous_pnl_pct=0.35,
            previous_observed_at_ms=15_000,
        )
        state, metrics = advance_peak_state(
            current_pnl_pct=0.55,
            observed_at_ms=20_000,
            arm_pct=0.30,
            previous=previous,
        )
        self.assertAlmostEqual(state.running_peak_pct, 0.55)
        self.assertEqual(state.running_peak_at_ms, 20_000)
        self.assertAlmostEqual(metrics["delta_pnl_pct_points"], 0.20)
        self.assertEqual(metrics["sample_gap_ms"], 5_000)
        self.assertAlmostEqual(metrics["seconds_since_peak"], 0.0)

    def test_retracement_preserves_peak_and_computes_giveback(self) -> None:
        previous = PeakState(
            running_peak_pct=1.00,
            running_peak_at_ms=10_000,
            previous_pnl_pct=1.00,
            previous_observed_at_ms=10_000,
        )
        state, metrics = advance_peak_state(
            current_pnl_pct=0.80,
            observed_at_ms=15_000,
            arm_pct=0.30,
            previous=previous,
        )
        self.assertAlmostEqual(state.running_peak_pct, 1.00)
        self.assertEqual(state.running_peak_at_ms, 10_000)
        self.assertAlmostEqual(metrics["giveback_ratio"], 0.20)
        self.assertAlmostEqual(metrics["seconds_since_peak"], 5.0)
        self.assertAlmostEqual(metrics["delta_pnl_pct_points"], -0.20)

    def test_arm_state_uses_running_peak_not_current_pnl(self) -> None:
        previous = PeakState(
            running_peak_pct=0.35,
            running_peak_at_ms=10_000,
            previous_pnl_pct=0.35,
            previous_observed_at_ms=10_000,
        )
        _, metrics = advance_peak_state(
            current_pnl_pct=0.10,
            observed_at_ms=15_000,
            arm_pct=0.30,
            previous=previous,
        )
        self.assertTrue(metrics["armed"])


if __name__ == "__main__":
    unittest.main()
