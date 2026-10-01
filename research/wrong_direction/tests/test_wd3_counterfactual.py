from __future__ import annotations

import unittest

from research.wrong_direction.wd3_counterfactual import (
    _entry_fill,
    _exit_fill,
    _gross,
    dynamic_exit_net,
    delayed_entry_censor_net,
    observation_flags,
)


class WD3CounterfactualTests(unittest.TestCase):
    def test_fill_direction(self):
        self.assertAlmostEqual(_entry_fill("LONG", 100.0, 2.0), 100.02)
        self.assertAlmostEqual(_entry_fill("SHORT", 100.0, 2.0), 99.98)
        self.assertAlmostEqual(_exit_fill("LONG", 100.0, 2.0), 99.98)
        self.assertAlmostEqual(_exit_fill("SHORT", 100.0, 2.0), 100.02)

    def test_gross_long_short(self):
        self.assertEqual(_gross("LONG", 2.0, 100.0, 101.0), 2.0)
        self.assertEqual(_gross("SHORT", 2.0, 100.0, 99.0), 2.0)

    def test_observation_flags(self):
        obs = {
            "current_pnl_pct": -0.4,
            "danger_score": 4,
            "snapshot_json": """{
                "side_ret_3m_pct": -0.2,
                "flow_opposite": true,
                "positioning_opposite": true,
                "opposite_micro_structure": false
            }""",
        }
        flags = observation_flags(obs)
        self.assertTrue(flags["ret3neg_and_flow_opp"])
        self.assertTrue(flags["ret3neg_and_positioning_opp"])
        self.assertTrue(flags["adverse_families_ge_2"])
        self.assertTrue(flags["danger_ge_4"])
        self.assertTrue(flags["pnl_le_minus_035_and_adverse_ge_2"])

    def test_dynamic_exit_respects_prior_reduce(self):
        position = {
            "position_id": "P1",
            "side": "LONG",
            "entry_price": 100.0,
            "realized_pnl": 0.0,
            "raw_json": """{
                "initial_notional_usdt": 1000.0,
                "initial_quantity": 10.0,
                "entry_fee_total": 1.0,
                "fee_rate": 0.001,
                "slippage_bps": 0.0,
                "last_exit_market_price": 100.0
            }""",
        }
        orders = [
            {
                "action": "REDUCE",
                "executed_at_ms": 1000,
                "executed_quantity": 5.0,
                "fill_price": 101.0,
                "fee": 0.505,
            }
        ]
        obs = {
            "evaluated_at_ms": 2000,
            "current_price": 99.0,
        }
        # First 5 units: +5 gross -0.5 entry fee -0.505 exit fee = 3.995
        # Remaining 5 units: -5 gross -0.5 entry fee -0.495 exit fee = -5.995
        # Total = -2.0
        self.assertAlmostEqual(
            dynamic_exit_net(position, orders, obs),
            -2.0,
            places=9,
        )

    def test_delayed_entry_fixed_censor(self):
        position = {
            "side": "LONG",
            "exit_price": 102.0,
            "raw_json": """{
                "initial_notional_usdt": 500.0,
                "initial_quantity": 5.0,
                "entry_fee_total": 0.5,
                "fee_rate": 0.001,
                "slippage_bps": 0.0,
                "last_exit_market_price": 102.0
            }""",
        }
        obs = {"current_price": 100.0}
        # Qty=5; gross=10; fees=.5 entry + .51 exit
        self.assertAlmostEqual(
            delayed_entry_censor_net(position, obs),
            8.99,
            places=9,
        )


if __name__ == "__main__":
    unittest.main()
