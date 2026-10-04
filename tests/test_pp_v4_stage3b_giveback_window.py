from __future__ import annotations

import unittest

from research.profit_protection_v4.stage3b_giveback_window_anatomy import (
    classify_crossing_outcome,
    peak_regime,
)


class PPV4Stage3BGivebackWindowTests(unittest.TestCase):
    def test_crossing_recovers_when_future_new_high_exists(self):
        self.assertEqual(
            classify_crossing_outcome([0.9, 1.01], 1.0),
            "RECOVERED_NEW_HIGH",
        )

    def test_crossing_is_final_without_future_new_high(self):
        self.assertEqual(
            classify_crossing_outcome([0.9, 0.8], 1.0),
            "FINAL_REVERSAL",
        )

    def test_peak_regimes(self):
        self.assertEqual(peak_regime(0.99), "LT1")
        self.assertEqual(peak_regime(1.20), "1_TO_1_5")
        self.assertEqual(peak_regime(2.00), "1_5_TO_3")
        self.assertEqual(peak_regime(3.00), "GE3")


if __name__ == "__main__":
    unittest.main()
