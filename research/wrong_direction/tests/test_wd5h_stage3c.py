from __future__ import annotations

import unittest

from research.wrong_direction.wd5h_stage3c import (
    MIN_USABLE_RESOLVED_TAKES,
    best_precision,
    choose_for_floor,
    threshold_metrics,
    validation_frontier,
)


class WD5HStage3CTests(unittest.TestCase):
    def rows(self):
        return [
            {
                "primary_meta_label": "META_WIN",
                "meta_opened_at_ms": "0",
                "primary_final_net_usdt": "0",
            },
            {
                "primary_meta_label": "META_LOSS",
                "meta_opened_at_ms": "60000",
                "primary_final_net_usdt": "0",
            },
            {
                "primary_meta_label": "TIMEOUT",
                "meta_opened_at_ms": "120000",
                "primary_final_net_usdt": "1.25",
            },
        ]

    def test_threshold_metrics_keeps_timeout_separate(self):
        m = threshold_metrics(
            self.rows(), [0.9, 0.8, 0.7], 0.7
        )
        self.assertEqual(m["meta_win_n"], 1)
        self.assertEqual(m["meta_loss_n"], 1)
        self.assertEqual(m["timeout_n"], 1)
        self.assertEqual(m["take_resolved_n"], 2)
        self.assertAlmostEqual(
            m["resolved_precision_pct"], 50.0
        )

    def test_frontier_enforces_min_resolved(self):
        f = validation_frontier(
            self.rows(), [0.9, 0.8, 0.7], 2
        )
        self.assertTrue(f)
        self.assertTrue(
            all(x["take_resolved_n"] >= 2 for x in f)
        )

    def test_choose_floor_returns_none_when_unavailable(self):
        rows = [
            {
                "resolved_precision_pct": 55.0,
                "take_resolved_n": 20,
                "threshold": 0.5,
            }
        ]
        self.assertIsNone(choose_for_floor(rows, 0.60))

    def test_choose_floor_maximizes_take_count(self):
        rows = [
            {
                "resolved_precision_pct": 70.0,
                "take_resolved_n": 10,
                "threshold": 0.8,
            },
            {
                "resolved_precision_pct": 65.0,
                "take_resolved_n": 20,
                "threshold": 0.7,
            },
        ]
        got = choose_for_floor(rows, 0.60)
        self.assertEqual(got["take_resolved_n"], 20)

    def test_best_precision_prioritizes_precision(self):
        rows = [
            {
                "resolved_precision_pct": 60.0,
                "take_resolved_n": 20,
            },
            {
                "resolved_precision_pct": 70.0,
                "take_resolved_n": 10,
            },
        ]
        self.assertEqual(
            best_precision(rows)["resolved_precision_pct"],
            70.0,
        )

    def test_min_usable_is_not_tiny(self):
        self.assertGreaterEqual(
            MIN_USABLE_RESOLVED_TAKES, 10
        )


if __name__ == "__main__":
    unittest.main()
