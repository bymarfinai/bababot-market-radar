from __future__ import annotations

import unittest

from market_radar.wd5f_conditional_reversal import (
    OVERHEAT_THRESHOLD,
    derive_flow_structure_features,
    derive_oi_features,
    one_sided_reverse_metrics,
    choose_one_sided_reverse_threshold,
    promotion_assessment,
)


class WD5FConditionalReversalTests(unittest.TestCase):
    def _rows(self):
        rows = []
        start = 1_000_000
        for i in range(30):
            o = 100 + i * 0.1
            c = o + (0.08 if i < 27 else -0.04)
            h = max(o, c) + 0.05
            l = min(o, c) - 0.03
            quote = 1000.0
            buy_share = 0.65 if i < 25 else 0.45
            rows.append([
                start + i * 60_000,
                str(o), str(h), str(l), str(c),
                "10",
                start + (i + 1) * 60_000 - 1,
                str(quote),
                "100",
                "5",
                str(quote * buy_share),
            ])
        return rows

    def test_frozen_overheat_threshold(self):
        self.assertAlmostEqual(
            OVERHEAT_THRESHOLD,
            5.481925222153388,
        )

    def test_flow_structure_features_exist(self):
        out = derive_flow_structure_features(
            self._rows(), "LONG"
        )
        self.assertIn("f_f_taker_accel_3m", out)
        self.assertIn("f_f_structure_reversal_score", out)
        self.assertIn("f_f_failed_selected_extreme", out)

    def test_oi_acceleration(self):
        rows = [
            {"timestamp": 1, "sumOpenInterest": "100"},
            {"timestamp": 2, "sumOpenInterest": "101"},
            {"timestamp": 3, "sumOpenInterest": "103"},
            {"timestamp": 4, "sumOpenInterest": "106"},
        ]
        out = derive_oi_features(rows, 1.0, 8.0)
        self.assertGreater(out["f_f_oi_change_5m_pct"], 0)
        self.assertGreater(out["f_f_oi_accel_5m_pct"], 0)

    def test_one_sided_threshold_prefers_high_precision(self):
        y = [1, 1, 1, 0, 0, 0]
        p = [0.9, 0.8, 0.7, 0.6, 0.2, 0.1]
        out = choose_one_sided_reverse_threshold(
            y, p, precision_floor=0.8, min_flags=2
        )
        self.assertIsNotNone(out["selected"])
        self.assertGreaterEqual(
            out["selected"]["reverse_precision"], 0.8
        )

    def test_one_sided_metrics_default_to_no_trade(self):
        m = one_sided_reverse_metrics(
            [1, 0, 1, 0],
            [0.9, 0.8, 0.2, 0.1],
            0.85,
        )
        self.assertEqual(m["flagged_n"], 1)
        self.assertEqual(m["tp_reverse"], 1)
        self.assertEqual(m["default_no_trade_n"], 3)

    def test_research_candidate_passes_asymmetric_gate(self):
        selected = {
            "validation": {"auc": 0.68},
            "test": {"auc": 0.58},
            "novel_symbol_metrics": {"auc": 0.57},
            "one_sided_reverse_gate": {
                "selected": {
                    "reverse_precision": 0.81,
                    "reverse_recall": 0.4,
                }
            },
            "test_one_sided_reverse_gate": {
                "reverse_precision": 0.73,
                "reverse_recall": 0.2,
                "flagged_n": 10,
            },
            "novel_symbol_one_sided_reverse_gate": {
                "reverse_precision": 0.70,
                "reverse_recall": 0.2,
                "flagged_n": 4,
            },
        }
        out = promotion_assessment(selected)
        self.assertEqual(
            out["status"],
            "ONE_SIDED_REVERSAL_CANDIDATE_FOUND",
        )
        self.assertEqual(out["production_authority"], "NONE")

    def test_research_candidate_rejects_low_reverse_precision(self):
        selected = {
            "validation": {"auc": 0.68},
            "test": {"auc": 0.58},
            "novel_symbol_metrics": {"auc": 0.57},
            "one_sided_reverse_gate": {
                "selected": {"reverse_precision": 0.81}
            },
            "test_one_sided_reverse_gate": {
                "reverse_precision": 0.60,
                "reverse_recall": 0.3,
                "flagged_n": 10,
            },
            "novel_symbol_one_sided_reverse_gate": {
                "reverse_precision": 0.70,
                "flagged_n": 4,
            },
        }
        out = promotion_assessment(selected)
        self.assertEqual(
            out["status"], "CONDITIONAL_REVERSAL_NOT_READY"
        )


if __name__ == "__main__":
    unittest.main()
