from __future__ import annotations

import unittest

from market_radar.wd5g_replay import (
    OVERHEAT_THRESHOLD,
    summarize_policy,
    promotion_assessment,
)


class WD5GReplayTests(unittest.TestCase):
    def test_frozen_health_threshold(self):
        self.assertAlmostEqual(
            OVERHEAT_THRESHOLD,
            5.481925222153388,
        )

    def test_summary_skips_not_counted_as_trades(self):
        rows = [
            {
                "x": 2.0,
                "x_action": "KEEP",
            },
            {
                "x": 0.0,
                "x_action": "SKIP",
            },
            {
                "x": -1.0,
                "x_action": "REVERSE",
            },
        ]
        s = summarize_policy(rows, "x")
        self.assertEqual(s["trade_n"], 2)
        self.assertEqual(s["skip_n"], 1)
        self.assertEqual(s["win_n"], 1)
        self.assertEqual(s["loss_n"], 1)
        self.assertAlmostEqual(s["win_rate_pct"], 50.0)

    def test_assessment_rejects_reversal_worse_than_health_only(self):
        out = promotion_assessment(
            {"net_pnl": -100},
            {"net_pnl": -50},
            {"net_pnl": -60},
            {"win_or_skip_pct": 60},
            {"kept_original_pct": 90},
            {"kept_original_pct": 90},
            {"net_pnl": 10},
        )
        self.assertEqual(
            out["status"],
            "END_TO_END_POLICY_NOT_READY",
        )
        self.assertFalse(
            out["requirements"][
                "primary_pnl_not_worse_than_health_only"
            ]
        )

    def test_summary_net_pnl(self):
        rows = [
            {"x": 2.0, "x_action": "KEEP"},
            {"x": 0.0, "x_action": "SKIP"},
            {"x": -1.0, "x_action": "REVERSE"},
        ]
        self.assertAlmostEqual(
            summarize_policy(rows, "x")["net_pnl"],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
