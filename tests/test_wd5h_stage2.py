from __future__ import annotations

import unittest

from market_radar.wd5h_stage2 import (
    WIN,
    REJECT_CLASSES,
    chronological_split,
    gate_metrics,
)


class WD5HStage2Tests(unittest.TestCase):
    def test_reject_heads_are_distinct(self):
        self.assertEqual(
            set(REJECT_CLASSES),
            {
                "TRUE_WRONG_DIRECTION",
                "RIGHT_THEN_FAILURE",
                "STALL_NO_EDGE",
            },
        )
        self.assertEqual(WIN, "VALID_WINNER")

    def test_chronological_split_60_20_20(self):
        rows = [
            {"meta_opened_at_ms": str(i)}
            for i in range(100)
        ]
        train, val, test = chronological_split(rows)
        self.assertEqual(len(train), 60)
        self.assertEqual(len(val), 20)
        self.assertEqual(len(test), 20)
        self.assertLess(
            int(train[-1]["meta_opened_at_ms"]),
            int(val[0]["meta_opened_at_ms"]),
        )
        self.assertLess(
            int(val[-1]["meta_opened_at_ms"]),
            int(test[0]["meta_opened_at_ms"]),
        )

    def test_gate_metrics_precision(self):
        rows = [
            {
                "label_thesis_class": "VALID_WINNER",
                "future_realized_pnl": "2",
                "meta_opened_at_ms": "0",
                "meta_position_id": "a",
                "label_opportunity_tier": "RUNNER",
            },
            {
                "label_thesis_class": "TRUE_WRONG_DIRECTION",
                "future_realized_pnl": "-1",
                "meta_opened_at_ms": "86400000",
                "meta_position_id": "b",
                "label_opportunity_tier": "NO_EDGE",
            },
        ]
        m = gate_metrics(rows, [True, True])
        self.assertEqual(m["take_n"], 2)
        self.assertAlmostEqual(
            m["thesis_win_precision_pct"], 50.0
        )
        self.assertAlmostEqual(
            m["realized_win_rate_pct"], 50.0
        )

    def test_gate_metrics_skip_all(self):
        rows = [
            {
                "label_thesis_class": "VALID_WINNER",
                "future_realized_pnl": "2",
                "meta_opened_at_ms": "0",
                "meta_position_id": "a",
                "label_opportunity_tier": "RUNNER",
            }
        ]
        m = gate_metrics(rows, [False])
        self.assertEqual(m["take_n"], 0)
        self.assertIsNone(m["thesis_win_precision_pct"])


if __name__ == "__main__":
    unittest.main()
