from __future__ import annotations

import unittest

from research.profit_protection_v4.stage1k_fetch_phase_evidence import (
    residual_rows,
    sample_price,
    side_return,
    threshold_price,
)
from research.profit_protection_v4.stage1k_sub5s_phase_benchmark import (
    build_result,
)


class PPV4Stage1KSub5sTests(unittest.TestCase):
    def test_sample_price_is_causal_latest_at_or_before(self) -> None:
        self.assertEqual(
            sample_price(
                times=[1000, 1500, 2200],
                prices=[100.0, 101.0, 99.0],
                prior_price=98.0,
                sample_at_ms=1400,
            ),
            100.0,
        )
        self.assertEqual(
            sample_price(
                times=[1000, 1500],
                prices=[100.0, 101.0],
                prior_price=98.0,
                sample_at_ms=900,
            ),
            98.0,
        )

    def test_side_return_long_and_short(self) -> None:
        self.assertAlmostEqual(side_return("LONG", 100.0, 101.0), 1.0)
        self.assertAlmostEqual(side_return("SHORT", 100.0, 99.0), 1.0)

    def test_threshold_price_tracks_capture_target(self) -> None:
        self.assertAlmostEqual(
            threshold_price("LONG", 100.0, 1.0, 0.80),
            100.8,
        )
        self.assertAlmostEqual(
            threshold_price("SHORT", 100.0, 1.0, 0.80),
            99.2,
        )

    def test_residual_rows_use_clean_mfe(self) -> None:
        rows = [
            {
                "position_id": "A",
                "clean_post_entry_mfe_pct": 1.0,
                "peak5": 0.79,
            },
            {
                "position_id": "B",
                "clean_post_entry_mfe_pct": 1.0,
                "peak5": 0.80,
            },
            {
                "position_id": "C",
                "clean_post_entry_mfe_pct": 0.20,
                "peak5": 0.0,
            },
        ]
        self.assertEqual(
            [row["position_id"] for row in residual_rows(rows)],
            ["A"],
        )

    def test_evaluator_selects_event_driven_when_1s_and_2s_fail(self) -> None:
        stage1j = []
        evidence = []
        for index in range(24):
            pid = f"P{index}"
            stage1j.append(
                {
                    "position_id": pid,
                    "clean_post_entry_mfe_pct": 1.0,
                    "peak5": 0.50,
                }
            )
            evidence.append(
                {
                    "position_id": pid,
                    "symbol": "TESTUSDT",
                    "side": "LONG" if index % 2 == 0 else "SHORT",
                    "actual_5s_capture_ratio": 0.50,
                    "clean_mfe_pct": 1.0,
                    "cadences": {
                        "5000": {
                            "ge80_phase_probability": 0.0,
                            "ge90_phase_probability": 0.0,
                            "ge95_phase_probability": 0.0,
                        },
                        "2000": {
                            "ge80_phase_probability": 0.20,
                            "ge90_phase_probability": 0.10,
                            "ge95_phase_probability": 0.0,
                        },
                        "1000": {
                            "ge80_phase_probability": 0.40,
                            "ge90_phase_probability": 0.20,
                            "ge95_phase_probability": 0.10,
                        },
                    },
                }
            )
        result = build_result(evidence, stage1j)
        self.assertTrue(
            result["population"]["stage1j_residual_ids_match_exactly"]
        )
        self.assertEqual(result["decision"]["two_second_periodic"], "FAIL")
        self.assertEqual(result["decision"]["one_second_periodic"], "FAIL")
        self.assertEqual(
            result["decision"]["selected_next_research_path"],
            "EVENT_DRIVEN_NEXT_RESEARCH_CANDIDATE",
        )


if __name__ == "__main__":
    unittest.main()
