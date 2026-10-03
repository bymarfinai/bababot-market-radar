from __future__ import annotations

import unittest

from research.profit_protection_v3.stage_a_low_tail_anatomy import (
    analysis_group,
    classify_observability_mechanism,
    quantile,
    ratio_band,
)


class PPV3LowTailStageATests(unittest.TestCase):
    def test_ratio_band_boundaries(self) -> None:
        self.assertEqual(ratio_band(0.49), "<50")
        self.assertEqual(ratio_band(0.50), "50-60")
        self.assertEqual(ratio_band(0.79), "70-80")
        self.assertEqual(ratio_band(0.80), "80-90")
        self.assertEqual(ratio_band(0.90), "90-100")
        self.assertEqual(ratio_band(1.01), "100-105")
        self.assertEqual(ratio_band(1.06), ">105")

    def test_analysis_groups(self) -> None:
        self.assertEqual(analysis_group(0.69), "SEVERE_LT70")
        self.assertEqual(analysis_group(0.75), "LOW_70_80")
        self.assertEqual(analysis_group(0.85), "MID_80_90")
        self.assertEqual(analysis_group(0.95), "GOOD_90_100")
        self.assertEqual(analysis_group(1.001), "BENCHMARK_GT100")

    def test_quantile_interpolates(self) -> None:
        values = [0.0, 1.0, 2.0, 3.0]
        self.assertAlmostEqual(float(quantile(values, 0.5)), 1.5)
        self.assertAlmostEqual(float(quantile(values, 0.25)), 0.75)

    def test_dominant_intrapoll_mechanism(self) -> None:
        row = {
            "capture_ratio": 0.60,
            "true_mfe_pct": 1.00,
            "max_v2_mfe_pct": 0.98,
            "terminal_peak_pct": 0.60,
        }
        self.assertEqual(
            classify_observability_mechanism(row),
            "INTRAPOLL_EXCURSION_DOMINANT",
        )

    def test_moderate_intrapoll_mechanism(self) -> None:
        row = {
            "capture_ratio": 0.85,
            "true_mfe_pct": 1.00,
            "max_v2_mfe_pct": 0.98,
            "terminal_peak_pct": 0.85,
        }
        self.assertEqual(
            classify_observability_mechanism(row),
            "INTRAPOLL_EXCURSION_MODERATE",
        )

    def test_benchmark_mismatch_mechanisms(self) -> None:
        overshoot = {
            "capture_ratio": 1.02,
            "true_mfe_pct": 1.00,
            "max_v2_mfe_pct": 1.02,
            "terminal_peak_pct": 1.02,
        }
        stream_miss = {
            "capture_ratio": 0.60,
            "true_mfe_pct": 1.00,
            "max_v2_mfe_pct": 0.80,
            "terminal_peak_pct": 0.60,
        }
        self.assertEqual(
            classify_observability_mechanism(overshoot),
            "BENCHMARK_MISMATCH_GT101",
        )
        self.assertEqual(
            classify_observability_mechanism(stream_miss),
            "BENCHMARK_STREAM_MISMATCH",
        )


if __name__ == "__main__":
    unittest.main()
