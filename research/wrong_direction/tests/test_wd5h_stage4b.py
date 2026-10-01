from __future__ import annotations

import unittest

from research.wrong_direction.wd5h_stage4b import (
    ROBUST_MIN_SEPARATION,
    STRONG_MIN_SEPARATION,
    chronological_splits,
    feature_family,
    static_key_for_temporal,
)


class WD5HStage4BTests(unittest.TestCase):
    def test_split_is_60_20_20(self):
        rows = [{"gate_checked_at_ms": i} for i in range(100)]
        s = chronological_splits(rows)
        self.assertEqual(len(s["train"]), 60)
        self.assertEqual(len(s["validation"]), 20)
        self.assertEqual(len(s["test"]), 20)

    def test_family_confirmation(self):
        self.assertEqual(
            feature_family("t1_confirm_side_return_pct"),
            "CONFIRMATION_PATH",
        )

    def test_family_delta(self):
        self.assertEqual(
            feature_family("t2_delta_micro_side_ret_3m"),
            "DELTA_VS_T0",
        )

    def test_family_market(self):
        self.assertEqual(
            feature_family("t3_f_f_coin_minus_market_5m"),
            "MARKET_RELATIVE",
        )

    def test_static_mapping(self):
        self.assertEqual(
            static_key_for_temporal("t2_f_micro_side_ret_3m"),
            "f_micro_side_ret_3m",
        )
        self.assertIsNone(
            static_key_for_temporal("t2_confirm_side_return_pct")
        )

    def test_robust_is_below_strong(self):
        self.assertLess(
            ROBUST_MIN_SEPARATION,
            STRONG_MIN_SEPARATION,
        )


if __name__ == "__main__":
    unittest.main()
