from __future__ import annotations

import unittest

from research.wrong_direction.wd5h_stage4c import (
    MIN_RESOLVED_TAKES,
    choose_for_floor,
    choose_formal_rule,
    eligible_all,
)


class WD5HStage4CTests(unittest.TestCase):
    def test_eligible_guard_excludes_early_resolved(self):
        rows = [
            {
                "primary_label_end_ms": "100",
                "t1_target_ms": "100",
            },
            {
                "primary_label_end_ms": "101",
                "t1_target_ms": "100",
            },
        ]
        got = eligible_all(rows, 1)
        self.assertEqual(len(got), 1)

    def test_floor_choice_prefers_more_resolved_takes(self):
        points = [
            {
                "resolved_precision_pct": 80.0,
                "resolved_take_n": 10,
                "timeout_rate_pct": 5.0,
                "all_take_win_rate_pct": 76.0,
                "threshold": 0.8,
            },
            {
                "resolved_precision_pct": 75.0,
                "resolved_take_n": 20,
                "timeout_rate_pct": 5.0,
                "all_take_win_rate_pct": 71.0,
                "threshold": 0.7,
            },
        ]
        pick = choose_for_floor(points, 0.70)
        self.assertEqual(pick["resolved_take_n"], 20)

    def test_formal_rule_prioritizes_precision_floor(self):
        r = {
            "1": {
                "precision_floors": {
                    "60": {"validation": {"resolved_take_n": 100, "timeout_rate_pct": 0.0}},
                    "65": {"validation": None},
                    "70": {"validation": None},
                    "75": {"validation": None},
                    "80": {"validation": None},
                }
            },
            "2": {
                "precision_floors": {
                    "60": {"validation": {"resolved_take_n": 20, "timeout_rate_pct": 0.0}},
                    "65": {"validation": {"resolved_take_n": 10, "timeout_rate_pct": 0.0}},
                    "70": {"validation": None},
                    "75": {"validation": None},
                    "80": {"validation": None},
                }
            },
            "3": {
                "precision_floors": {
                    "60": {"validation": None},
                    "65": {"validation": None},
                    "70": {"validation": None},
                    "75": {"validation": None},
                    "80": {"validation": None},
                }
            },
        }
        pick = choose_formal_rule(r)
        self.assertEqual(pick["horizon_min"], 2)
        self.assertEqual(pick["precision_floor_pct"], 65)

    def test_minimum_take_not_tiny(self):
        self.assertGreaterEqual(MIN_RESOLVED_TAKES, 10)


if __name__ == "__main__":
    unittest.main()
