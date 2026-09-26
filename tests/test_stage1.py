from __future__ import annotations

import unittest

from market_radar.direction_scorer import score_directions
from market_radar.models import MovementDetection
from market_radar.moving_detector import (
    InsufficientHistoryError,
    detect_movement,
)
from market_radar.stage_classifier import (
    VALID_STAGES,
    classify_movement_stage,
)
from market_radar.scheduler import next_five_minute_run_ms
from market_radar.stage1_scanner import (
    filter_usdt_perpetuals,
    latest_closed_kline,
    snapshot_from_kline,
)


def make_klines(
    closes: list[float],
    quote_volumes: list[float] | None = None,
    ranges: list[float] | None = None,
    trades: list[int] | None = None,
) -> list[list]:
    quote_volumes = quote_volumes or [100.0] * len(closes)
    ranges = ranges or [0.2] * len(closes)
    trades = trades or [100] * len(closes)

    rows: list[list] = []
    for idx, close in enumerate(closes):
        previous = closes[idx - 1] if idx > 0 else close
        half_range = ranges[idx] / 2.0
        open_time = idx * 300_000
        close_time = (idx + 1) * 300_000 - 1

        rows.append(
            [
                open_time,
                str(previous),
                str(close + half_range),
                str(close - half_range),
                str(close),
                "1",
                close_time,
                str(quote_volumes[idx]),
                trades[idx],
                "0.5",
                str(quote_volumes[idx] * 0.5),
                "0",
            ]
        )
    return rows


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


class Stage2MovementDetectorTests(unittest.TestCase):
    def test_flat_market_is_noise_not_candidate(self):
        rows = make_klines([100.0] * 40)
        result = detect_movement("FLATUSDT", rows, now_ms=40 * 300_000 + 1)

        self.assertEqual(result.movement_state, "NOISE")
        self.assertFalse(result.is_moving)
        self.assertEqual(result.direction_hint, "FLAT")

    def test_abnormal_fresh_move_is_early_movement(self):
        closes = [100.0] * 39 + [100.5]
        volumes = [100.0] * 39 + [250.0]
        ranges = [0.2] * 39 + [0.8]
        trades = [100] * 39 + [180]

        result = detect_movement(
            "EARLYUSDT",
            make_klines(closes, volumes, ranges, trades),
            now_ms=40 * 300_000 + 1,
        )

        self.assertTrue(result.is_moving)
        self.assertEqual(result.movement_state, "EARLY_MOVEMENT")
        self.assertEqual(result.direction_hint, "UP")
        self.assertGreaterEqual(result.evidence_count, 3)

    def test_persistent_move_is_strong_continuation(self):
        closes = [100.0] * 37 + [100.25, 100.55, 101.0]
        volumes = [100.0] * 37 + [130.0, 160.0, 250.0]
        ranges = [0.2] * 37 + [0.3, 0.4, 0.9]
        trades = [100] * 37 + [120, 140, 220]

        result = detect_movement(
            "STRONGUSDT",
            make_klines(closes, volumes, ranges, trades),
            now_ms=40 * 300_000 + 1,
        )

        self.assertTrue(result.is_moving)
        self.assertTrue(result.directional_persistence)
        self.assertEqual(result.movement_state, "STRONG_CONTINUATION")

    def test_already_extended_move_is_flagged_late_not_stage3_exhaustion(self):
        closes = [100.0] * 37 + [100.25, 100.55, 101.0]
        volumes = [100.0] * 37 + [130.0, 160.0, 250.0]
        ranges = [0.2] * 37 + [0.3, 0.4, 0.9]
        trades = [100] * 37 + [120, 140, 220]

        result = detect_movement(
            "LATEUSDT",
            make_klines(closes, volumes, ranges, trades),
            now_ms=40 * 300_000 + 1,
            ret_24h_pct=35.0,
        )

        self.assertTrue(result.is_moving)
        self.assertEqual(result.movement_state, "LATE_MOVEMENT")
        self.assertNotEqual(result.movement_state, "EXHAUSTION")

    def test_down_move_is_raw_direction_hint_not_short_trade_decision(self):
        closes = [100.0] * 39 + [99.5]
        volumes = [100.0] * 39 + [250.0]
        ranges = [0.2] * 39 + [0.8]
        trades = [100] * 39 + [180]

        result = detect_movement(
            "DOWNUSDT",
            make_klines(closes, volumes, ranges, trades),
            now_ms=40 * 300_000 + 1,
        )

        self.assertTrue(result.is_moving)
        self.assertEqual(result.direction_hint, "DOWN")
        self.assertIsNone(result.long_score)
        self.assertIsNone(result.short_score)
        self.assertIsNone(result.decision)

    def test_in_progress_spike_cannot_leak_into_detection(self):
        closed = make_klines([100.0] * 40)
        open_spike = [
            40 * 300_000,
            "100",
            "120",
            "99",
            "118",
            "1000",
            41 * 300_000 - 1,
            "100000",
            10000,
            "900",
            "90000",
            "0",
        ]
        rows = closed + [open_spike]

        result = detect_movement(
            "CAUSALUSDT",
            rows,
            now_ms=40 * 300_000 + 1000,
        )

        self.assertFalse(result.is_moving)
        self.assertEqual(result.movement_state, "NOISE")
        self.assertEqual(result.candle_close_time_ms, 40 * 300_000 - 1)

    def test_new_listing_without_baseline_is_skipped_cleanly(self):
        rows = make_klines([100.0] * 10)
        with self.assertRaises(InsufficientHistoryError):
            detect_movement("NEWUSDT", rows, now_ms=10 * 300_000 + 1)


