from __future__ import annotations

import itertools
import unittest

from research.profit_protection_v4.stage2c_runner_preservation import (
    REDUCE_FRACTIONS,
    RUNNER_QUALIFY_PCTS,
    SMALL_TEMPLATES,
    simulate_hybrid,
)


class PPV4Stage2CRunnerPreservationTests(unittest.TestCase):
    def test_preregistered_grid_has_24_candidates(self) -> None:
        self.assertEqual(
            len(
                list(
                    itertools.product(
                        SMALL_TEMPLATES,
                        REDUCE_FRACTIONS,
                        RUNNER_QUALIFY_PCTS,
                    )
                )
            ),
            24,
        )

    def test_small_reduce_then_runner_close(self) -> None:
        row = {"position_id": "P"}
        positions = {
            "P": {
                "position_id": "P",
                "side": "LONG",
                "opened_at_ms": 0,
                "closed_at_ms": 60_000,
                "entry_price": 100.0,
                "exit_price": 100.0,
                "realized_pnl": 0.0,
                "realized_pnl_pct": 0.0,
                "raw_json": (
                    '{"initial_quantity":5.0,"initial_notional_usdt":500.0,'
                    '"entry_fee_total":0.375,"fee_rate":0.00075,'
                    '"slippage_bps":2.0}'
                ),
            }
        }
        observations = {
            "P": [
                {"observed_at_ms": 5_000, "current_price": 100.6, "current_pnl_pct": 0.6},
                {"observed_at_ms": 10_000, "current_price": 100.3, "current_pnl_pct": 0.3},
                {"observed_at_ms": 15_000, "current_price": 100.3, "current_pnl_pct": 0.3},
                {"observed_at_ms": 20_000, "current_price": 100.3, "current_pnl_pct": 0.3},
                {"observed_at_ms": 25_000, "current_price": 101.6, "current_pnl_pct": 1.6},
                {"observed_at_ms": 30_000, "current_price": 101.4, "current_pnl_pct": 1.4},
                {"observed_at_ms": 35_000, "current_price": 101.3, "current_pnl_pct": 1.3},
            ]
        }
        orders = {"P": []}
        result = simulate_hybrid(
            row,
            small_template=(0.50, 0.60, 3),
            reduce_fraction=0.25,
            runner_qualify_pct=1.50,
            positions=positions,
            observations=observations,
            orders=orders,
        )
        self.assertTrue(result["small_fired"])
        self.assertTrue(result["runner_closed"])
        self.assertEqual(result["small_at_ms"], 20_000)
        self.assertEqual(result["runner_at_ms"], 35_000)

    def test_runner_qualification_disables_small_mode(self) -> None:
        row = {"position_id": "P"}
        positions = {
            "P": {
                "position_id": "P",
                "side": "LONG",
                "opened_at_ms": 0,
                "closed_at_ms": 40_000,
                "entry_price": 100.0,
                "exit_price": 100.0,
                "realized_pnl": 0.0,
                "realized_pnl_pct": 0.0,
                "raw_json": (
                    '{"initial_quantity":5.0,"initial_notional_usdt":500.0,'
                    '"entry_fee_total":0.375,"fee_rate":0.00075,'
                    '"slippage_bps":2.0}'
                ),
            }
        }
        observations = {
            "P": [
                {"observed_at_ms": 5_000, "current_price": 101.6, "current_pnl_pct": 1.6},
                {"observed_at_ms": 10_000, "current_price": 101.4, "current_pnl_pct": 1.4},
                {"observed_at_ms": 15_000, "current_price": 101.3, "current_pnl_pct": 1.3},
            ]
        }
        result = simulate_hybrid(
            row,
            small_template=(0.50, 0.60, 3),
            reduce_fraction=0.25,
            runner_qualify_pct=1.50,
            positions=positions,
            observations=observations,
            orders={"P": []},
        )
        self.assertFalse(result["small_fired"])
        self.assertTrue(result["runner_closed"])

    def test_no_overlay_keeps_actual_outcome(self) -> None:
        row = {"position_id": "P"}
        positions = {
            "P": {
                "position_id": "P",
                "side": "LONG",
                "opened_at_ms": 0,
                "closed_at_ms": 20_000,
                "entry_price": 100.0,
                "exit_price": 99.5,
                "realized_pnl": -3.0,
                "realized_pnl_pct": -0.6,
                "raw_json": (
                    '{"initial_quantity":5.0,"initial_notional_usdt":500.0,'
                    '"entry_fee_total":0.375,"fee_rate":0.00075,'
                    '"slippage_bps":2.0}'
                ),
            }
        }
        observations = {
            "P": [
                {"observed_at_ms": 5_000, "current_price": 100.1, "current_pnl_pct": 0.1},
                {"observed_at_ms": 10_000, "current_price": 99.9, "current_pnl_pct": -0.1},
            ]
        }
        result = simulate_hybrid(
            row,
            small_template=(0.50, 0.60, 3),
            reduce_fraction=0.25,
            runner_qualify_pct=1.50,
            positions=positions,
            observations=observations,
            orders={"P": []},
        )
        self.assertFalse(result["small_fired"])
        self.assertFalse(result["runner_closed"])
        self.assertEqual(result["sim_usdt"], -3.0)
        self.assertEqual(result["sim_pct"], -0.6)


if __name__ == "__main__":
    unittest.main()
