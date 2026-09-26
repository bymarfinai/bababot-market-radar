from __future__ import annotations

import unittest

from market_radar.market_context import attach_market_context
from market_radar.models import MovementDetection, SymbolSnapshot
from market_radar.regime_context import VALID_REGIMES, classify_regime


def make_5m_rows(
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    quote_volumes: list[float] | None = None,
    taker_buy_quote: list[float] | None = None,
) -> list[list]:
    highs = highs or [c + 0.2 for c in closes]
    lows = lows or [c - 0.2 for c in closes]
    quote_volumes = quote_volumes or [1000.0] * len(closes)
    taker_buy_quote = taker_buy_quote or [500.0] * len(closes)

    rows = []
    for i, close in enumerate(closes):
        open_time = i * 300_000
        close_time = (i + 1) * 300_000 - 1
        previous = closes[i - 1] if i else close
        rows.append(
            [
                open_time,
                str(previous),
                str(highs[i]),
                str(lows[i]),
                str(close),
                "10",
                close_time,
                str(quote_volumes[i]),
                100,
                "5",
                str(taker_buy_quote[i]),
                "0",
            ]
        )
    return rows


def make_4h_rows(n: int = 60) -> list[list]:
    rows = []
    price = 100.0
    for i in range(n):
        # Gentle deterministic zig-zag with upward drift.
        price += 0.8 if i % 2 == 0 else -0.2
        open_time = i * 4 * 60 * 60 * 1000
        close_time = (i + 1) * 4 * 60 * 60 * 1000 - 1
        rows.append(
            [
                open_time,
                str(price - 0.1),
                str(price + 0.6),
                str(price - 0.6),
                str(price),
                "100",
                close_time,
                "10000",
                100,
                "50",
                "5000",
                "0",
            ]
        )
    return rows


def moving_candidate(candle_close_time_ms: int) -> MovementDetection:
    return MovementDetection(
        symbol="TESTUSDT",
        detector_version="stage2-v1",
        candle_close_time_ms=candle_close_time_ms,
        movement_state="EARLY_MOVEMENT",
        direction_hint="UP",
        is_moving=True,
        ret_5m_pct=0.50,
        ret_15m_pct=1.00,
        ret_1h_pct=2.00,
        ret_24h_pct=5.00,
        median_abs_ret_5m_pct=0.10,
        return_expansion_ratio=5.0,
        volume_ratio=2.0,
        range_ratio=2.0,
        trades_ratio=2.0,
        directional_persistence=True,
        evidence_count=5,
        reasons=(),
        stage="IGNITION",
        stage_classifier_version="stage3-v1",
        long_score=80.0,
        short_score=10.0,
        score_gap=70.0,
        score_edge=70.0,
        direction_score_version="stage4-v1",
    )


