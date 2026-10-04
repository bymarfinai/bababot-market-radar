from __future__ import annotations

import unittest

from research.profit_protection_v4.stage3c3_multicycle_volnorm_detector import (
    gates,
    label_signal,
    local_noise_scale,
    multicycle_signal,
)


def obs(ms: int, pnl: float) -> dict[str, float | int]:
    return {"observed_at_ms": ms, "current_pnl_pct": pnl}


class PPV4Stage3C3MultiCycleVolNormTests(unittest.TestCase):
    def test_noise_uses_only_available_history(self):
        path = [
            obs(0, 1.00),
            obs(5000, 1.10),
            obs(10000, 1.30),
            obs(15000, 1.25),
        ]
        self.assertAlmostEqual(
            local_noise_scale(path, 2, 6),
            0.15,
            places=9,
        )

    def test_new_high_resets_reclaim_cycles(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(10000, 1.75),
            obs(15000, 1.90),
            obs(20000, 1.70),
            obs(25000, 2.10),
            obs(30000, 2.00),
        ]
        signal = multicycle_signal(
            path,
            floor=0.90,
            noise_lookback=6,
            reclaim_fraction=0.25,
            required_failed_cycles=2,
            min_drawdown_z=2.0,
        )
        self.assertIsNone(signal)

    def test_failed_reclaim_can_emit_when_z_gate_passes(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(10000, 1.70),
            obs(15000, 1.85),
            obs(20000, 1.69),
        ]
        signal = multicycle_signal(
            path,
            floor=0.90,
            noise_lookback=6,
            reclaim_fraction=0.25,
            required_failed_cycles=1,
            min_drawdown_z=2.0,
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal["failed_reclaim_count"], 1)

    def test_future_higher_peak_is_label_only(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(15000, 1.65),
            obs(20000, 2.10),
        ]
        signal = {
            "signal_at_ms": 15000,
            "signal_pnl_pct": 1.65,
            "signal_running_peak_pct": 2.00,
        }
        outcome = label_signal(path, signal, 2.10)
        self.assertEqual(
            outcome["label"],
            "PREMATURE_FALSE_REVERSAL",
        )

    def test_stage3c3_contract_gates(self):
        passing = {
            "signal_coverage": 0.50,
            "precision": 0.65,
            "premature_share": 0.35,
            "median_correct_retention": 0.80,
            "correct_retention_ge80_share": 0.50,
        }
        self.assertTrue(all(gates(passing).values()))
        failing = dict(passing)
        failing["premature_share"] = 0.351
        self.assertFalse(gates(failing)["premature"])


if __name__ == "__main__":
    unittest.main()
