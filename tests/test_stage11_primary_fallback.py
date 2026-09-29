from __future__ import annotations

import unittest
from unittest.mock import patch

from market_radar.multi_model import (
    STAGE11B_VERSION,
    run_stage11b_failover,
)


class Stage11BFailoverTests(unittest.TestCase):
    def call(self, alternate=("thirty", "thirty/gpt-5.6-luna")) -> dict:
        return run_stage11b_failover(
            signal_id="TEST:1:LONG",
            reviewed_at_ms=1,
            payload={"symbol": "TESTUSDT", "direction": "LONG"},
            system_prompt="test",
            failed_target=("clario", "gemini-3.7-flash"),
            alternate_target=alternate,
        )

    @patch("market_radar.multi_model.save_model_review")
    @patch("market_radar.multi_model.call_model_review")
    def test_single_alternate_approve_is_final(self, model_call, save):
        model_call.return_value = {
            "verdict": "APPROVE",
            "confidence": 0.8,
            "reasons": ["aligned"],
            "risk_flags": [],
        }
        result = self.call()
        self.assertEqual(result["version"], STAGE11B_VERSION)
        self.assertEqual(result["mode"], "FAILOVER_ONLY")
        self.assertEqual(result["final_verdict"], "APPROVE")
        self.assertEqual(result["fallback_reason"], "alternate_fast_lane_succeeded")
        model_call.assert_called_once()
        save.assert_called_once()
        self.assertEqual(save.call_args.kwargs["role"], "FAST_FAILOVER")

    @patch("market_radar.multi_model.save_model_review")
    @patch("market_radar.multi_model.call_model_review")
    def test_single_alternate_watch_remains_watch(self, model_call, save):
        model_call.return_value = {
            "verdict": "WATCH",
            "confidence": 0.6,
            "reasons": ["mixed"],
            "risk_flags": [],
        }
        result = self.call()
        self.assertEqual(result["final_verdict"], "WATCH")
        model_call.assert_called_once()
        save.assert_called_once()

    @patch("market_radar.multi_model.save_model_review")
    @patch("market_radar.multi_model.call_model_review")
    def test_alternate_failure_fails_closed(self, model_call, save):
        model_call.side_effect = TimeoutError("provider down")
        result = self.call()
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["final_verdict"], "VETO")
        self.assertEqual(result["fallback_reason"], "alternate_fast_lane_failed")
        model_call.assert_called_once()
        save.assert_called_once()
        self.assertEqual(save.call_args.kwargs["status"], "ERROR")

    @patch("market_radar.multi_model.save_model_review")
    @patch("market_radar.multi_model.call_model_review")
    def test_no_alternate_fails_closed_without_call(self, model_call, save):
        result = self.call(alternate=None)
        self.assertEqual(result["status"], "NO_ALTERNATE")
        self.assertEqual(result["final_verdict"], "VETO")
        self.assertEqual(result["fallback_reason"], "no_alternate_fast_lane")
        model_call.assert_not_called()
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
