from __future__ import annotations

import unittest

from research.wrong_direction.wd5e_multihead import (
    MICRO_FEATURES,
    derive_micro_features,
    wd5e_conclusion,
)


class WD5EMultiHeadTests(unittest.TestCase):
    def _rows(self):
        rows = []
        start = 1_000_000
        for i in range(30):
            o = 100 + i * 0.1
            c = o + (0.08 if i < 27 else 0.01)
            h = max(o, c) + 0.04
            l = min(o, c) - 0.02
            quote = 1000 + i * 10
            rows.append([
                start + i * 60_000,
                str(o), str(h), str(l), str(c),
                "10",
                start + (i + 1) * 60_000 - 1,
                str(quote),
                "100",
                "5",
                str(quote * 0.55),
            ])
        return rows

    def test_feature_shape(self):
        out = derive_micro_features(self._rows(), "LONG", 5.0)
        self.assertEqual(set(out), set(MICRO_FEATURES))

    def test_long_extreme_distance_nonnegative(self):
        out = derive_micro_features(self._rows(), "LONG", 5.0)
        self.assertGreaterEqual(
            out["f_micro_distance_selected_extreme_15m"], 0
        )

    def test_short_taker_share_is_symmetric(self):
        long = derive_micro_features(self._rows(), "LONG", 5.0)
        short = derive_micro_features(self._rows(), "SHORT", 5.0)
        self.assertAlmostEqual(
            long["f_micro_selected_taker_share_3m"]
            + short["f_micro_selected_taker_share_3m"],
            1.0,
            places=6,
        )

    def test_conclusion_blocks_weak_reversal(self):
        head = lambda va, ta: {
            "selected": {
                "validation": {"auc": va},
                "test": {"auc": ta},
            },
            "variants": {
                "x": {
                    "validation": {"auc": va},
                    "test": {"auc": ta},
                }
            },
        }
        heads = {
            "continuation_health": head(0.78, 0.76),
            "path_expectation_recovered": head(0.80, 0.71),
            "reversal_thesis": head(0.66, 0.57),
        }
        nonlinear = {
            "selected": {
                "validation": {"auc": 0.63},
                "test": {"auc": 0.61},
            }
        }
        novel = {"metrics": {"auc": 0.40}}
        result = wd5e_conclusion(heads, nonlinear, novel)
        self.assertEqual(
            result["reversal_thesis_status"],
            "NO_ROBUST_REVERSAL_HEAD",
        )
        self.assertEqual(result["production_authority"], "NONE")

    def test_reversal_pressure_positive(self):
        out = derive_micro_features(self._rows(), "LONG", 5.0)
        self.assertGreater(out["f_micro_reversal_pressure"], 0)


if __name__ == "__main__":
    unittest.main()
