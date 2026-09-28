from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.control_state import (
    get_control_state,
    set_control_mode,
    valid_control_token,
)


class Stage14ControlTests(unittest.TestCase):
    def test_control_token_is_required_and_exact(self):
        with patch.dict(
            os.environ,
            {"CONTROL_API_TOKEN": "secret-token"},
            clear=False,
        ):
            self.assertTrue(valid_control_token("secret-token"))
            self.assertFalse(valid_control_token("wrong"))
            self.assertFalse(valid_control_token(None))

    def test_control_modes_persist_and_keep_exits_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "control.sqlite3")
            env = {
                "DATABASE_URL": "",
                "BABABOT_DB_PATH": db,
                "PAPER_TRADING_ENABLED": "true",
            }
            with patch.dict(os.environ, env, clear=False):
                paused = set_control_mode(
                    "PAUSE_ENTRIES",
                    note="test",
                )
                self.assertEqual(paused["mode"], "PAUSE_ENTRIES")
                self.assertFalse(paused["entries_enabled"])
                self.assertTrue(paused["lifecycle_exits_enabled"])
                self.assertFalse(paused["live_order_submission_enabled"])

                again = get_control_state()
                self.assertEqual(again["mode"], "PAUSE_ENTRIES")

                exit_only = set_control_mode("EXIT_ONLY")
                self.assertEqual(exit_only["mode"], "EXIT_ONLY")
                self.assertFalse(exit_only["entries_enabled"])
                self.assertTrue(exit_only["lifecycle_exits_enabled"])

                running = set_control_mode("RUN")
                self.assertTrue(running["entries_enabled"])
                self.assertTrue(running["lifecycle_exits_enabled"])

    def test_invalid_control_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "control.sqlite3")
            with patch.dict(
                os.environ,
                {"DATABASE_URL": "", "BABABOT_DB_PATH": db},
                clear=False,
            ):
                with self.assertRaises(ValueError):
                    set_control_mode("BUY_NOW")


if __name__ == "__main__":
    unittest.main()
