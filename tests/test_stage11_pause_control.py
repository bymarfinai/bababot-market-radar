from __future__ import annotations

import unittest
from unittest.mock import patch

from market_radar.ai_approval import process_pending_approvals, start_pending_approval_worker


class Stage11PauseControlTests(unittest.TestCase):
    @patch("market_radar.ai_approval.get_pending_entry_signals")
    @patch("market_radar.ai_approval.get_control_state")
    def test_pause_skips_stage11_before_querying_candidates(self, control, pending):
        control.return_value = {
            "mode": "PAUSE_ENTRIES",
            "entries_enabled": False,
            "updated_at_ms": 123,
        }
        result = process_pending_approvals()
        self.assertEqual(result["status"], "PAUSED")
        self.assertEqual(result["processed"], 0)
        pending.assert_not_called()

    @patch("market_radar.ai_approval.get_control_state")
    def test_pause_does_not_start_worker(self, control):
        control.return_value = {
            "mode": "PAUSE_ENTRIES",
            "entries_enabled": False,
            "updated_at_ms": 123,
        }
        self.assertFalse(start_pending_approval_worker())

    @patch("market_radar.ai_approval.get_pending_entry_signals")
    @patch("market_radar.ai_approval.get_control_state")
    def test_run_drops_candidates_older_than_run_transition(self, control, pending):
        control.return_value = {
            "mode": "RUN",
            "entries_enabled": True,
            "updated_at_ms": 1_000,
        }
        pending.return_value = [
            {"signal_id": "old", "signal_time_ms": 999},
        ]
        result = process_pending_approvals()
        self.assertEqual(result["status"], "IDLE")
        self.assertEqual(result["processed"], 0)


if __name__ == "__main__":
    unittest.main()
