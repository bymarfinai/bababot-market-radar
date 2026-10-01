from __future__ import annotations

import unittest

from research.wrong_direction.wd5d_features import (
    NEW_FEATURES,
    _family_score,
    derive_features,
    rank_train_features,
    _overheat_rule_metrics,
)


class WD5DFeatureTests(unittest.TestCase):
    def _row(self):
        return {
            "f_ret_5m_pct_for_selected": "1.2",
            "f_ret_15m_pct_for_selected": "2.1",
            "f_ret_1h_pct_for_selected": "3.0",
            "f_median_abs_ret_5m_pct": "0.2",
            "f_gate_side_ret_1m_pct": "0.1",
            "f_gate_side_ret_3m_pct": "0.9",
            "f_gate_taker_share_for_selected": "0.55",
            "f_context_taker_share_for_selected": "0.58",
            "f_volume_ratio_signal": "4.0",
            "f_range_ratio": "3.0",
            "f_trades_ratio": "2.0",
            "f_return_expansion_ratio": "5.0",
            "f_context_raw_oi_change_pct": "0.1",
            "f_selected_score": "85",
            "f_gate_positioning_family": "ALIGNED",
            "f_gate_regime_family": "NEUTRAL",
            "f_gate_flow_family": "OPPOSITE",
            "f_gate_aligned_family_count": "2",
            "f_gate_opposing_family_count": "1",
        }

    def test_family_score(self):
        self.assertEqual(_family_score("ALIGNED"), 1.0)
        self.assertEqual(_family_score("SUPPORTIVE"), 1.0)
        self.assertEqual(_family_score("NEUTRAL"), 0.0)
        self.assertEqual(_family_score("OPPOSITE"), -1.0)

    def test_all_new_features_present(self):
        out = derive_features(self._row())
        self.assertEqual(set(out), set(NEW_FEATURES))

    def test_acceleration(self):
        out = derive_features(self._row())
        self.assertAlmostEqual(out["f_new_accel_5_vs_15"], 0.5)
        self.assertAlmostEqual(out["f_new_accel_15_vs_60"], 0.45)

    def test_micro_fade_heat_positive(self):
        out = derive_features(self._row())
        self.assertGreater(out["f_new_heat_x_micro_fade"], 0)

    def test_train_feature_ranking_prefers_perfect_numeric_signal(self):
        rows = [
            {"x": "0", "z": "1", "meta": "a"},
            {"x": "0.1", "z": "0", "meta": "b"},
            {"x": "0.9", "z": "1", "meta": "c"},
            {"x": "1.0", "z": "0", "meta": "d"},
        ]
        for i, row in enumerate(rows):
            row["label_opportunity_tier"] = "RUNNER"
            row["label_path_style"] = (
                "RECOVERED_WINNER" if i >= 2 else "MISSED_OPPORTUNITY"
            )
            row["future_realized_pnl_pct"] = "0.1" if i >= 2 else "-0.1"
            row["future_max_mfe_pct"] = "1.2"
        ranked = rank_train_features(
            rows,
            "RUNNER_WIN_vs_RUNNER_MISSED",
            ["z", "x"],
            {"z": "numeric", "x": "numeric"},
        )
        self.assertEqual(ranked[0], "x")

    def test_overheat_rule_metrics(self):
        rows = [
            {"f_new_overheat_pressure": "10", "label_path_style": "MISSED_OPPORTUNITY"},
            {"f_new_overheat_pressure": "8", "label_path_style": "RECOVERED_WINNER"},
            {"f_new_overheat_pressure": "2", "label_path_style": "RECOVERED_WINNER"},
            {"f_new_overheat_pressure": "1", "label_path_style": "MISSED_OPPORTUNITY"},
        ]
        m = _overheat_rule_metrics(rows, 5.0)
        self.assertEqual(m["tp_miss"], 1)
        self.assertEqual(m["fp_winner"], 1)
        self.assertEqual(m["tn_winner"], 1)
        self.assertEqual(m["fn_miss"], 1)
        self.assertAlmostEqual(m["balanced_accuracy"], 0.5)

    def test_overheat_pressure_positive(self):
        out = derive_features(self._row())
        self.assertGreater(out["f_new_overheat_pressure"], 0)


if __name__ == "__main__":
    unittest.main()
