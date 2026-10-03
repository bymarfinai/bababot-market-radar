from __future__ import annotations

import unittest

from research.profit_protection_v3.stage_b_low_tail_prearm_exchange import (
    _bars_from_observations,
    _fractional_excursion_stop,
    _native_stop,
    replay_exchange_trail,
)


class PPV3LowTailStageBTests(unittest.TestCase):
    def test_native_stop_long_and_short(self) -> None:
        self.assertAlmostEqual(
            _native_stop(
                side="LONG",
                peak_price=101.0,
                callback_rate_pct=0.10,
                entry=100.0,
            ),
            100.899,
        )
        self.assertAlmostEqual(
            _native_stop(
                side="SHORT",
                peak_price=99.0,
                callback_rate_pct=0.10,
                entry=100.0,
            ),
            99.099,
        )

    def test_fractional_stop_retains_fraction_of_excursion(self) -> None:
        self.assertAlmostEqual(
            _fractional_excursion_stop(
                side="LONG",
                peak_price=102.0,
                callback_rate_pct=0.90,
                entry=100.0,
            ),
            101.8,
        )
        self.assertAlmostEqual(
            _fractional_excursion_stop(
                side="SHORT",
                peak_price=98.0,
                callback_rate_pct=0.90,
                entry=100.0,
            ),
            98.2,
        )

    def test_same_bar_activation_is_ambiguous_conservatively(self) -> None:
        position = {
            "side": "LONG",
            "entry_price": 100.0,
            "exit_price": 100.5,
            "closed_at_ms": 180_000,
        }
        bars = [
            {
                "open_time_ms": 60_000,
                "close_time_ms": 119_999,
                "open": 100.0,
                "high": 101.0,
                "low": 100.7,
                "close": 100.8,
            }
        ]
        conservative = replay_exchange_trail(
            position=position,
            bars=bars,
            activation_roi_pct=0.30,
            trail_value=0.90,
            stop_function=_fractional_excursion_stop,
            optimistic_same_bar=False,
        )
        optimistic = replay_exchange_trail(
            position=position,
            bars=bars,
            activation_roi_pct=0.30,
            trail_value=0.90,
            stop_function=_fractional_excursion_stop,
            optimistic_same_bar=True,
        )
        self.assertFalse(conservative["triggered"])
        self.assertEqual(
            conservative["ambiguous_same_bar_events_before_exit"],
            1,
        )
        self.assertTrue(optimistic["triggered"])
        self.assertEqual(
            optimistic["trigger_kind"],
            "AMBIGUOUS_ACTIVATION_BAR",
        )

    def test_prior_bar_stop_cross_is_definite(self) -> None:
        position = {
            "side": "LONG",
            "entry_price": 100.0,
            "exit_price": 100.2,
            "closed_at_ms": 240_000,
        }
        bars = [
            {
                "open_time_ms": 60_000,
                "close_time_ms": 119_999,
                "open": 100.0,
                "high": 101.0,
                "low": 100.95,
                "close": 100.98,
            },
            {
                "open_time_ms": 120_000,
                "close_time_ms": 179_999,
                "open": 100.98,
                "high": 101.0,
                "low": 100.80,
                "close": 100.85,
            },
        ]
        result = replay_exchange_trail(
            position=position,
            bars=bars,
            activation_roi_pct=0.30,
            trail_value=0.90,
            stop_function=_fractional_excursion_stop,
            optimistic_same_bar=False,
        )
        self.assertTrue(result["triggered"])
        self.assertEqual(
            result["trigger_kind"],
            "DEFINITE_PRIOR_BAR_STOP",
        )

    def test_entry_straddling_bar_is_excluded(self) -> None:
        position = {
            "opened_at_ms": 90_000,
            "closed_at_ms": 240_000,
        }
        rows = [
            {
                "snapshot": {
                    "candle_close_time_ms": 119_999,
                    "latest_1m_open": 100.0,
                    "latest_1m_high": 105.0,
                    "latest_1m_low": 99.0,
                    "latest_1m_close": 101.0,
                }
            },
            {
                "snapshot": {
                    "candle_close_time_ms": 179_999,
                    "latest_1m_open": 101.0,
                    "latest_1m_high": 102.0,
                    "latest_1m_low": 100.5,
                    "latest_1m_close": 101.5,
                }
            },
        ]
        bars = _bars_from_observations(position=position, rows=rows)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["close_time_ms"], 179_999)


if __name__ == "__main__":
    unittest.main()
