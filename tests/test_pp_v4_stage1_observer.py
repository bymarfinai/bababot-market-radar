from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_radar.binance import BinancePublicClient
from market_radar.profit_protection_v4_observer import (
    PeakState,
    advance_peak_state,
    process_pp_v4_cycle,
    side_return_pct,
)


class FakeClient:
    def __init__(self, prices=None, error: Exception | None = None):
        self.prices = prices or {}
        self.error = error

    def ticker_prices(self):
        if self.error is not None:
            raise self.error
        return dict(self.prices)


class PPV4Stage1ObserverTests(unittest.TestCase):
    def test_side_return_long_short_symmetry(self) -> None:
        self.assertAlmostEqual(side_return_pct("LONG", 100.0, 101.0), 1.0)
        self.assertAlmostEqual(side_return_pct("SHORT", 100.0, 99.0), 1.0)

    def test_peak_state_ratchets_and_tracks_gap(self) -> None:
        previous = PeakState(
            running_peak_pct=0.40,
            running_peak_at_ms=10_000,
            previous_pnl_pct=0.35,
            previous_observed_at_ms=15_000,
        )
        state, metrics = advance_peak_state(
            current_pnl_pct=0.55,
            observed_at_ms=20_000,
            arm_pct=0.30,
            previous=previous,
        )
        self.assertAlmostEqual(state.running_peak_pct, 0.55)
        self.assertEqual(state.running_peak_at_ms, 20_000)
        self.assertAlmostEqual(metrics["delta_pnl_pct_points"], 0.20)
        self.assertEqual(metrics["sample_gap_ms"], 5_000)
        self.assertTrue(metrics["armed"])

    def test_batch_ticker_prices_parses_snapshot(self) -> None:
        client = BinancePublicClient()
        with patch.object(
            client,
            "get",
            return_value=[
                {"symbol": "BTCUSDT", "price": "100.5"},
                {"symbol": "ETHUSDT", "price": "50.25"},
                {"symbol": "", "price": "1"},
                {"symbol": "BAD", "price": "x"},
            ],
        ):
            prices = client.ticker_prices()
        self.assertEqual(prices, {"BTCUSDT": 100.5, "ETHUSDT": 50.25})

    def test_cycle_observes_all_positions_from_one_snapshot(self) -> None:
        positions = [
            {
                "position_id": "P1",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_price": 100.0,
                "opened_at_ms": 2_000,
                "status": "OPEN",
                "mode": "PAPER",
            },
            {
                "position_id": "P2",
                "symbol": "ETHUSDT",
                "side": "SHORT",
                "entry_price": 50.0,
                "opened_at_ms": 2_000,
                "status": "OPEN",
                "mode": "PAPER",
            },
        ]
        saved_rows = []
        saved_cycles = []
        env = {
            "PP_V4_STAGE1_ENABLED": "true",
            "PP_V4_STAGE1_START_MS": "1000",
            "PP_V4_STAGE1_ARM_PCT": "0.30",
        }
        with patch.dict(os.environ, env, clear=False), \
             patch("market_radar.profit_protection_v4_observer.initialize_pp_v4_store"), \
             patch("market_radar.profit_protection_v4_observer._eligible_positions", return_value=positions), \
             patch("market_radar.profit_protection_v4_observer._last_cycle_receive_ms", return_value=None), \
             patch("market_radar.profit_protection_v4_observer._state_for", return_value=None), \
             patch(
                 "market_radar.profit_protection_v4_observer._save_observation",
                 side_effect=lambda row: saved_rows.append(dict(row)) or True,
             ), \
             patch(
                 "market_radar.profit_protection_v4_observer._save_cycle",
                 side_effect=lambda row: saved_cycles.append(dict(row)),
             ):
            result = process_pp_v4_cycle(
                client=FakeClient({"BTCUSDT": 101.0, "ETHUSDT": 49.5}),
                started_at_ms=10_000,
            )

        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["eligible_positions"], 2)
        self.assertEqual(result["observed_positions"], 2)
        self.assertEqual(len(saved_rows), 2)
        self.assertEqual(len(saved_cycles), 1)
        self.assertEqual(saved_cycles[0]["missing_positions"], 0)

    def test_missing_symbol_marks_cycle_partial(self) -> None:
        positions = [
            {
                "position_id": "P1",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_price": 100.0,
                "opened_at_ms": 2_000,
                "status": "OPEN",
                "mode": "PAPER",
            },
            {
                "position_id": "P2",
                "symbol": "ETHUSDT",
                "side": "LONG",
                "entry_price": 50.0,
                "opened_at_ms": 2_000,
                "status": "OPEN",
                "mode": "PAPER",
            },
        ]
        saved_cycles = []
        with patch.dict(
            os.environ,
            {
                "PP_V4_STAGE1_ENABLED": "true",
                "PP_V4_STAGE1_START_MS": "1000",
            },
            clear=False,
        ), patch("market_radar.profit_protection_v4_observer.initialize_pp_v4_store"), \
             patch("market_radar.profit_protection_v4_observer._eligible_positions", return_value=positions), \
             patch("market_radar.profit_protection_v4_observer._last_cycle_receive_ms", return_value=None), \
             patch("market_radar.profit_protection_v4_observer._state_for", return_value=None), \
             patch("market_radar.profit_protection_v4_observer._save_observation", return_value=True), \
             patch(
                 "market_radar.profit_protection_v4_observer._save_cycle",
                 side_effect=lambda row: saved_cycles.append(dict(row)),
             ):
            result = process_pp_v4_cycle(
                client=FakeClient({"BTCUSDT": 101.0}),
                started_at_ms=10_000,
            )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["missing_positions"], 1)
        self.assertEqual(saved_cycles[0]["status"], "PARTIAL")

    def test_provider_failure_is_fail_closed_and_audited(self) -> None:
        positions = [
            {
                "position_id": "P1",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_price": 100.0,
                "opened_at_ms": 2_000,
                "status": "OPEN",
                "mode": "PAPER",
            }
        ]
        saved_cycles = []
        with patch.dict(
            os.environ,
            {
                "PP_V4_STAGE1_ENABLED": "true",
                "PP_V4_STAGE1_START_MS": "1000",
            },
            clear=False,
        ), patch("market_radar.profit_protection_v4_observer.initialize_pp_v4_store"), \
             patch("market_radar.profit_protection_v4_observer._eligible_positions", return_value=positions), \
             patch("market_radar.profit_protection_v4_observer._last_cycle_receive_ms", return_value=None), \
             patch(
                 "market_radar.profit_protection_v4_observer._save_cycle",
                 side_effect=lambda row: saved_cycles.append(dict(row)),
             ):
            result = process_pp_v4_cycle(
                client=FakeClient(error=RuntimeError("provider down")),
                started_at_ms=10_000,
            )
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["observed_positions"], 0)
        self.assertEqual(saved_cycles[0]["status"], "ERROR")
        self.assertIn("provider down", saved_cycles[0]["error_text"])


if __name__ == "__main__":
    unittest.main()
