from __future__ import annotations

import unittest

from market_radar.scheduler import next_five_minute_run_ms
from market_radar.stage1_scanner import (
    filter_usdt_perpetuals,
    latest_closed_kline,
    snapshot_from_kline,
)


class Stage1ScannerTests(unittest.TestCase):
    def test_universe_is_all_trading_usdt_perpetuals(self):
        exchange = {
            "symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "ETHUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "ABCUSDT", "status": "BREAK", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "BTCUSDC", "status": "TRADING", "quoteAsset": "USDC", "contractType": "PERPETUAL"},
                {"symbol": "BTCUSDT_260925", "status": "TRADING", "quoteAsset": "USDT", "contractType": "CURRENT_QUARTER"},
            ]
        }
        self.assertEqual(filter_usdt_perpetuals(exchange), ["BTCUSDT", "ETHUSDT"])

    def test_latest_closed_kline_rejects_in_progress_candle(self):
        rows = [
            [0, "1", "2", "0.5", "1.5", "10", 299_999, "15", 10, "6", "9", "0"],
            [300_000, "1.5", "2.5", "1", "2", "20", 599_999, "40", 20, "12", "24", "0"],
            [600_000, "2", "3", "1.5", "2.5", "30", 899_999, "75", 30, "20", "50", "0"],
        ]
        selected = latest_closed_kline(rows, now_ms=700_000)
        self.assertEqual(int(selected[6]), 599_999)

    def test_snapshot_uses_closed_candle_close_as_price(self):
        row = [300_000, "10", "13", "9", "12", "100", 599_999, "1200", 45, "60", "720", "0"]
        ticker = {"quoteVolume": "987654", "priceChangePercent": "2.4"}
        snap = snapshot_from_kline("TESTUSDT", row, ticker)
        self.assertEqual(snap.close, 12.0)
        self.assertEqual(snap.candle_close_time_ms, 599_999)
        self.assertEqual(snap.quote_volume_5m, 1200.0)
        self.assertEqual(snap.taker_buy_quote_volume_5m, 720.0)

    def test_scheduler_uses_next_boundary_plus_offset(self):
        now_ms = 2 * 60 * 1000
        self.assertEqual(next_five_minute_run_ms(now_ms, offset_seconds=3), 303_000)

    def test_malformed_or_ineligible_symbols_are_excluded_without_ranking(self):
        exchange = {
            "symbols": [
                {"symbol": "ZZZUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "AAAUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": "AAAUSDT", "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
                {"symbol": None, "status": "TRADING", "quoteAsset": "USDT", "contractType": "PERPETUAL"},
            ]
        }
        self.assertEqual(filter_usdt_perpetuals(exchange), ["AAAUSDT", "ZZZUSDT"])

    def test_exact_close_timestamp_is_not_treated_as_closed(self):
        rows = [
            [0, "1", "2", "0.5", "1.5", "10", 299_999, "15", 10, "6", "9", "0"],
            [300_000, "1.5", "2.5", "1", "2", "20", 599_999, "40", 20, "12", "24", "0"],
        ]
        selected = latest_closed_kline(rows, now_ms=599_999)
        self.assertEqual(int(selected[6]), 299_999)


if __name__ == "__main__":
    unittest.main()
