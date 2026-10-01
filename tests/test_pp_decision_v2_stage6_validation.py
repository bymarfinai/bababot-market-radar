from __future__ import annotations
import os
import unittest
from unittest.mock import patch

from market_radar.profit_discriminator_stage6 import (
    _replay,
    stage6_discriminator_enabled,
    stage6_discriminator_start_ms,
)

class PPDecisionV2Stage6ValidationTests(unittest.TestCase):
    def position(self) -> dict:
        return {
            "side": "LONG",
            "entry_price": 100.0,
            "exit_price": 100.1,
            "raw_json": (
                '{"initial_quantity":5.0,'
                '"entry_fee_total":0.375,'
                '"initial_notional_usdt":500.0}'
            ),
        }

    def observations(self) -> list[dict]:
        return [
            {
                "evaluated_at_ms": 1_000_000,
                "current_price": 100.4,
                "current_pnl_pct": 0.4,
                "mfe_pct": 0.8,                "previous_pnl_pct": 0.8,
                "elapsed_seconds": 15.0,
                "danger_score": 2,
            },
            {
                "evaluated_at_ms": 1_015_000,
                "current_price": 100.2,
                "current_pnl_pct": 0.2,
                "mfe_pct": 0.8,
                "previous_pnl_pct": 0.4,
                "elapsed_seconds": 15.0,
                "danger_score": 4,
            },
            {
                "evaluated_at_ms": 1_030_000,
                "current_price": 100.1,
                "current_pnl_pct": 0.1,
                "mfe_pct": 0.8,
                "previous_pnl_pct": 0.2,
                "elapsed_seconds": 15.0,
                "danger_score": 4,
            },
        ]

    def test_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"PP_DECISION_V2_STAGE6_VALIDATION_ENABLED": "false"}, clear=False):
            self.assertFalse(stage6_discriminator_enabled())
    def test_boundary_parse(self) -> None:
        with patch.dict(os.environ, {"PP_DECISION_V2_STAGE6_START_MS": "123456"}, clear=False):
            self.assertEqual(stage6_discriminator_start_ms(), 123456)

    def test_stage3_replay_is_stateful(self) -> None:
        net, actions = _replay(self.position(), self.observations(), 0)
        self.assertEqual(actions, 2)
        self.assertIsInstance(net, float)

    def test_grace15_skips_first_irreversible_action(self) -> None:
        baseline, a0 = _replay(self.position(), self.observations(), 0)
        grace, a15 = _replay(self.position(), self.observations(), 15)
        self.assertEqual(a0, 2)
        self.assertEqual(a15, 1)
        self.assertNotEqual(baseline, grace)

    def test_grace30_delays_to_third_sample(self) -> None:
        g15, a15 = _replay(self.position(), self.observations(), 15)
        g30, a30 = _replay(self.position(), self.observations(), 30)
        self.assertEqual(a15, 1)
        self.assertEqual(a30, 1)
        self.assertNotEqual(g15, g30)

if __name__ == "__main__":
    unittest.main()