class Stage3MovementStageTests(unittest.TestCase):
    def movement(self, state: str, is_moving: bool = True) -> MovementDetection:
        return MovementDetection(
            symbol="TESTUSDT",
            detector_version="stage2-v1",
            candle_close_time_ms=1_000,
            movement_state=state,
            direction_hint="UP" if is_moving else "FLAT",
            is_moving=is_moving,
            ret_5m_pct=0.5 if is_moving else 0.0,
            ret_15m_pct=0.7 if is_moving else 0.0,
            ret_1h_pct=1.0 if is_moving else 0.0,
            ret_24h_pct=2.0 if is_moving else 0.0,
            median_abs_ret_5m_pct=0.1,
            return_expansion_ratio=5.0 if is_moving else 0.0,
            volume_ratio=2.0 if is_moving else 1.0,
            range_ratio=2.0 if is_moving else 1.0,
            trades_ratio=2.0 if is_moving else 1.0,
            directional_persistence=is_moving,
            evidence_count=5 if is_moving else 0,
            reasons=(),
        )

    def test_early_movement_maps_to_ignition(self):
        result = classify_movement_stage(self.movement("EARLY_MOVEMENT"))
        self.assertEqual(result.stage, "IGNITION")
        self.assertIn(result.stage, VALID_STAGES)

    def test_strong_continuation_maps_to_expansion(self):
        result = classify_movement_stage(self.movement("STRONG_CONTINUATION"))
        self.assertEqual(result.stage, "EXPANSION")

    def test_late_movement_maps_to_exhaustion(self):
        result = classify_movement_stage(self.movement("LATE_MOVEMENT"))
        self.assertEqual(result.stage, "EXHAUSTION")

    def test_non_moving_observation_has_no_stage(self):
        result = classify_movement_stage(self.movement("NOISE", is_moving=False))
        self.assertIsNone(result.stage)

    def test_unknown_moving_state_fails_closed(self):
        with self.assertRaises(ValueError):
            classify_movement_stage(self.movement("UNKNOWN_MOVEMENT"))

    def test_stage3_does_not_calculate_scores_or_decision(self):
        result = classify_movement_stage(self.movement("EARLY_MOVEMENT"))
        self.assertIsNone(result.long_score)
        self.assertIsNone(result.short_score)
        self.assertIsNone(result.decision)


