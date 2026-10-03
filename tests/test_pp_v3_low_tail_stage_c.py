from __future__ import annotations

import unittest

from research.profit_protection_v3.stage_b_low_tail_prearm_exchange import (
    _fractional_excursion_stop,
)
from research.profit_protection_v3.stage_c_selective_protection import (
    ProtectionConfig,
    _distribution,
    replay_exchange_trail_after_selection,
    select_trades,
)


class PPV3LowTailStageCTests(unittest.TestCase):
    def test_runner_escape_suppresses_high_running_peak(self) -> None:
        model = {
            "feature_key": "context_features",
            "means": [0.0],
            "stds": [1.0],
            "weights": [0.0, 10.0],
        }
        rows = [
            {
                "position_id": "A",
                "evaluated_at_ms": 1_000,
                "checkpoint_seconds": 30,
                "context_features": [1.0],
                "running_current_peak_pct": 1.20,
                "current_pnl_pct": 1.0,
                "current_mfe_pct": 1.2,
            }
        ]
        selected = select_trades(
            model=model,
            rows=rows,
            threshold=0.5,
            runner_escape_peak_pct=1.0,
        )
        self.assertEqual(selected, {})

    def test_selector_keeps_first_causal_fire(self) -> None:
        model = {
            "feature_key": "context_features",
            "means": [0.0],
            "stds": [1.0],
            "weights": [0.0, 10.0],
        }
        rows = [
            {
                "position_id": "A",
                "evaluated_at_ms": 1_000,
                "checkpoint_seconds": 30,
                "context_features": [1.0],
                "running_current_peak_pct": 0.20,
                "current_pnl_pct": 0.1,
                "current_mfe_pct": 0.2,
            },
            {
                "position_id": "A",
                "evaluated_at_ms": 2_000,
                "checkpoint_seconds": 45,
                "context_features": [2.0],
                "running_current_peak_pct": 0.30,
                "current_pnl_pct": 0.2,
                "current_mfe_pct": 0.3,
            },
        ]
        selected = select_trades(
            model=model,
            rows=rows,
            threshold=0.5,
            runner_escape_peak_pct=None,
        )
        self.assertEqual(selected["A"]["selected_at_ms"], 1_000)

    def test_replay_excludes_bar_started_before_selection(self) -> None:
        config = ProtectionConfig(
            name="IDEAL",
            activation_roi_pct=0.30,
            trail_value=0.90,
            stop_function=_fractional_excursion_stop,
            trail_type="IDEAL",
        )
        position = {
            "side": "LONG",
            "entry_price": 100.0,
        }
        bars = [
            {
                "open_time_ms": 60_000,
                "close_time_ms": 119_999,
                "open": 100.0,
                "high": 110.0,
                "low": 99.0,
                "close": 101.0,
            },
            {
                "open_time_ms": 120_000,
                "close_time_ms": 179_999,
                "open": 101.0,
                "high": 101.1,
                "low": 101.0,
                "close": 101.05,
            },
        ]
        result = replay_exchange_trail_after_selection(
            position=position,
            bars=bars,
            selected_at_ms=90_000,
            config=config,
        )
        self.assertFalse(result["triggered"])

    def test_same_bar_cross_is_not_executed(self) -> None:
        config = ProtectionConfig(
            name="IDEAL",
            activation_roi_pct=0.30,
            trail_value=0.90,
            stop_function=_fractional_excursion_stop,
            trail_type="IDEAL",
        )
        position = {"side": "LONG", "entry_price": 100.0}
        bars = [
            {
                "open_time_ms": 120_000,
                "close_time_ms": 179_999,
                "open": 100.0,
                "high": 101.0,
                "low": 100.50,
                "close": 100.70,
            }
        ]
        result = replay_exchange_trail_after_selection(
            position=position,
            bars=bars,
            selected_at_ms=120_000,
            config=config,
        )
        self.assertFalse(result["triggered"])
        self.assertEqual(result["ambiguous_same_bar_events"], 1)

    def test_distribution_metrics(self) -> None:
        rows = [
            {"capture": 0.70},
            {"capture": 0.90},
            {"capture": 1.00},
        ]
        result = _distribution(rows, key="capture")
        self.assertAlmostEqual(result["ge90_share_pct"], 200.0 / 3.0)
        self.assertAlmostEqual(result["lt80_share_pct"], 100.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
