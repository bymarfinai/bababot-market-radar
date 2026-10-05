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
                    "clario:gpt-5.6-sol,"
                    "thirty:thirty/gpt-5.6-sol"
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
        with patch(
            "market_radar.paper_trading.process_approved_signal",
            return_value={"status": "FILLED"},
        ) as handoff:
            result = review_signal(
                good_signal(),
                target=("clario", "gpt-5.6-sol"),
                now_ms=1_300_000,
            )
        handoff.assert_called_once_with("SOLUSDT:1000000:LONG")
        self.assertEqual(result["stage13_handoff"]["status"], "FILLED")
        self.assertEqual(result["risk_verdict"], "PASS")
        self.assertEqual(result["ai_verdict"], "APPROVE")
        self.assertEqual(result["final_verdict"], "APPROVE")
        self.assertFalse(result["fast_pool"]["fallback_used"])
        self.assertEqual(ai_call.call_count, 1)
        save_model.assert_called_once()
        save.assert_called_once()

    @patch("market_radar.ai_approval.update_entry_latency")
    @patch("market_radar.ai_approval.run_stage11b_failover")
    @patch("market_radar.ai_approval.save_model_review")
    @patch("market_radar.ai_approval.save_entry_approval")
    @patch("market_radar.ai_approval.call_ai_entry_review")
    def test_primary_error_routes_once_to_stage11b(
        self, ai_call, save, save_model, failover, telemetry
    ):
        ai_call.side_effect = TimeoutError("clario timeout")
        failover.return_value = {
            "status": "OK",
            "final_verdict": "WATCH",
            "fallback_reason": "alternate_fast_lane_succeeded",
            "alternate": {
                "status": "OK",
                "provider": "thirty",
                "model": "thirty/gpt-5.6-luna",
                "verdict": "WATCH",
                "confidence": 0.7,
                "reasons": ["fallback lane reviewed"],
                "risk_flags": [],
            },
        }
        result = review_signal(
            good_signal(),
            target=("clario", "gpt-5.6-sol"),
            now_ms=1_300_000,
        )
        self.assertEqual(result["final_verdict"], "WATCH")
        self.assertTrue(result["fast_pool"]["fallback_used"])
        self.assertEqual(ai_call.call_count, 1)
        failover.assert_called_once()
        self.assertEqual(
            failover.call_args.kwargs["alternate_target"],
            ("thirty", "thirty/gpt-5.6-sol"),
        )
        self.assertEqual(save_model.call_count, 1)

    @patch("market_radar.ai_approval.update_entry_latency")
    @patch("market_radar.ai_approval.run_stage11b_failover")
    @patch("market_radar.ai_approval.save_model_review")
    @patch("market_radar.ai_approval.save_entry_approval")
    @patch("market_radar.ai_approval.call_ai_entry_review")
    def test_stage11b_failure_fails_closed(
        self, ai_call, save, save_model, failover, telemetry
    ):
        ai_call.side_effect = TimeoutError("provider down")
        failover.return_value = {
            "status": "ERROR",
            "final_verdict": "VETO",
            "fallback_reason": "alternate_fast_lane_failed",
            "alternate": {"status": "ERROR"},
        }
        result = review_signal(
            good_signal(),
            target=("clario", "gpt-5.6-sol"),
            now_ms=1_300_000,
        )
        self.assertEqual(result["ai_verdict"], "ERROR")
        self.assertEqual(result["final_verdict"], "VETO")
        self.assertTrue(result["fast_pool"]["fallback_used"])
        self.assertEqual(ai_call.call_count, 1)
        failover.assert_called_once()
        self.assertEqual(save_model.call_count, 1)

    def test_fast_pool_uses_two_distinct_default_lanes(self):
        from market_radar.ai_approval import _fast_pool_targets, _workers

        self.assertEqual(
            _fast_pool_targets(),
            [
                ("clario", "gpt-5.6-sol"),
                ("thirty", "thirty/gpt-5.6-sol"),
            ],
        )
        self.assertEqual(_workers(), 2)


if __name__ == "__main__":
    unittest.main()
