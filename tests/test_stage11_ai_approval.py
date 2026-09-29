from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_radar.ai_approval import (
    _parse_ai_response,
    evaluate_entry_risk,
    review_signal,
)


def good_signal() -> dict:
    return {
        "signal_id": "SOLUSDT:1000000:LONG",
        "symbol": "SOLUSDT",
        "side": "LONG",
        "signal_time_ms": 1_000_000,
        "signal_price": 200.0,
        "stage": "IGNITION",
        "long_score": 82.0,
        "short_score": 20.0,
        "score_edge": 62.0,
        "volume_ratio": 2.5,
        "structure_status": "BREAKOUT",
        "taker_bias": "BUY",
        "raw_oi_change_pct": 0.3,
        "funding_rate": 0.0001,
        "market_regime": "BULL",
        "decision_context_balance": 4,
        "decision_reasons_json": '["score_pass","context_confirmed"]',
        "snapshot_json": "{}",
    }


class Stage11ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "AI_APPROVAL_MAX_AGE_MINUTES": "15",
                "AI_APPROVAL_ENABLED": "true",
                "AI_FAST_POOL_TARGETS": (
                    "clario:gemini-3.7-flash,"
                    "thirty:thirty/gpt-5.6-luna"
                ),
                "AI_APPROVAL_WORKERS": "2",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_good_signal_passes_deterministic_risk_gate(self):
        result = evaluate_entry_risk(good_signal(), now_ms=1_300_000)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["reasons"], [])

    def test_structural_conflict_fails_risk_gate(self):
        signal = good_signal()
        signal["structure_status"] = "BREAKDOWN"
        result = evaluate_entry_risk(signal, now_ms=1_300_000)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("hard_structural_conflict", result["reasons"])

    def test_stale_signal_fails_risk_gate(self):
        result = evaluate_entry_risk(good_signal(), now_ms=2_000_001)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("stale_signal", result["reasons"])

    def test_stage6_score_floor_is_preserved(self):
        signal = good_signal()
        signal["long_score"] = 67.9
        result = evaluate_entry_risk(signal, now_ms=1_300_000)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("winning_score_below_stage6_floor", result["reasons"])

    def test_ai_json_is_strictly_normalized(self):
        payload = {
            "content": [
                {
                    "type": "text",
                    "text": (
                        '{"verdict":"APPROVE","confidence":0.82,'
                        '"reasons":["aligned"],"risk_flags":[]}'
                    ),
                }
            ]
        }
        result = _parse_ai_response(payload)
        self.assertEqual(result["verdict"], "APPROVE")
        self.assertEqual(result["confidence"], 0.82)

    @patch("market_radar.ai_approval.update_entry_latency")
    @patch("market_radar.ai_approval.save_entry_approval")
    @patch("market_radar.ai_approval.call_ai_entry_review")
    def test_risk_fail_never_calls_ai(self, ai_call, save, telemetry):
        signal = good_signal()
        signal["structure_status"] = "BREAKDOWN"
        result = review_signal(signal, now_ms=1_300_000)
        self.assertEqual(result["final_verdict"], "VETO")
        self.assertEqual(result["ai_verdict"], "NOT_CALLED")
        ai_call.assert_not_called()
        save.assert_called_once()

    @patch("market_radar.ai_approval.update_entry_latency")
    @patch("market_radar.ai_approval.save_model_review")
    @patch("market_radar.ai_approval.save_entry_approval")
    @patch("market_radar.ai_approval.call_ai_entry_review")
    def test_fast_primary_approve_is_final_without_shadow(
        self, ai_call, save, save_model, telemetry
    ):
        ai_call.return_value = {
            "verdict": "APPROVE",
            "confidence": 0.9,
            "reasons": ["context aligned"],
            "risk_flags": [],
        }
        result = review_signal(
            good_signal(),
            target=("clario", "gemini-3.7-flash"),
            now_ms=1_300_000,
        )
        self.assertEqual(result["risk_verdict"], "PASS")
        self.assertEqual(result["ai_verdict"], "APPROVE")
        self.assertEqual(result["final_verdict"], "APPROVE")
        self.assertFalse(result["fast_pool"]["fallback_used"])
        self.assertEqual(ai_call.call_count, 1)
        save_model.assert_called_once()
        save.assert_called_once()

    @patch("market_radar.ai_approval.update_entry_latency")
    @patch("market_radar.ai_approval.save_model_review")
    @patch("market_radar.ai_approval.save_entry_approval")
    @patch("market_radar.ai_approval.call_ai_entry_review")
    def test_primary_error_routes_once_to_other_fast_lane(
        self, ai_call, save, save_model, telemetry
    ):
        ai_call.side_effect = [
            TimeoutError("clario timeout"),
            {
                "verdict": "WATCH",
                "confidence": 0.7,
                "reasons": ["fallback lane reviewed"],
                "risk_flags": [],
            },
        ]
        result = review_signal(
            good_signal(),
            target=("clario", "gemini-3.7-flash"),
            now_ms=1_300_000,
        )
        self.assertEqual(result["final_verdict"], "WATCH")
        self.assertTrue(result["fast_pool"]["fallback_used"])
        self.assertEqual(ai_call.call_count, 2)
        providers = [call.kwargs["provider"] for call in ai_call.call_args_list]
        self.assertEqual(providers, ["clario", "thirty"])
        self.assertEqual(save_model.call_count, 2)

    @patch("market_radar.ai_approval.update_entry_latency")
    @patch("market_radar.ai_approval.save_model_review")
    @patch("market_radar.ai_approval.save_entry_approval")
    @patch("market_radar.ai_approval.call_ai_entry_review")
    def test_all_fast_lanes_failed_fail_closed(
        self, ai_call, save, save_model, telemetry
    ):
        ai_call.side_effect = TimeoutError("provider down")
        result = review_signal(
            good_signal(),
            target=("clario", "gemini-3.7-flash"),
            now_ms=1_300_000,
        )
        self.assertEqual(result["ai_verdict"], "ERROR")
        self.assertEqual(result["final_verdict"], "VETO")
        self.assertTrue(result["fast_pool"]["fallback_used"])
        self.assertEqual(ai_call.call_count, 2)
        self.assertEqual(save_model.call_count, 2)

    def test_fast_pool_uses_two_distinct_default_lanes(self):
        from market_radar.ai_approval import _fast_pool_targets, _workers

        self.assertEqual(
            _fast_pool_targets(),
            [
                ("clario", "gemini-3.7-flash"),
                ("thirty", "thirty/gpt-5.6-luna"),
            ],
        )
        self.assertEqual(_workers(), 2)


if __name__ == "__main__":
    unittest.main()
