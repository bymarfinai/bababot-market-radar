from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.paper_store import initialize_paper_store
from market_radar.paper_trading import (
    _fill_price,
    _gross_pnl,
    _hard_stop_pct,
    _notional_usdt,
    process_approved_signal,
)


class Stage13PaperTradingTests(unittest.TestCase):
    def test_long_market_entry_slippage_is_adverse(self):
        with patch.dict(os.environ, {"PAPER_SLIPPAGE_BPS": "2"}, clear=False):
            fill = _fill_price(
                market_price=100.0,
                side="LONG",
                action="OPEN",
            )
        self.assertGreater(fill, 100.0)

    def test_long_market_exit_slippage_is_adverse(self):
        with patch.dict(os.environ, {"PAPER_SLIPPAGE_BPS": "2"}, clear=False):
            fill = _fill_price(
                market_price=100.0,
                side="LONG",
                action="CLOSE",
            )
        self.assertLess(fill, 100.0)

    def test_short_market_entry_and_exit_slippage_are_adverse(self):
        with patch.dict(os.environ, {"PAPER_SLIPPAGE_BPS": "2"}, clear=False):
            entry = _fill_price(
                market_price=100.0,
                side="SHORT",
                action="OPEN",
            )
            exit_price = _fill_price(
                market_price=100.0,
                side="SHORT",
                action="CLOSE",
            )
        self.assertLess(entry, 100.0)
        self.assertGreater(exit_price, 100.0)

    def test_long_short_gross_pnl_are_symmetric(self):
        self.assertAlmostEqual(
            _gross_pnl(
                side="LONG",
                entry_price=100.0,
                exit_price=105.0,
                quantity=2.0,
            ),
            10.0,
        )
        self.assertAlmostEqual(
            _gross_pnl(
                side="SHORT",
                entry_price=100.0,
                exit_price=95.0,
                quantity=2.0,
            ),
            10.0,
        )

    @patch("market_radar.paper_trading._execute_open")
    @patch("market_radar.paper_trading.get_paper_order")
    @patch("market_radar.paper_trading.create_order")
    @patch("market_radar.paper_trading.check_fresh_entry")
    @patch("market_radar.paper_trading.has_open_paper_symbol", return_value=False)
    @patch("market_radar.paper_trading._at_open_capacity", return_value=False)
    @patch("market_radar.paper_trading.get_entry_candidate")
    @patch("market_radar.paper_trading.get_control_state")
    @patch("market_radar.paper_trading.paper_trading_enabled", return_value=True)
    def test_approve_enter_executes_immediately(
        self, enabled, control, candidate, capacity, open_symbol,
        gate, create, get_order, execute,
    ):
        control.return_value = {"entries_enabled": True}
        candidate.return_value = {
            "signal_id": "TEST:1:LONG",
            "symbol": "TESTUSDT",
            "side": "LONG",
            "reviewed_at_ms": 100,
            "signal_time_ms": 50,
            "signal_price": 100.0,
            "stage": "IGNITION",
            "long_score": 80.0,
            "short_score": 20.0,
            "score_edge": 60.0,
        }
        gate.return_value = {
            "verdict": "ENTER",
            "checked_at_ms": 120,
            "reasons": ["ret3_aligned"],
            "snapshot": {},
            "version": "stage11c-v1-fresh-direction",
        }
        create.return_value = "ENTRY:TEST:1:LONG:OPEN"
        get_order.return_value = {"order_id": "ENTRY:TEST:1:LONG:OPEN"}
        execute.return_value = {"status": "FILLED", "fill_price": 100.1}

        result = process_approved_signal("TEST:1:LONG")

        self.assertEqual(result["status"], "FILLED")
        gate.assert_called_once()
        create.assert_called_once()
        execute.assert_called_once()

    @patch("market_radar.paper_trading.check_fresh_entry")
    @patch("market_radar.paper_trading.has_open_paper_symbol", return_value=False)
    @patch("market_radar.paper_trading._at_open_capacity", return_value=False)
    @patch("market_radar.paper_trading.get_entry_candidate")
    @patch("market_radar.paper_trading.get_control_state")
    @patch("market_radar.paper_trading.paper_trading_enabled", return_value=True)
    def test_approve_wait_does_not_create_order(
        self, enabled, control, candidate, capacity, open_symbol, gate,
    ):
        control.return_value = {"entries_enabled": True}
        candidate.return_value = {
            "signal_id": "TEST:1:LONG",
            "symbol": "TESTUSDT",
            "side": "LONG",
        }
        gate.return_value = {
            "verdict": "WAIT",
            "reasons": ["fresh_direction_not_confirmed"],
        }
        with patch("market_radar.paper_trading.create_order") as create:
            result = process_approved_signal("TEST:1:LONG")
        self.assertEqual(result["status"], "WAIT")
        create.assert_not_called()

    def test_default_paper_notional_and_no_invented_hard_stop(self):
        with patch.dict(
            os.environ,
            {
                "PAPER_NOTIONAL_USDT": "500",
                "PAPER_HARD_STOP_PCT": "0",
            },
            clear=False,
        ):
            self.assertEqual(_notional_usdt(), 500.0)
            self.assertEqual(_hard_stop_pct(), 0.0)


if __name__ == "__main__":
    unittest.main()
