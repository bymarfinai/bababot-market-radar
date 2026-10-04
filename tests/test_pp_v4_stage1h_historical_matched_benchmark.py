from __future__ import annotations

import unittest

from research.profit_protection_v4.stage1h_historical_matched_benchmark import (
    distribution,
    enrich,
    group_delta,
    strict_coverage,
)


class PPV4Stage1HHistoricalBenchmarkTests(unittest.TestCase):
    def base_row(self) -> dict:
        return {
            "position_id": "P1",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "opened_at_ms": 1_000,
            "closed_at_ms": 101_000,
            "peak5": 0.90,
            "n5": 20,
            "first5": 5_000,
            "last5": 98_000,
            "medgap5": 5_000,
            "peak15": 0.75,
            "n15": 7,
            "first15": 10_000,
            "last15": 95_000,
            "true_mfe": 1.00,
            "mfe_first_seen_ms": 30_000,
        }

    def test_strict_coverage_accepts_full_lifecycle_case(self) -> None:
        self.assertTrue(strict_coverage(self.base_row()))

    def test_strict_coverage_rejects_retired_observer_tail(self) -> None:
        row = self.base_row()
        row["last5"] = 80_000
        self.assertFalse(strict_coverage(row))

    def test_strict_coverage_rejects_low_mfe(self) -> None:
        row = self.base_row()
        row["true_mfe"] = 0.20
        self.assertFalse(strict_coverage(row))

    def test_distribution_tail_metrics(self) -> None:
        result = distribution([0.50, 0.80, 0.90, 1.00])
        self.assertAlmostEqual(result["lt80_share_pct"], 25.0)
        self.assertAlmostEqual(result["ge90_share_pct"], 50.0)

    def test_group_delta_detects_5s_uplift(self) -> None:
        rows = []
        for index in range(4):
            row = self.base_row()
            row["position_id"] = f"P{index}"
            row["peak15"] = 0.70
            row["peak5"] = 0.90
            rows.append(row)
        result = group_delta(enrich(rows))
        self.assertAlmostEqual(result["delta"]["median_capture_pp"], 20.0)
        self.assertGreater(result["delta"]["ge90_share_pp"], 0.0)
        self.assertGreater(result["delta"]["lt80_reduction_pp"], 0.0)


if __name__ == "__main__":
    unittest.main()
