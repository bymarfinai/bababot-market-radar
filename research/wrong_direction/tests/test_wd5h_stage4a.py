from __future__ import annotations

import unittest

from research.wrong_direction.wd5h_stage4a import (
    HORIZONS_MIN,
    merge_closed_rows,
    new_closed_rows,
    selected_taker_share,
    temporal_path_features,
)


class WD5HStage4ATests(unittest.TestCase):
    def kline(self, open_ms, close_ms, o, h, l, c, vol=10, trades=5, taker=6):
        return [
            open_ms, str(o), str(h), str(l), str(c), str(vol),
            close_ms, "0", trades, str(taker), "0", "0",
        ]

    def test_horizons_are_frozen_1_2_3(self):
        self.assertEqual(HORIZONS_MIN, (1, 2, 3))

    def test_merge_closed_rows_dedupes(self):
        a = self.kline(0, 59_999, 100, 101, 99, 100)
        b = self.kline(60_000, 119_999, 100, 102, 99, 101)
        got = merge_closed_rows([a], [a, b], 119_999)
        self.assertEqual(len(got), 2)

    def test_merge_excludes_future_candle(self):
        a = self.kline(0, 59_999, 100, 101, 99, 100)
        b = self.kline(60_000, 119_999, 100, 102, 99, 101)
        got = merge_closed_rows([a], [b], 100_000)
        self.assertEqual(len(got), 1)

    def test_new_rows_are_after_gate_and_before_target(self):
        a = self.kline(0, 59_999, 100, 101, 99, 100)
        b = self.kline(60_000, 119_999, 100, 102, 99, 101)
        c = self.kline(120_000, 179_999, 101, 103, 100, 102)
        got = new_closed_rows([a, b, c], 60_500, 180_500)
        self.assertEqual(got, [b, c])

    def test_selected_taker_share_long_short(self):
        rows = [self.kline(0, 59_999, 1, 1, 1, 1, vol=10, taker=7)]
        self.assertAlmostEqual(selected_taker_share(rows, "LONG"), 0.7)
        self.assertAlmostEqual(selected_taker_share(rows, "SHORT"), 0.3)

    def test_temporal_long_path(self):
        rows = [
            self.kline(0, 59_999, 100, 102, 99, 101),
            self.kline(60_000, 119_999, 101, 103, 100, 102),
        ]
        got = temporal_path_features(rows, side="LONG", gate_price=100)
        self.assertEqual(got["confirm_closed_bars"], 2)
        self.assertAlmostEqual(got["confirm_side_return_pct"], 2.0)
        self.assertAlmostEqual(got["confirm_mfe_pct"], 3.0)
        self.assertAlmostEqual(got["confirm_mae_pct"], -1.0)

    def test_temporal_short_path(self):
        rows = [
            self.kline(0, 59_999, 100, 101, 98, 99),
        ]
        got = temporal_path_features(rows, side="SHORT", gate_price=100)
        self.assertGreater(got["confirm_side_return_pct"], 0)
        self.assertGreater(got["confirm_mfe_pct"], 0)
        self.assertLess(got["confirm_mae_pct"], 0)


if __name__ == "__main__":
    unittest.main()
