from __future__ import annotations

import unittest
from unittest.mock import patch

from market_radar.multi_model import run_primary_fallback


def ok(verdict: str) -> dict:
    return {
        "status": "OK",
        "verdict": verdict,
        "confidence": 0.8,
        "reasons": [],
        "risk_flags": [],
    }


class PrimaryFallbackTests(unittest.TestCase):
    def call(self, shadow: dict, validator: dict) -> dict:
        with patch("market_radar.multi_model._take_slot", return_value=True), patch(
            "market_radar.multi_model._review_model",
            side_effect=[shadow, validator],
        ):
            return run_primary_fallback(
                signal_id="TEST:1:LONG",
                reviewed_at_ms=1,
                payload={"symbol": "TESTUSDT"},
                system_prompt="test",
                primary_error={"error_type": "TimeoutError"},
            )

    def test_requires_dual_approve(self):
        result = self.call(ok("APPROVE"), ok("APPROVE"))
        self.assertEqual(result["final_verdict"], "APPROVE")
        self.assertEqual(result["fallback_reason"], "dual_approve")

    def test_watch_blocks_single_approve(self):
        result = self.call(ok("APPROVE"), ok("WATCH"))
        self.assertEqual(result["final_verdict"], "WATCH")
        self.assertEqual(result["fallback_reason"], "no_dual_approve")

    def test_any_veto_fails_closed(self):
        result = self.call(ok("APPROVE"), ok("VETO"))
        self.assertEqual(result["final_verdict"], "VETO")
        self.assertEqual(result["fallback_reason"], "fallback_veto_present")

    def test_both_errors_veto(self):
        err = {"status": "ERROR"}
        result = self.call(err, err)
        self.assertEqual(result["final_verdict"], "VETO")
        self.assertEqual(result["fallback_reason"], "both_fallback_models_failed")


if __name__ == "__main__":
    unittest.main()