class Stage5ContextTests(unittest.TestCase):
    def test_context_uses_raw_oi_not_usd_valued_oi(self):
        closes = [100.0] * 24 + [101.0]
        rows = make_5m_rows(closes)
        close_ts = int(rows[-1][6])
        snapshot = SymbolSnapshot(
            symbol="TESTUSDT",
            candle_open_time_ms=int(rows[-1][0]),
            candle_close_time_ms=close_ts,
            open=100.0,
            high=101.2,
            low=99.8,
            close=101.0,
            base_volume_5m=10.0,
            quote_volume_5m=1000.0,
            trades_5m=100,
            taker_buy_base_volume_5m=5.0,
            taker_buy_quote_volume_5m=700.0,
            quote_volume_24h=50_000_000.0,
            price_change_pct_24h=5.0,
        )

        oi_hist = [
            {
                "timestamp": close_ts - 30 * 60_000,
                "sumOpenInterest": "100",
                "sumOpenInterestValue": "9000000",
            },
            {
                "timestamp": close_ts - 5 * 60_000,
                "sumOpenInterest": "110",
                "sumOpenInterestValue": "1000000",
            },
        ]

        regime = classify_regime(
            make_4h_rows(60),
            now_ms=60 * 4 * 60 * 60 * 1000 + 1,
        )

        result = attach_market_context(
            movement=moving_candidate(close_ts),
            snapshot=snapshot,
            klines_5m=rows,
            now_ms=close_ts + 1,
            oi_hist=oi_hist,
            premium={"lastFundingRate": "0.0001"},
            regime=regime,
        )

        ctx = result.market_context
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.raw_oi_first, 100.0)
        self.assertEqual(ctx.raw_oi_last, 110.0)
        self.assertAlmostEqual(ctx.raw_oi_change_pct, 10.0)
        self.assertEqual(ctx.oi_interpretation, "FRESH_LONG_PARTICIPATION")

    def test_future_oi_observation_is_rejected(self):
        rows = make_5m_rows([100.0] * 24 + [101.0])
        close_ts = int(rows[-1][6])
        snapshot = SymbolSnapshot(
            symbol="TESTUSDT",
            candle_open_time_ms=int(rows[-1][0]),
            candle_close_time_ms=close_ts,
            open=100.0, high=101.2, low=99.8, close=101.0,
            base_volume_5m=10.0, quote_volume_5m=1000.0, trades_5m=100,
            taker_buy_base_volume_5m=5.0, taker_buy_quote_volume_5m=700.0,
            quote_volume_24h=50_000_000.0, price_change_pct_24h=5.0,
        )
        oi_hist = [
            {"timestamp": close_ts - 10 * 60_000, "sumOpenInterest": "100"},
            {"timestamp": close_ts - 5 * 60_000, "sumOpenInterest": "110"},
            {"timestamp": close_ts + 5 * 60_000, "sumOpenInterest": "999"},
        ]

        result = attach_market_context(
            movement=moving_candidate(close_ts),
            snapshot=snapshot,
            klines_5m=rows,
            now_ms=close_ts + 1,
            oi_hist=oi_hist,
            premium={"lastFundingRate": "0"},
            regime=None,
        )
        self.assertEqual(result.market_context.raw_oi_last, 110.0)

    def test_breakout_and_taker_flow_are_from_closed_signal_candle(self):
        closes = [100.0] * 24 + [102.0]
        highs = [101.0] * 24 + [102.2]
        lows = [99.0] * 24 + [99.8]
        vols = [1000.0] * 24 + [2000.0]
        taker = [500.0] * 24 + [1400.0]
        rows = make_5m_rows(closes, highs, lows, vols, taker)
        close_ts = int(rows[-1][6])

        snapshot = SymbolSnapshot(
            symbol="TESTUSDT",
            candle_open_time_ms=int(rows[-1][0]),
            candle_close_time_ms=close_ts,
            open=100.0, high=102.2, low=99.8, close=102.0,
            base_volume_5m=10.0, quote_volume_5m=2000.0, trades_5m=100,
            taker_buy_base_volume_5m=5.0, taker_buy_quote_volume_5m=1400.0,
            quote_volume_24h=50_000_000.0, price_change_pct_24h=5.0,
        )

        result = attach_market_context(
            movement=moving_candidate(close_ts),
            snapshot=snapshot,
            klines_5m=rows,
            now_ms=close_ts + 1,
            oi_hist=[
                {"timestamp": close_ts - 10 * 60_000, "sumOpenInterest": "100"},
                {"timestamp": close_ts - 5 * 60_000, "sumOpenInterest": "101"},
            ],
            premium={"lastFundingRate": "0.0002"},
            regime=None,
        )

        ctx = result.market_context
        self.assertTrue(ctx.breakout)
        self.assertEqual(ctx.structure_status, "BREAKOUT")
        self.assertAlmostEqual(ctx.taker_buy_share, 0.7)
        self.assertEqual(ctx.taker_bias, "BUY")
        self.assertAlmostEqual(ctx.taker_buy_sell_ratio, 1400.0 / 600.0, places=5)
        self.assertAlmostEqual(ctx.funding_rate, 0.0002)

    def test_failed_breakout_is_distinct_from_breakout(self):
        closes = [100.0] * 24 + [100.5]
        highs = [101.0] * 24 + [102.0]
        lows = [99.0] * 25
        rows = make_5m_rows(closes, highs, lows)
        close_ts = int(rows[-1][6])

        snapshot = SymbolSnapshot(
            symbol="TESTUSDT",
            candle_open_time_ms=int(rows[-1][0]),
            candle_close_time_ms=close_ts,
            open=100.0, high=102.0, low=99.0, close=100.5,
            base_volume_5m=10.0, quote_volume_5m=1000.0, trades_5m=100,
            taker_buy_base_volume_5m=5.0, taker_buy_quote_volume_5m=500.0,
            quote_volume_24h=50_000_000.0, price_change_pct_24h=1.0,
        )

        result = attach_market_context(
            movement=moving_candidate(close_ts),
            snapshot=snapshot,
            klines_5m=rows,
            now_ms=close_ts + 1,
            oi_hist=[
                {"timestamp": close_ts - 10 * 60_000, "sumOpenInterest": "100"},
                {"timestamp": close_ts - 5 * 60_000, "sumOpenInterest": "101"},
            ],
            premium={"lastFundingRate": "0"},
            regime=None,
        )

        ctx = result.market_context
        self.assertFalse(ctx.breakout)
        self.assertTrue(ctx.failed_breakout)
        self.assertEqual(ctx.structure_status, "FAILED_BREAKOUT")

    def test_open_4h_candle_cannot_change_regime(self):
        closed = make_4h_rows(60)
        now_ms = 60 * 4 * 60 * 60 * 1000 + 1

        baseline = classify_regime(closed, now_ms=now_ms)
        self.assertIn(baseline.regime, VALID_REGIMES)

        current_open = [
            60 * 4 * 60 * 60 * 1000,
            "100",
            "1000",
            "1",
            "900",
            "100000",
            61 * 4 * 60 * 60 * 1000 - 1,
            "99999999",
            99999,
            "99999",
            "99999999",
            "0",
        ]

        with_open = classify_regime(closed + [current_open], now_ms=now_ms)
        self.assertEqual(with_open.regime, baseline.regime)
        self.assertEqual(
            with_open.regime_bar_close_time_ms,
            baseline.regime_bar_close_time_ms,
        )

    def test_stage5_does_not_create_final_trade_decision(self):
        rows = make_5m_rows([100.0] * 24 + [101.0])
        close_ts = int(rows[-1][6])
        snapshot = SymbolSnapshot(
            symbol="TESTUSDT",
            candle_open_time_ms=int(rows[-1][0]),
            candle_close_time_ms=close_ts,
            open=100.0, high=101.2, low=99.8, close=101.0,
            base_volume_5m=10.0, quote_volume_5m=1000.0, trades_5m=100,
            taker_buy_base_volume_5m=5.0, taker_buy_quote_volume_5m=500.0,
            quote_volume_24h=50_000_000.0, price_change_pct_24h=5.0,
        )
        result = attach_market_context(
            movement=moving_candidate(close_ts),
            snapshot=snapshot,
            klines_5m=rows,
            now_ms=close_ts + 1,
            oi_hist=[
                {"timestamp": close_ts - 10 * 60_000, "sumOpenInterest": "100"},
                {"timestamp": close_ts - 5 * 60_000, "sumOpenInterest": "101"},
            ],
            premium={"lastFundingRate": "0"},
            regime=None,
        )
        self.assertIsNone(result.decision)


if __name__ == "__main__":
    unittest.main()
