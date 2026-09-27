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
