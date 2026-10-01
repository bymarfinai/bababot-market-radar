from __future__ import annotations

import unittest

from market_radar.wd5a_features import (
    LEAKAGE_DENYLIST,
    _gate_reason_flags,
    _score_components,
    causal_audit,
)


class WD5AFeaturesTests(unittest.TestCase):
    def test_score_components_are_selected_side_aware(self):
        signal = {
            "long_score_components": {
                "activity": 10,
                "momentum": 20,
                "persistence": 30,
                "timeframe_consistency": 40,
            },
            "short_score_components": {
                "activity": 1,
                "momentum": 2,
                "persistence": 3,
                "timeframe_consistency": 4,
            },
        }
        out = _score_components(signal, "SHORT")
        self.assertEqual(out["f_score_component_selected_momentum"], 2.0)
        self.assertEqual(out["f_score_component_opposite_momentum"], 20.0)
        self.assertEqual(out["f_score_component_delta_momentum"], -18.0)

    def test_gate_reason_flags(self):
        flags = _gate_reason_flags(
            '["family:price_structure_aligned","family:flow_opposite"]'
        )
        self.assertEqual(flags["f_gate_reason_family_price_structure_aligned"], 1)
        self.assertEqual(flags["f_gate_reason_family_flow_opposite"], 1)
        self.assertEqual(flags["f_gate_reason_family_flow_aligned"], 0)

    def test_causal_audit_passes_pre_gate_features(self):
        rows = [{
            "opened_at_ms": 1000,
            "gate_checked_at_ms": 980,
            "candle_close_at_ms": 900,
            "signal_created_at_ms": 910,
            "ai_queued_at_ms": 920,
            "ai_started_at_ms": 930,
            "ai_finished_at_ms": 940,
            "stage11c_started_at_ms": 950,
            "stage11c_finished_at_ms": 970,
            "order_created_at_ms": 990,
            "position_opened_at_ms": 1000,
        }]
        audit = causal_audit(rows)
        self.assertTrue(audit["causal_pass"])
        self.assertEqual(
            audit["excluded_post_gate_counts"]["order_created_at_ms"],
            1,
        )

    def test_causal_audit_rejects_post_gate_feature_timestamp(self):
        rows = [{
            "opened_at_ms": 1000,
            "gate_checked_at_ms": 980,
            "stage11c_finished_at_ms": 981,
            "position_opened_at_ms": 1000,
        }]
        audit = causal_audit(rows)
        self.assertFalse(audit["causal_pass"])
        self.assertEqual(
            audit["violation_counts"]["stage11c_finished_after_decision_cutoff"],
            1,
        )

    def test_denylist_contains_outcome_fields(self):
        self.assertIn("realized_pnl", LEAKAGE_DENYLIST)
        self.assertIn("mfe_pct", LEAKAGE_DENYLIST)
        self.assertIn("outcome_label", LEAKAGE_DENYLIST)


if __name__ == "__main__":
    unittest.main()
