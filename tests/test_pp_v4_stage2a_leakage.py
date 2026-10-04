from __future__ import annotations

import unittest

from research.profit_protection_v4.stage2a_build_evidence import (
    exit_fill_price,
    gross_pnl,
)
from research.profit_protection_v4.stage2a_observable_realized_leakage import (
    build_result,
)


class PPV4Stage2ALeakageTests(unittest.TestCase):
    def test_exit_fill_is_adverse(self) -> None:
        self.assertLess(exit_fill_price("LONG", 100.0, 2.0), 100.0)
        self.assertGreater(exit_fill_price("SHORT", 100.0, 2.0), 100.0)

    def test_gross_pnl_long_short(self) -> None:
        self.assertAlmostEqual(gross_pnl("LONG", 100.0, 101.0, 2.0), 2.0)
        self.assertAlmostEqual(gross_pnl("SHORT", 100.0, 99.0, 2.0), 2.0)

    def test_stage2a_decision_requires_material_leakage(self) -> None:
        rows = []
        for i in range(42):
            rows.append(
                {
                    "position_id": f"P{i}",
                    "symbol": "TESTUSDT",
                    "side": "LONG",
                    "close_reason": "stage12_close",
                    "clean_mfe_pct": 1.0,
                    "observable_gross_peak_pct": 0.9,
                    "observable_net_peak_pct": 0.8,
                    "actual_realized_net_pct": 0.2,
                    "net_leakage_pp": 0.6,
                    "net_retention_ratio": 0.25,
                    "positive_observability_gap_pp": 0.1,
                    "peak_to_close_seconds": 200.0,
                    "peak_age_seconds": 60.0,
                    "reductions_before_peak": 0,
                    "observable_net_peak_usdt": 4.0,
                    "realized_pnl_usdt": 1.0,
                    "thresholds": {
                        "r90": {
                            "seconds_from_peak": 10.0,
                            "seconds_to_close": 190.0,
                        },
                        "r80": {
                            "seconds_from_peak": 15.0,
                            "seconds_to_close": 185.0,
                        },
                        "r70": {
                            "seconds_from_peak": 25.0,
                            "seconds_to_close": 175.0,
                        },
                        "r50": {
                            "seconds_from_peak": 60.0,
                            "seconds_to_close": 140.0,
                        },
                        "breakeven": None,
                    },
                }
            )
        result = build_result(rows)
        self.assertTrue(
            result["decision"][
                "leakage_is_larger_than_remaining_observability_gap"
            ]
        )
        self.assertTrue(
            result["decision"][
                "proceed_to_v4_2b_optimal_protection_frontier"
            ]
        )
        self.assertIsNone(result["decision"]["threshold_selected"])


if __name__ == "__main__":
    unittest.main()
