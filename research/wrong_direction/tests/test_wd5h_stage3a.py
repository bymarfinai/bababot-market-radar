from __future__ import annotations

import unittest

from research.wrong_direction.wd5h_stage3a import (
    BARRIER_CONFIGS,
    PRIMARY_CONFIG,
    close_path,
    net_pnl_at_market,
    triple_barrier_label,
)


class WD5HStage3ATests(unittest.TestCase):
    def test_primary_config_is_frozen_wd4_style(self):
        self.assertEqual(PRIMARY_CONFIG["tp_pct"], 0.50)
        self.assertEqual(PRIMARY_CONFIG["sl_pct"], 0.50)
        self.assertEqual(PRIMARY_CONFIG["horizon_min"], 30)

    def test_all_barriers_are_symmetric(self):
        for config in BARRIER_CONFIGS:
            self.assertEqual(config["tp_pct"], config["sl_pct"])

    def test_net_pnl_long_increases_with_market(self):
        low = net_pnl_at_market(
            side="LONG",
            entry_market=100.0,
            exit_market=100.0,
            fee_rate=0.00075,
            slippage_bps=2.0,
        )
        high = net_pnl_at_market(
            side="LONG",
            entry_market=100.0,
            exit_market=101.0,
            fee_rate=0.00075,
            slippage_bps=2.0,
        )
        self.assertGreater(high, low)

    def test_net_pnl_short_increases_when_market_falls(self):
        flat = net_pnl_at_market(
            side="SHORT",
            entry_market=100.0,
            exit_market=100.0,
            fee_rate=0.00075,
            slippage_bps=2.0,
        )
        down = net_pnl_at_market(
            side="SHORT",
            entry_market=100.0,
            exit_market=99.0,
            fee_rate=0.00075,
            slippage_bps=2.0,
        )
        self.assertGreater(down, flat)

    def test_close_path_excludes_pre_entry_close(self):
        rows = [
            [0, "1", "1", "1", "100", "1", 59_999],
            [60_000, "1", "1", "1", "101", "1", 119_999],
        ]
        out = close_path(rows, 60_500, 2)
        self.assertEqual(out, [(119_999, 101.0)])

    def test_meta_win_when_tp_first(self):
        pos = {
            "side": "LONG",
            "opened_at_ms": 60_500,
            "entry_price": 100.0,
            "raw_json": {
                "entry_market_price": 100.0,
                "fee_rate": 0.0,
                "slippage_bps": 0.0,
            },
        }
        rows = [
            [60_000, "100", "101", "100", "100.2", "1", 119_999],
            [120_000, "100", "101", "100", "100.6", "1", 179_999],
        ]
        out = triple_barrier_label(
            pos, rows, tp_pct=0.5, sl_pct=0.5, horizon_min=3
        )
        self.assertEqual(out["label"], "META_WIN")

    def test_meta_loss_when_sl_first(self):
        pos = {
            "side": "LONG",
            "opened_at_ms": 60_500,
            "entry_price": 100.0,
            "raw_json": {
                "entry_market_price": 100.0,
                "fee_rate": 0.0,
                "slippage_bps": 0.0,
            },
        }
        rows = [
            [60_000, "100", "100", "99", "99.4", "1", 119_999],
            [120_000, "99", "101", "99", "100.8", "1", 179_999],
        ]
        out = triple_barrier_label(
            pos, rows, tp_pct=0.5, sl_pct=0.5, horizon_min=3
        )
        self.assertEqual(out["label"], "META_LOSS")

    def test_timeout_when_no_barrier(self):
        pos = {
            "side": "SHORT",
            "opened_at_ms": 60_500,
            "entry_price": 100.0,
            "raw_json": {
                "entry_market_price": 100.0,
                "fee_rate": 0.0,
                "slippage_bps": 0.0,
            },
        }
        rows = [
            [60_000, "100", "100", "100", "100.1", "1", 119_999],
            [120_000, "100", "100", "100", "99.9", "1", 179_999],
        ]
        out = triple_barrier_label(
            pos, rows, tp_pct=0.5, sl_pct=0.5, horizon_min=3
        )
        self.assertEqual(out["label"], "TIMEOUT")


if __name__ == "__main__":
    unittest.main()
