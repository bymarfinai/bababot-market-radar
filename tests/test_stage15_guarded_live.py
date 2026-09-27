from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.control_state import get_control_state, set_live_armed
from market_radar.live_trading import (
    _hard_stop_pct,
    _leverage,
    _max_notional,
    _notional,
    _stop_client_id,
    live_credentials_configured,
    live_env_enabled,
    preflight,
)


class Stage15GuardedLiveTests(unittest.TestCase):
    def _sqlite_env(self, tmp: str) -> dict[str, str]:
        return {
            "DATABASE_URL": "",
            "BABABOT_DB_PATH": str(Path(tmp) / "live.sqlite3"),
            "LIVE_TRADING_ENABLED": "false",
            "BINANCE_API_KEY": "",
            "BINANCE_API_SECRET": "",
            "LIVE_NOTIONAL_USDT": "25",
            "LIVE_MAX_NOTIONAL_USDT": "50",
            "LIVE_LEVERAGE": "1",
            "LIVE_HARD_STOP_PCT": "1.5",
            "LIVE_MIN_PAPER_CLOSED_TRADES": "0",
            "LIVE_REQUIRE_PAPER_NET_PNL_NONNEGATIVE": "false",
        }

    def test_live_is_locked_without_env_and_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, self._sqlite_env(tmp), clear=False):
                result = preflight(
                    client=None,
                    require_arm=True,
                    require_entry_mode=True,
                )
                self.assertFalse(result["ok"])
                self.assertIn("live_env_disabled", result["reasons"])
                self.assertIn("live_credentials_missing", result["reasons"])
                self.assertFalse(live_env_enabled())
                self.assertFalse(live_credentials_configured())

    def test_live_arm_defaults_false_and_exits_not_equal_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self._sqlite_env(tmp)
            env["LIVE_TRADING_ENABLED"] = "true"
            env["BINANCE_API_KEY"] = "test-key"
            env["BINANCE_API_SECRET"] = "test-secret"
            with patch.dict(os.environ, env, clear=False):
                state = get_control_state()
                self.assertFalse(state["live_armed"])
                self.assertFalse(state["live_entry_submission_enabled"])
                self.assertTrue(state["live_exit_submission_enabled"])

                armed = set_live_armed(True, note="test-only")
                self.assertTrue(armed["live_armed"])
                self.assertTrue(armed["live_entry_submission_enabled"])

    def test_canary_risk_defaults_are_bounded(self):
        with patch.dict(
            os.environ,
            {
                "LIVE_NOTIONAL_USDT": "25",
                "LIVE_MAX_NOTIONAL_USDT": "50",
                "LIVE_LEVERAGE": "1",
                "LIVE_HARD_STOP_PCT": "1.5",
            },
            clear=False,
        ):
            self.assertLessEqual(_notional(), _max_notional())
            self.assertEqual(_leverage(), 1)
            self.assertGreaterEqual(_hard_stop_pct(), 0.5)
            self.assertLessEqual(_hard_stop_pct(), 5.0)

    def test_protective_stop_client_id_is_exchange_safe_length(self):
        cid = _stop_client_id("LIVE:BTCUSDT:example")
        self.assertLessEqual(len(cid), 32)
        self.assertTrue(cid.startswith("BBS"))


if __name__ == "__main__":
    unittest.main()
