from __future__ import annotations

import unittest

from research.wrong_direction.wd4_resolution import (
    _entry_fill,
    _exit_fill,
    _gross,
    _path_metrics,
    classify_resolution,
)


class WD4ResolutionTests(unittest.TestCase):
    def test_fill_direction(self):
        self.assertAlmostEqual(_entry_fill("LONG", 100.0, 2.0), 100.02)
        self.assertAlmostEqual(_entry_fill("SHORT", 100.0, 2.0), 99.98)
        self.assertAlmostEqual(_exit_fill("LONG", 100.0, 2.0), 99.98)
        self.assertAlmostEqual(_exit_fill("SHORT", 100.0, 2.0), 100.02)

    def test_gross(self):
        self.assertEqual(_gross("LONG", 2, 100, 101), 2)
        self.assertEqual(_gross("SHORT", 2, 100, 99), 2)

    def test_path_metrics_strong_win_after_fees(self):
        result = _path_metrics(
            side="LONG",
            entry_market=100.0,
            path=[(1, 100.2), (2, 101.0)],
            fee_rate=0.00075,
            slippage_bps=2.0,
        )
        self.assertTrue(result["positive_win"])
        self.assertTrue(result["strong_win_0p5"])

    def test_classify_resolution_priority(self):
        empty = {
            "positive_win": False,
            "strong_win_0p5": False,
            "robust_win_1p0": False,
        }
        strong = {
            "positive_win": True,
            "strong_win_0p5": True,
            "robust_win_1p0": False,
        }
        paths = {
            "opposite_entry": dict(empty),
            "flip_1m": dict(strong),
            "flip_3m": dict(strong),
        }
        self.assertEqual(classify_resolution(paths), "FLIP_1M_STRONG_WIN")

    def test_classify_no_trade_required(self):
        empty = {
            "positive_win": False,
            "strong_win_0p5": False,
            "robust_win_1p0": False,
        }
        paths = {
            "opposite_entry": dict(empty),
            "flip_1m": dict(empty),
            "flip_3m": dict(empty),
        }
        self.assertEqual(classify_resolution(paths), "NO_TRADE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
