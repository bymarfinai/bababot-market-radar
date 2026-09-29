from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from market_radar.fresh_entry_gate import (
    STAGE11C_VERSION,
    evaluate_fresh_entry,
)


NOW = 2_000_000


def candidate(
    side: str = "LONG",
    *,
    structure: str | None = None,
    regime: str = "SIDEWAYS",
) -> dict:
    if structure is None:
        structure = "BREAKOUT" if side == "LONG" else "BREAKDOWN"
    return {
        "signal_id": f"TEST:1:{side}",
        "symbol": "TESTUSDT",
        "side": side,
        "signal_time_ms": NOW - 30_000,
        "reviewed_at_ms": NOW - 20_000,
        "signal_price": 100.0,
        "stage": "EXPANSION",
        "structure_status": structure,
        "market_regime": regime,
        "raw_oi_change_pct": 0.2,
        "decision_reasons_json": "[]",
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
    base = NOW - 300_000
    return [
        row(base + (i + 1) * 60_000, close, taker_share=taker_share)
        for i, close in enumerate(closes)
    ]


def oi(change_pct: float) -> list[dict]:
    first = 1000.0
    last = first * (1.0 + change_pct / 100.0)
    return [
        {"timestamp": NOW - 600_000, "sumOpenInterest": str(first)},
        {"timestamp": NOW - 300_000, "sumOpenInterest": str(last)},
    ]


class Stage11CFreshEntryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "STAGE11C_MAX_SIGNAL_AGE_SECONDS": "180",
                "STAGE11C_MAX_APPROVAL_AGE_SECONDS": "120",
                "STAGE11C_MAX_CHASE_PCT": "0.75",
                "STAGE11C_SOFT_CHASE_PCT": "0.50",
                "STAGE11C_MAX_ADVERSE_PCT": "0.75",
                "STAGE11C_RET1_THRESHOLD_PCT": "0.01",
                "STAGE11C_RET3_THRESHOLD_PCT": "0.03",
                "STAGE11C_TAKER_BUY_SHARE": "0.55",
                "STAGE11C_TAKER_SELL_SHARE": "0.45",
                "STAGE11C_OI_MIN_CHANGE_PCT": "0.05",
                "STAGE11C_IMPULSE_CONCENTRATION_RATIO": "0.80",
                "STAGE11C_IMPULSE_RET1_MIN_PCT": "0.20",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_long_independent_families_enter(self):
        result = evaluate_fresh_entry(
            candidate("LONG", regime="BULL"),
            current_price=100.40,
            klines_1m=rows([100.0, 100.1, 100.2, 100.4], 0.70),
            oi_hist=oi(+0.20),
            now_ms=NOW,
        )
        self.assertEqual(result["version"], STAGE11C_VERSION)
        self.assertEqual(result["verdict"], "ENTER")
        families = result["snapshot"]["evidence_families"]
        self.assertEqual(families["PRICE_STRUCTURE"], "ALIGNED")
        self.assertEqual(families["FLOW"], "ALIGNED")
        self.assertEqual(families["POSITIONING"], "ALIGNED")
        self.assertEqual(families["REGIME"], "ALIGNED")

    def test_short_independent_families_enter(self):
        result = evaluate_fresh_entry(
            candidate("SHORT", regime="BEAR"),
            current_price=99.60,
            klines_1m=rows([100.0, 99.9, 99.8, 99.6], 0.30),
            oi_hist=oi(+0.20),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "ENTER")
        self.assertEqual(
            result["snapshot"]["evidence_families"]["POSITIONING"],
            "ALIGNED",
        )

    def test_bull_regime_cannot_replace_near_entry_support(self):
        result = evaluate_fresh_entry(
            candidate("LONG", regime="BULL"),
            current_price=100.20,
            klines_1m=rows([100.0, 100.05, 100.10, 100.20], 0.50),
            oi_hist=oi(+0.01),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "WAIT")
        self.assertEqual(result["reasons"], ["independent_near_entry_support_missing"])
        self.assertEqual(
            result["snapshot"]["evidence_families"]["REGIME"],
            "ALIGNED",
        )

    def test_soft_chase_requires_flow_and_positioning(self):
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=100.60,
            klines_1m=rows([100.0, 100.05, 100.10, 100.25], 0.50),
            oi_hist=oi(+0.20),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "WAIT")
        self.assertIn("soft_chase_requires_flow_and_positioning", result["reasons"])
        self.assertTrue(result["snapshot"]["soft_chase"])

    def test_soft_chase_can_enter_with_two_independent_near_families(self):
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=100.60,
            klines_1m=rows([100.0, 100.05, 100.10, 100.25], 0.70),
            oi_hist=oi(+0.20),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "ENTER")

    def test_hard_chase_cancels(self):
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=100.80,
            klines_1m=rows([100.0, 100.1, 100.2, 100.4], 0.70),
            oi_hist=oi(+0.20),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "CANCEL")
        self.assertEqual(result["reasons"], ["price_chased_too_far"])

    def test_concentrated_latest_minute_without_independent_support_waits(self):
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=100.30,
            klines_1m=rows([100.0, 100.0, 100.0, 100.30], 0.50),
            oi_hist=oi(-0.20),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "WAIT")
        self.assertTrue(result["snapshot"]["concentrated_impulse"])

    def test_price_family_opposite_cancels(self):
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
            oi_hist=oi(+0.20),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "CANCEL")
        self.assertIn("family:price_structure_opposite", result["reasons"])

    def test_flow_and_positioning_opposite_cancel(self):
        result = evaluate_fresh_entry(
            candidate("LONG"),
            current_price=100.10,
            klines_1m=rows([100.0, 100.05, 100.10, 100.15], 0.30),
            oi_hist=oi(+0.20),
            now_ms=NOW,
        )
        # Price is still aligned, so positive OI is aligned too. Force price-side
        # positioning contradiction using signal-context fallback.
        item = candidate("LONG")
        item["decision_reasons_json"] = '["confirm:oi_fresh_short"]'
        result = evaluate_fresh_entry(
            item,
            current_price=100.10,
            klines_1m=rows([100.0, 100.05, 100.10, 100.15], 0.30),
            oi_hist=None,
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "CANCEL")
        self.assertIn("family:flow_opposite", result["reasons"])
        self.assertIn("family:positioning_opposite", result["reasons"])

    def test_stale_approval_cancels(self):
        item = candidate("LONG")
        item["reviewed_at_ms"] = NOW - 121_000
        result = evaluate_fresh_entry(
            item,
            current_price=100.2,
            klines_1m=rows([100.0, 100.1, 100.2, 100.3], 0.70),
            oi_hist=oi(+0.20),
            now_ms=NOW,
        )
        self.assertEqual(result["verdict"], "CANCEL")
        self.assertIn("approval_stale", result["reasons"])


if __name__ == "__main__":
    unittest.main()
