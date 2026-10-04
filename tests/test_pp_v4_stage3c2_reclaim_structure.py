from __future__ import annotations

import unittest

from research.profit_protection_v4.stage3c2_reclaim_structure_detector import (
    gates,
    label_signal,
    reclaim_signal,
)


def obs(ms: int, pnl: float) -> dict[str, float | int]:
    return {"observed_at_ms": ms, "current_pnl_pct": pnl}


class PPV4Stage3C2ReclaimStructureTests(unittest.TestCase):
    def test_new_high_cancels_probe(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(10000, 1.75),
            obs(15000, 2.05),
            obs(20000, 2.00),
        ]
        signal = reclaim_signal(
            path,
            floor=0.90,
            probe_window_seconds=10,
            reclaim_fraction_threshold=0.50,
            rebound_velocity_threshold=0.0,
        )
        self.assertIsNone(signal)

    def test_strong_reclaim_cancels_reversal(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(10000, 1.70),
            obs(15000, 1.85),
            obs(20000, 1.90),
        ]
        signal = reclaim_signal(
            path,
            floor=0.90,
            probe_window_seconds=10,
            reclaim_fraction_threshold=0.50,
            rebound_velocity_threshold=0.0,
        )
        self.assertIsNone(signal)

    def test_failed_reclaim_emits_reversal(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(10000, 1.70),
            obs(15000, 1.72),
            obs(20000, 1.69),
        ]
        signal = reclaim_signal(
            path,
            floor=0.90,
            probe_window_seconds=10,
            reclaim_fraction_threshold=0.50,
            rebound_velocity_threshold=0.01,
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal["signal_at_ms"], 20000)

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
            "probe_running_peak_pct": 2.00,
        }
        outcome = label_signal(path, signal, 2.10)
        self.assertEqual(
            outcome["label"],
            "PREMATURE_FALSE_REVERSAL",
        )

    def test_stage3c2_contract_gates(self):
        passing = {
            "signal_coverage": 0.50,
            "precision": 0.65,
            "premature_share": 0.35,
            "median_correct_retention": 0.80,
            "correct_retention_ge80_share": 0.50,
        }
        self.assertTrue(all(gates(passing).values()))
        failing = dict(passing)
        failing["precision"] = 0.649
        self.assertFalse(gates(failing)["precision"])


if __name__ == "__main__":
    unittest.main()
