from __future__ import annotations

import itertools
import unittest

from research.profit_protection_v4.stage2b_optimal_protection_frontier import (
    ARM_PCTS,
    CONFIRM_SAMPLES,
    RETAIN_RATIOS,
    exit_fill_price,
    holdout_positive,
    pareto_frontier,
    simulate_trade,
)


class PPV4Stage2BFrontierTests(unittest.TestCase):
    def test_preregistered_grid_has_144_candidates(self) -> None:
        self.assertEqual(
            len(list(itertools.product(
                ARM_PCTS,
                RETAIN_RATIOS,
                CONFIRM_SAMPLES,
            ))),
            144,
        )

    def test_exit_fill_is_adverse(self) -> None:
        self.assertLess(exit_fill_price("LONG", 100.0, 2.0), 100.0)
        self.assertGreater(exit_fill_price("SHORT", 100.0, 2.0), 100.0)

    def test_simulation_requires_confirmation(self) -> None:
        row = {
            "position_id": "P",
            "actual_realized_net_pct": 0.0,
            "realized_pnl_usdt": 0.0,
        }
        positions = {
            "P": {
                "position_id": "P",
                "side": "LONG",
                "opened_at_ms": 0,
                "closed_at_ms": 30_000,
                "entry_price": 100.0,
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
                {
                    "observed_at_ms": 5_000,
                    "current_price": 101.6,
                    "current_pnl_pct": 1.6,
                },
                {
                    "observed_at_ms": 10_000,
                    "current_price": 101.4,
                    "current_pnl_pct": 1.4,
                },
                {
                    "observed_at_ms": 15_000,
                    "current_price": 101.3,
                    "current_pnl_pct": 1.3,
                },
            ]
        }
        result = simulate_trade(
            row,
            arm_pct=1.5,
            retain_ratio=0.9,
            confirm_samples=2,
            positions=positions,
            observations=observations,
            orders={"P": []},
        )
        self.assertTrue(result["triggered"])
        self.assertEqual(result["trigger_at_ms"], 15_000)

    def test_pareto_removes_dominated_candidate(self) -> None:
        def candidate(total: float, retention: float, runner: float):
            return {
                "dev": {
                    "total_usdt": total,
                    "median_retention": retention,
                    "runner_ge1": {"median_retention": runner},
                }
            }
        strong = candidate(10.0, 0.5, 0.6)
        weak = candidate(9.0, 0.4, 0.5)
        frontier = pareto_frontier([strong, weak])
        self.assertEqual(frontier, [strong])

    def test_holdout_guardrails(self) -> None:
        baseline = {
            "total_usdt": 1.0,
            "peak_ge050": {
                "median_retention": 0.3,
                "nonpositive_n": 4,
            },
            "runner_ge1": {"total_usdt": 10.0},
        }
        candidate = {
            "late": {
                "total_usdt": 2.0,
                "peak_ge050": {
                    "median_retention": 0.4,
                    "nonpositive_n": 3,
                },
                "runner_ge1": {"total_usdt": 11.0},
            }
        }
        self.assertTrue(holdout_positive(candidate, baseline))


if __name__ == "__main__":
    unittest.main()
