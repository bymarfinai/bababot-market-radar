from __future__ import annotations

import unittest

from research.wrong_direction.wd5h_stage3b import (
    WeightedLogisticModel,
    average_precision,
    normalized_uniqueness_weights,
    population_splits,
    purge_for_holdout,
    resolved,
)


class WD5HStage3BTests(unittest.TestCase):
    def test_population_split_is_45_15_20_20(self):
        rows = [
            {"meta_opened_at_ms": str(i)}
            for i in range(100)
        ]
        s = population_splits(rows)
        self.assertEqual(len(s["inner_train_pool"]), 45)
        self.assertEqual(len(s["inner_val_pool"]), 15)
        self.assertEqual(len(s["outer_train_pool"]), 60)
        self.assertEqual(len(s["outer_val_pool"]), 20)
        self.assertEqual(len(s["dev_plus_val_pool"]), 80)
        self.assertEqual(len(s["test_pool"]), 20)

    def test_resolved_excludes_timeout(self):
        rows = [
            {"primary_meta_label": "META_WIN"},
            {"primary_meta_label": "META_LOSS"},
            {"primary_meta_label": "TIMEOUT"},
        ]
        self.assertEqual(len(resolved(rows)), 2)

    def test_purge_removes_overlap(self):
        holdout = [{"meta_opened_at_ms": "10000000"}]
        train = [
            {
                "meta_opened_at_ms": "1000000",
                "primary_label_end_ms": "11000000",
            },
            {
                "meta_opened_at_ms": "1000000",
                "primary_label_end_ms": "2000000",
            },
        ]
        kept, info = purge_for_holdout(
            train, holdout, embargo_min=0
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(info["removed_overlap_n"], 1)

    def test_embargo_removes_recent_training_event(self):
        holdout = [{"meta_opened_at_ms": str(60 * 60_000)}]
        train = [
            {
                "meta_opened_at_ms": str(40 * 60_000),
                "primary_label_end_ms": str(41 * 60_000),
            },
            {
                "meta_opened_at_ms": str(20 * 60_000),
                "primary_label_end_ms": str(21 * 60_000),
            },
        ]
        kept, _ = purge_for_holdout(
            train, holdout, embargo_min=30
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(
            int(kept[0]["meta_opened_at_ms"]),
            20 * 60_000,
        )

    def test_uniqueness_weights_are_normalized(self):
        rows = [
            {"primary_uniqueness_weight": 0.1},
            {"primary_uniqueness_weight": 0.2},
            {"primary_uniqueness_weight": 0.3},
        ]
        w = normalized_uniqueness_weights(rows)
        self.assertAlmostEqual(sum(w) / len(w), 1.0)

    def test_average_precision_perfect(self):
        self.assertAlmostEqual(
            average_precision([1, 0, 1], [0.9, 0.1, 0.8]),
            1.0,
        )

    def test_weighted_logistic_learns_direction(self):
        x = [[-2.0], [-1.0], [1.0], [2.0]]
        y = [0, 0, 1, 1]
        m = WeightedLogisticModel(
            l2=0.1, epochs=500, lr=0.1
        ).fit(x, y, [1.0, 1.0, 1.0, 1.0])
        p = m.predict_proba([[-1.5], [1.5]])
        self.assertLess(p[0], p[1])

    def test_weighted_logistic_accepts_unequal_weights(self):
        x = [[-1.0], [0.0], [1.0]]
        y = [0, 0, 1]
        m = WeightedLogisticModel(
            l2=0.1, epochs=20, lr=0.1
        ).fit(x, y, [0.1, 0.2, 3.0])
        self.assertEqual(len(m.weights), 2)


if __name__ == "__main__":
    unittest.main()
