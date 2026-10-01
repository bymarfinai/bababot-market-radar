from __future__ import annotations

import unittest

from market_radar.wd5b_discovery import (
    Encoder,
    LogisticModel,
    RandomForestModel,
    auc_score,
    binary_metrics,
    triage_metrics,
)


class WD5BDiscoveryTests(unittest.TestCase):
    def test_auc_perfect(self):
        self.assertEqual(auc_score([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]), 1.0)

    def test_auc_reverse(self):
        self.assertEqual(auc_score([0, 0, 1, 1], [0.8, 0.9, 0.1, 0.2]), 0.0)

    def test_binary_metrics(self):
        m = binary_metrics([0, 0, 1, 1], [0.1, 0.6, 0.7, 0.9])
        self.assertAlmostEqual(m["accuracy"], 0.75)
        self.assertAlmostEqual(m["reverse_precision"], 2 / 3)

    def test_triage_abstain(self):
        m = triage_metrics(
            [0, 0, 1, 1],
            [0.1, 0.4, 0.6, 0.9],
            0.2,
            0.8,
        )
        self.assertEqual(m["no_trade_n"], 1)
        self.assertEqual(m["reverse_n"], 1)
        self.assertEqual(m["abstain_n"], 2)
        self.assertEqual(m["decided_accuracy"], 1.0)

    def test_encoder_unseen_category_maps_to_baseline(self):
        rows = [
            {"num": "1", "cat": "A"},
            {"num": "2", "cat": "B"},
        ]
        enc = Encoder(["num", "cat"], {"num": "numeric", "cat": "categorical"}).fit(rows)
        x = enc.transform([{"num": "1.5", "cat": "C"}])[0]
        self.assertEqual(x[-1], 0.0)

    def test_forest_learns_simple_signal(self):
        x = [[-2.0], [-1.0], [-0.5], [0.5], [1.0], [2.0]] * 10
        y = [0, 0, 0, 1, 1, 1] * 10
        model = RandomForestModel(
            trees=20,
            max_depth=2,
            min_leaf=3,
            seed=7,
        ).fit(x, y)
        p = model.predict_proba([[-1.5], [1.5]])
        self.assertLess(p[0], p[1])

    def test_logistic_learns_simple_signal(self):
        x = [[-2.0], [-1.0], [1.0], [2.0]]
        y = [0, 0, 1, 1]
        model = LogisticModel(l2=0.01, epochs=1200, lr=0.15).fit(x, y)
        p = model.predict_proba(x)
        self.assertLess(p[0], 0.5)
        self.assertGreater(p[-1], 0.5)


if __name__ == "__main__":
    unittest.main()
