from __future__ import annotations

import unittest

from research.profit_protection_v3.stage1_capture_frontier import (
    Observation,
    exit_fill_price,
    gross_pnl,
    market_price_for_roi,
    replay_static_floor,
)


class PPV3Stage1CaptureFrontierTests(unittest.TestCase):
    def test_long_short_fill_symmetry(self) -> None:
        self.assertAlmostEqual(exit_fill_price(side="LONG", market_price=100.0, slippage_bps=2.0), 99.98)
        self.assertAlmostEqual(exit_fill_price(side="SHORT", market_price=100.0, slippage_bps=2.0), 100.02)

    def test_market_price_for_roi(self) -> None:
        self.assertAlmostEqual(market_price_for_roi(side="LONG", entry_price=100.0, roi_pct=0.8), 100.8)
        self.assertAlmostEqual(market_price_for_roi(side="SHORT", entry_price=100.0, roi_pct=0.8), 99.2)

    def test_gross_pnl_symmetry(self) -> None:
        self.assertAlmostEqual(gross_pnl(side="LONG", quantity=5.0, entry_price=100.0, exit_price=101.0), 5.0)
        self.assertAlmostEqual(gross_pnl(side="SHORT", quantity=5.0, entry_price=100.0, exit_price=99.0), 5.0)

    def test_does_not_arm_on_hidden_mfe(self) -> None:
        stream = [
            Observation(1, 100.10, 0.10),
            Observation(2, 100.20, 0.20),
            Observation(3, 100.05, 0.05),
        ]
        out = replay_static_floor(stream, ratio=0.80, arm_pct=0.30)
        self.assertFalse(out.armed)
        self.assertFalse(out.triggered)

    def test_running_observed_peak_ratchets_and_triggers_later(self) -> None:
        stream = [
            Observation(1, 100.30, 0.30),
            Observation(2, 100.50, 0.50),
            Observation(3, 100.46, 0.46),
            Observation(4, 100.39, 0.39),
        ]
        out = replay_static_floor(stream, ratio=0.80, arm_pct=0.30)
        self.assertTrue(out.armed)
        self.assertTrue(out.triggered)
        self.assertEqual(out.arm_at_ms, 1)
        self.assertEqual(out.trigger_at_ms, 4)
        self.assertAlmostEqual(out.running_peak_pct, 0.50)
        self.assertAlmostEqual(out.trigger_current_pnl_pct, 0.39)

    def test_exact_floor_crossing_triggers(self) -> None:
        stream = [
            Observation(1, 100.40, 0.40),
            Observation(2, 100.32, 0.32),
        ]
        out = replay_static_floor(stream, ratio=0.80, arm_pct=0.30)
        self.assertTrue(out.triggered)
        self.assertEqual(out.trigger_at_ms, 2)


if __name__ == "__main__":
    unittest.main()
