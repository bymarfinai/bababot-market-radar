from __future__ import annotations

import unittest

from research.profit_protection_v4.stage3c_temporal_reversal_detector import (
    detector_signal,
    gates,
    label_signal,
)


def obs(ms: int, pnl: float) -> dict[str, float | int]:
    return {
        "observed_at_ms": ms,
        "current_pnl_pct": pnl,
    }


class PPV4Stage3CTemporalReversalTests(unittest.TestCase):
    def test_wait_is_cancelled_by_new_running_high(self):
        path = [
            obs(0, 1.50),
            obs(5000, 1.80),
            obs(15000, 1.40),
            obs(20000, 1.90),
            obs(25000, 1.88),
        ]
        signal = detector_signal(
            path,
            floor=0.80,
            min_age_seconds=10,
            min_velocity_pp_per_sec=0.0,
            reclaim_wait_seconds=10,
        )
        self.assertIsNone(signal)

    def test_signal_emits_after_wait_if_floor_not_reclaimed(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(15000, 1.55),
            obs(20000, 1.50),
            obs(25000, 1.45),
        ]
        signal = detector_signal(
            path,
            floor=0.80,
            min_age_seconds=10,
            min_velocity_pp_per_sec=0.0,
            reclaim_wait_seconds=10,
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal["signal_at_ms"], 25000)

    def test_future_higher_peak_is_research_label_only(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(15000, 1.50),
            obs(20000, 2.10),
        ]
        signal = {
            "signal_at_ms": 15000,
            "signal_pnl_pct": 1.50,
            "signal_running_peak_pct": 2.00,
            "signal_running_peak_at_ms": 5000,
        }
        labelled = label_signal(path, signal, 2.10)
        self.assertEqual(
            labelled["label"],
            "PREMATURE_FALSE_REVERSAL",
        )

    def test_contract_gates_require_all_four_dimensions(self):
        passing = {
            "signal_coverage": 0.50,
            "precision": 0.60,
            "premature_share": 0.40,
            "median_correct_retention": 0.75,
        }
        self.assertTrue(all(gates(passing).values()))
        failing = dict(passing)
        failing["median_correct_retention"] = 0.749
        self.assertFalse(gates(failing)["retention"])


if __name__ == "__main__":
    unittest.main()
