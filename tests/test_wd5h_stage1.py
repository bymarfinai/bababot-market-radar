from __future__ import annotations

import unittest

from market_radar.wd5h_stage1 import (
    LABEL_MAP,
    feature_family,
    thesis_label,
)


class WD5HStage1Tests(unittest.TestCase):
    def test_label_map_is_exhaustive_for_wd1(self):
        self.assertEqual(
            set(LABEL_MAP),
            {
                "CORRECT_RUNNER",
                "RECOVERED_DRAWDOWN",
                "RIGHT_THEN_FAILURE",
                "TRUE_WRONG_DIRECTION",
                "STALL_NO_EDGE",
            },
        )

    def test_winner_labels_merge_clean_and_recovered(self):
        self.assertEqual(
            thesis_label({"future_outcome_label": "CORRECT_RUNNER"}),
            "VALID_WINNER",
        )
        self.assertEqual(
            thesis_label({
                "future_outcome_label": "RECOVERED_DRAWDOWN"
            }),
            "VALID_WINNER",
        )

    def test_failure_classes_remain_distinct(self):
        for label in (
            "RIGHT_THEN_FAILURE",
            "TRUE_WRONG_DIRECTION",
            "STALL_NO_EDGE",
        ):
            self.assertEqual(
                thesis_label({"future_outcome_label": label}),
                label,
            )

    def test_feature_family_market_relative(self):
        self.assertEqual(
            feature_family("f_f_coin_minus_market_5m"),
            "MARKET_RELATIVE",
        )

    def test_feature_family_micro(self):
        self.assertEqual(
            feature_family("f_micro_side_ret_5m"),
            "MICRO_PATH",
        )


if __name__ == "__main__":
    unittest.main()
