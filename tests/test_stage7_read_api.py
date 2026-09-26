from __future__ import annotations

import unittest

from market_radar.read_api import candidates_view, latest_summary, symbol_view


def sample_scan() -> dict:
    return {
        "scan_started_at_ms": 100,
        "scan_finished_at_ms": 200,
        "candle_close_time_ms": 150,
        "interval": "5m",
        "universe_count": 500,
        "completed_count": 500,
        "failed_count": 0,
        "moving_candidate_count": 2,
        "ignition_count": 1,
        "expansion_count": 1,
        "exhaustion_count": 0,
        "long_decision_count": 1,
        "short_decision_count": 0,
        "no_trade_decision_count": 1,
        "moving_candidates": [
            {
                "symbol": "SOLUSDT",
                "candle_close_time_ms": 150,
                "stage": "IGNITION",
                "decision": "LONG",
                "long_score": 82.0,
                "short_score": 20.0,
                "score_gap": 62.0,
                "score_edge": 62.0,
                "direction_hint": "UP",
                "ret_5m_pct": 0.7,
                "ret_15m_pct": 1.1,
                "ret_1h_pct": 2.3,
                "volume_ratio": 2.1,
                "decision_reasons": ["confirm:volume_expansion"],
                "decision_context_confirmations": 4,
                "decision_context_conflicts": 0,
                "decision_context_balance": 4,
                "market_context": {
                    "structure_status": "BREAKOUT",
                    "taker_bias": "BUY",
                    "taker_buy_share": 0.64,
                    "raw_oi_change_pct": 2.5,
                    "oi_interpretation": "FRESH_LONG_PARTICIPATION",
                    "funding_rate": 0.0001,
                    "market_regime": "BULL",
                    "context_errors": [],
                },
            },
            {
                "symbol": "ENAUSDT",
                "candle_close_time_ms": 150,
                "stage": "EXPANSION",
                "decision": "NO TRADE",
                "long_score": 61.0,
                "short_score": 58.0,
                "score_gap": 3.0,
                "score_edge": 3.0,
                "direction_hint": "UP",
                "ret_5m_pct": 0.4,
                "ret_15m_pct": 0.8,
                "ret_1h_pct": 1.0,
                "volume_ratio": 1.8,
                "decision_reasons": ["edge_below_10"],
                "decision_context_confirmations": 0,
                "decision_context_conflicts": 0,
                "decision_context_balance": 0,
                "market_context": {
                    "structure_status": "NO_STRUCTURAL_BREAK",
                    "taker_bias": "BALANCED",
                    "taker_buy_share": 0.50,
                    "raw_oi_change_pct": 0.2,
                    "oi_interpretation": "UNRESOLVED",
                    "funding_rate": 0.0001,
                    "market_regime": "SIDEWAYS",
                    "context_errors": [],
                },
            },
        ],
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "candle_close_time_ms": 150,
                "close": 80000.0,
                "quote_volume_5m": 10000000.0,
                "quote_volume_24h": 9000000000.0,
                "price_change_pct_24h": 1.2,
            }
        ],
    }


class Stage7ReadApiTests(unittest.TestCase):
    def test_latest_summary_is_compact_and_contains_candidates(self):
        result = latest_summary(sample_scan())
        self.assertEqual(result["universe_count"], 500)
        self.assertEqual(result["long_decision_count"], 1)
        self.assertEqual(len(result["candidates"]), 2)
        self.assertNotIn("symbols", result)

    def test_candidates_filter_by_decision(self):
        result = candidates_view(sample_scan(), decision="LONG")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["candidates"][0]["symbol"], "SOLUSDT")

    def test_candidates_filter_by_stage(self):
        result = candidates_view(sample_scan(), stage="EXPANSION")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["candidates"][0]["symbol"], "ENAUSDT")

    def test_symbol_view_returns_candidate_when_moving(self):
        result = symbol_view(sample_scan(), "solusdt")
        self.assertIsNotNone(result)
        self.assertEqual(result["candidate"]["symbol"], "SOLUSDT")
        self.assertEqual(result["candidate"]["decision"], "LONG")

    def test_symbol_view_returns_snapshot_when_not_moving(self):
        result = symbol_view(sample_scan(), "BTCUSDT")
        self.assertIsNotNone(result)
        self.assertIsNone(result["candidate"])
        self.assertEqual(result["snapshot"]["close"], 80000.0)

    def test_symbol_view_returns_none_when_unknown(self):
        self.assertIsNone(symbol_view(sample_scan(), "UNKNOWNUSDT"))


if __name__ == "__main__":
    unittest.main()