class Stage4DirectionScoreTests(unittest.TestCase):
    def movement(
        self,
        *,
        r5: float,
        r15: float,
        r60: float,
        direction: str,
        persistent: bool,
        state: str = "EARLY_MOVEMENT",
    ) -> MovementDetection:
        stage = {
            "EARLY_MOVEMENT": "IGNITION",
            "STRONG_CONTINUATION": "EXPANSION",
            "LATE_MOVEMENT": "EXHAUSTION",
        }[state]
        return MovementDetection(
            symbol="SCOREUSDT",
            detector_version="stage2-v1",
            candle_close_time_ms=1_000,
            movement_state=state,
            direction_hint=direction,
            is_moving=True,
            ret_5m_pct=r5,
            ret_15m_pct=r15,
            ret_1h_pct=r60,
            ret_24h_pct=3.0 if direction == "UP" else -3.0,
            median_abs_ret_5m_pct=0.10,
            return_expansion_ratio=4.0,
            volume_ratio=2.2,
            range_ratio=1.9,
            trades_ratio=1.8,
            directional_persistence=persistent,
            evidence_count=5,
            reasons=(),
            stage=stage,
            stage_classifier_version="stage3-v1",
        )

    def test_up_move_scores_long_above_short(self):
        result = score_directions(
            self.movement(
                r5=0.60,
                r15=1.10,
                r60=2.20,
                direction="UP",
                persistent=True,
            )
        )
        self.assertGreater(result.long_score, result.short_score)
        self.assertGreater(result.score_gap, 0.0)

    def test_down_move_scores_short_above_long(self):
        result = score_directions(
            self.movement(
                r5=-0.60,
                r15=-1.10,
                r60=-2.20,
                direction="DOWN",
                persistent=True,
            )
        )
        self.assertGreater(result.short_score, result.long_score)
        self.assertLess(result.score_gap, 0.0)

    def test_scores_are_bounded_zero_to_one_hundred(self):
        result = score_directions(
            self.movement(
                r5=20.0,
                r15=40.0,
                r60=80.0,
                direction="UP",
                persistent=True,
                state="STRONG_CONTINUATION",
            )
        )
        self.assertGreaterEqual(result.long_score, 0.0)
        self.assertLessEqual(result.long_score, 100.0)
        self.assertGreaterEqual(result.short_score, 0.0)
        self.assertLessEqual(result.short_score, 100.0)

    def test_long_short_scores_are_independent_not_complements(self):
        # Current 5m reverses down while 15m/1h context remains positive.
        result = score_directions(
            self.movement(
                r5=-0.35,
                r15=0.60,
                r60=1.50,
                direction="DOWN",
                persistent=False,
            )
        )
        self.assertGreater(result.long_score, 0.0)
        self.assertGreater(result.short_score, 0.0)
        self.assertNotAlmostEqual(result.long_score + result.short_score, 100.0)

    def test_stage4_does_not_create_final_trade_decision(self):
        result = score_directions(
            self.movement(
                r5=0.50,
                r15=0.80,
                r60=1.20,
                direction="UP",
                persistent=True,
            )
        )
        self.assertIsNone(result.decision)
        self.assertIsNotNone(result.long_score)
        self.assertIsNotNone(result.short_score)

    def test_non_moving_scores_zero(self):
        movement = MovementDetection(
            symbol="FLATUSDT",
            detector_version="stage2-v1",
            candle_close_time_ms=1_000,
            movement_state="NOISE",
            direction_hint="FLAT",
            is_moving=False,
            ret_5m_pct=0.0,
            ret_15m_pct=0.0,
            ret_1h_pct=0.0,
            ret_24h_pct=0.0,
            median_abs_ret_5m_pct=0.1,
            return_expansion_ratio=1.0,
            volume_ratio=1.0,
            range_ratio=1.0,
            trades_ratio=1.0,
            directional_persistence=False,
            evidence_count=0,
            reasons=(),
            stage=None,
            stage_classifier_version="stage3-v1",
        )
        result = score_directions(movement)
        self.assertEqual(result.long_score, 0.0)
        self.assertEqual(result.short_score, 0.0)
        self.assertEqual(result.score_edge, 0.0)


if __name__ == "__main__":
    unittest.main()
