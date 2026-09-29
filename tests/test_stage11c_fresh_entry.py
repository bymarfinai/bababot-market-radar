from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_radar.fresh_entry_gate import (
    STAGE11C_VERSION,
    evaluate_fresh_entry,
)


NOW = 2_000_000


def candidate(side: str = "LONG") -> dict:
    return {
        "signal_id": f"TEST:1:{side}",
        "symbol": "TESTUSDT",
        "side": side,
        "signal_time_ms": NOW - 30_000,
        "reviewed_at_ms": NOW - 20_000,
        "signal_price": 100.0,
    }


def row(
    close_time: int,
    close: float,
    *,
    high: float | None = None,
    low: float | None = None,
    taker_share: float = 0.5,
) -> list:
    quote = 1000.0
    buy = quote * taker_share
    return [
        close_time - 59_999,
        str(close),
        str(high if high is not None else close + 0.10),
        str(low if low is not None else close - 0.10),
        str(close),
        "100",
        close_time,
        str(quote),
        100,
        "50",
        str(buy),
        "0",
    ]


def rows(closes: list[float], taker_share: float) -> list[list]:
    base = NOW - 240_000
    return [
        row(base + (i + 1) * 60_000, close, taker_share=taker_share)
        for i, close in enumerate(closes)
    ]


class Stage11CFreshEntryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "STAGE11C_MAX_SIGNAL_AGE_SECONDS": "180",
                "STAGE11C_MAX_APPROVAL_AGE_SECONDS": "120",
                "STAGE11C_MAX_CHASE_PCT": "0.75",
                "STAGE11C_MAX_ADVERSE_PCT": "0.75",
                "STAGE11C_RET1_THRESHOLD_PCT": "0.01",
                "STAGE11C_RET3_THRESHOLD_PCT": "0.03",
                "STAGE11C_TAKER_BUY_SHARE": "0.55",
                "STAGE11C_TAKER_SELL_SHARE": "0.45",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_long_fresh_alignment_enters(self):
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=100.45,
            klines_1m=rows([100.0, 100.1, 100.2, 100.4], 0.70),
            now_ms=NOW,
        )
        self.assertEqual(result["version"], STAGE11C_VERSION)
        self.assertEqual(result["verdict"], "ENTER")
        self.assertIn("ret3_aligned", result["reasons"])
        self.assertIn("taker_aligned", result["reasons"])

    def test_short_fresh_alignment_enters(self):
        result = evaluate_fresh_entry(
            candidate("SHORT"),
            current_price=99.55,
            klines_1m=rows([100.0, 99.9, 99.8, 99.6], 0.30),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "ENTER")
        self.assertGreater(result["snapshot"]["side_ret_3m_pct"], 0)

    def test_chased_price_cancels(self):
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=100.80,
            klines_1m=rows([100.0, 100.1, 100.2, 100.4], 0.70),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "CANCEL")
        self.assertEqual(result["reasons"], ["price_chased_too_far"])

    def test_stale_approval_cancels(self):
        item = candidate("LONG")
        item["reviewed_at_ms"] = NOW - 121_000
        result = evaluate_fresh_entry(
            item,
            current_price=100.2,
            klines_1m=rows([100.0, 100.1, 100.2, 100.3], 0.70),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "CANCEL")
        self.assertIn("approval_stale", result["reasons"])

    def test_opposite_micro_structure_and_momentum_cancel(self):
        custom = [
            row(NOW - 240_000, 100.0, high=100.2, low=99.8, taker_share=0.35),
            row(NOW - 180_000, 100.1, high=100.3, low=99.9, taker_share=0.35),
            row(NOW - 120_000, 100.0, high=100.2, low=99.8, taker_share=0.35),
            row(NOW - 60_000, 99.5, high=99.7, low=99.4, taker_share=0.35),
        ]
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=99.5,
            klines_1m=custom,
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "CANCEL")
        self.assertIn("opposite_micro_structure", result["reasons"])
        self.assertIn("ret3_opposite", result["reasons"])

    def test_mixed_fresh_context_waits(self):
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=100.03,
            klines_1m=rows([100.0, 100.01, 100.0, 100.02], 0.50),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "WAIT")
        self.assertIn("fresh_direction_not_confirmed", result["reasons"])


if __name__ == "__main__":
    unittest.main()
