from __future__ import annotations

import unittest

from research.profit_protection_v4.stage1i_5s_failure_anatomy import (
    classify_apparent_failure,
    persistence_class,
)


class PPV4Stage1IFailureAnatomyTests(unittest.TestCase):
    def row(self) -> dict:
        return {
            "peak5": 0.40,
            "true_mfe": 1.00,
            "actual_post_entry_mfe": 0.50,
        }

    def test_false_eligibility_when_actual_mfe_below_arm(self) -> None:
        row = self.row()
        row["actual_post_entry_mfe"] = 0.20
        self.assertEqual(
            classify_apparent_failure(row),
            "FALSE_MFE_ELIGIBILITY_POST_ENTRY_LT_030",
        )

    def test_benchmark_contamination_dominant(self) -> None:
        row = self.row()
        row["peak5"] = 0.45
        row["actual_post_entry_mfe"] = 0.50
        row["true_mfe"] = 1.00
        self.assertEqual(
            classify_apparent_failure(row),
            "BENCHMARK_CONTAMINATION_DOMINANT",
        )

    def test_mixed_contamination_and_true_miss(self) -> None:
        row = self.row()
        row["peak5"] = 0.20
        row["actual_post_entry_mfe"] = 0.50
        row["true_mfe"] = 1.00
        self.assertEqual(
            classify_apparent_failure(row),
            "MIXED_CONTAMINATION_PLUS_TRUE_5S_MISS",
        )

    def test_clean_true_5s_miss(self) -> None:
        row = self.row()
        row["peak5"] = 0.20
        row["actual_post_entry_mfe"] = 0.50
        row["true_mfe"] = 0.50
        self.assertEqual(
            classify_apparent_failure(row),
            "TRUE_POST_ENTRY_5S_MISS",
        )

    def test_persistence_classes(self) -> None:
        self.assertEqual(
            persistence_class({"near_90_longest_run_s": 1}),
            "FLASH_<=1S",
        )
        self.assertEqual(
            persistence_class({"near_90_longest_run_s": 2}),
            "SHORT_2S",
        )
        self.assertEqual(
            persistence_class({"near_90_longest_run_s": 4}),
            "SUB5S_3_4S",
        )
        self.assertEqual(
            persistence_class({"near_90_longest_run_s": 5}),
            "PERSISTENT_GE5S",
        )


if __name__ == "__main__":
    unittest.main()
