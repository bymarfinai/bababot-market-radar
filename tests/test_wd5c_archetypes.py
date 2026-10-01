from __future__ import annotations

import unittest

from market_radar.wd5c_archetypes import (
    capture_class,
    composite_archetype,
    opportunity_tier,
    path_style,
    realized_win_tier,
)


class WD5CArchetypeTests(unittest.TestCase):
    def test_opportunity_tiers(self):
        self.assertEqual(opportunity_tier(2.0), "BIG_RUNNER")
        self.assertEqual(opportunity_tier(1.5), "RUNNER")
        self.assertEqual(opportunity_tier(0.7), "SMALL_EDGE")
        self.assertEqual(opportunity_tier(0.4), "BORDERLINE")
        self.assertEqual(opportunity_tier(0.2), "NO_EDGE")

    def test_realized_win_tiers(self):
        self.assertEqual(realized_win_tier(1.1), "BIG_REALIZED_WIN")
        self.assertEqual(realized_win_tier(0.7), "MEDIUM_REALIZED_WIN")
        self.assertEqual(realized_win_tier(0.1), "SMALL_REALIZED_WIN")
        self.assertEqual(realized_win_tier(-0.1), "NON_WIN")

    def test_capture_class(self):
        self.assertEqual(capture_class(2.0, 1.2)[0], "HIGH_CAPTURE_GE50")
        self.assertEqual(capture_class(2.0, 0.7)[0], "MEDIUM_CAPTURE_25_50")
        self.assertEqual(capture_class(2.0, 0.2)[0], "LOW_CAPTURE_LT25")
        self.assertEqual(capture_class(2.0, -0.1)[0], "MISSED")
        self.assertEqual(
            capture_class(0.3, -0.1)[0],
            "NO_MEANINGFUL_OPPORTUNITY",
        )

    def test_path_style(self):
        self.assertEqual(path_style("RECOVERED_DRAWDOWN"), "RECOVERED_WINNER")
        self.assertEqual(path_style("CORRECT_RUNNER"), "CLEAN_WINNER")
        self.assertEqual(path_style("RIGHT_THEN_FAILURE"), "MISSED_OPPORTUNITY")

    def test_composite(self):
        self.assertEqual(
            composite_archetype(
                "BIG_RUNNER",
                "RECOVERED_WINNER",
                "SMALL_REALIZED_WIN",
            ),
            "BIG_RUNNER_RECOVERED",
        )
        self.assertEqual(
            composite_archetype("RUNNER", "MISSED_OPPORTUNITY", "NON_WIN"),
            "RUNNER_MISSED",
        )


if __name__ == "__main__":
    unittest.main()
