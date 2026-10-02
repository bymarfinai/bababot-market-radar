from __future__ import annotations

import unittest

from research.wrong_direction.wd5h_stage4d import (
    FROZEN_HORIZON_MIN,
    FROZEN_THRESHOLD,
    close_path,
    close_side_return_pct,
    replay_from_market_entry,
    standardized_net,
)


class WD5HStage4DTests(unittest.TestCase):
    def kline(self, open_ms, close_ms, close):
        return [
            open_ms, "100", "101", "99", str(close), "10",
            close_ms, "0", 5, "5", "0", "0",
        ]

    def test_gate_is_frozen(self):
        self.assertEqual(FROZEN_HORIZON_MIN, 3)
        self.assertAlmostEqual(
            FROZEN_THRESHOLD, 0.6028066188778062
        )

    def test_close_path_starts_after_entry(self):
        rows = [
            self.kline(0, 59_999, 100),
            self.kline(60_000, 119_999, 101),
        ]
        got = close_path(rows, 60_500, 5)
        self.assertEqual(got, [(119_999, 101.0)])

    def test_long_side_return(self):
        self.assertAlmostEqual(
            close_side_return_pct("LONG", 100, 101), 1.0
        )

    def test_short_side_return(self):
        self.assertGreater(
            close_side_return_pct("SHORT", 100, 99), 1.0
        )

    def test_replay_win(self):
        rows = [
            self.kline(60_000, 119_999, 100.2),
            self.kline(120_000, 179_999, 100.8),
        ]
        got = replay_from_market_entry(
            side="LONG",
            entry_market=100.0,
            entry_ts_ms=60_500,
            rows=rows,
            fee_rate=0.0,
            slippage_bps=0.0,
            horizon_min=3,
        )
        self.assertEqual(got["label"], "META_WIN")
        self.assertGreater(got["actual_exit_net_usdt"], 2.5)

    def test_replay_loss(self):
        rows = [
            self.kline(60_000, 119_999, 99.8),
            self.kline(120_000, 179_999, 99.2),
        ]
        got = replay_from_market_entry(
            side="LONG",
            entry_market=100.0,
            entry_ts_ms=60_500,
            rows=rows,
            fee_rate=0.0,
            slippage_bps=0.0,
            horizon_min=3,
        )
        self.assertEqual(got["label"], "META_LOSS")

    def test_standardized_net(self):
        self.assertEqual(standardized_net("META_WIN", 0), 2.5)
        self.assertEqual(standardized_net("META_LOSS", 0), -2.5)
        self.assertEqual(standardized_net("TIMEOUT", 1.25), 1.25)


if __name__ == "__main__":
    unittest.main()
