from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_radar.read_api import (
    MCP_PROTOCOL_VERSION,
    candidates_view,
    latest_summary,
    mcp_dispatch,
    symbol_view,
)


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



class Stage7McpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scan_path = Path(self.tmp.name) / "latest_scan.json"
        self.scan_path.write_text(
            json.dumps(sample_scan()),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def rpc(self, method: str, params: dict | None = None, request_id: int = 1):
        return mcp_dispatch(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            },
            scan_path=self.scan_path,
        )

    def test_initialize(self):
        status, payload = self.rpc(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "clientInfo": {"name": "test", "version": "1"},
                "capabilities": {},
            },
        )
        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertEqual(result["protocolVersion"], MCP_PROTOCOL_VERSION)
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(result["serverInfo"]["name"], "bababot-market-radar")

    def test_tools_list_exposes_exactly_three_read_only_tools(self):
        status, payload = self.rpc("tools/list")
        self.assertEqual(status, 200)
        names = [tool["name"] for tool in payload["result"]["tools"]]
        self.assertEqual(
            names,
            ["get_market_radar", "get_moving_coins", "inspect_symbol"],
        )

    def test_get_market_radar_tool(self):
        status, payload = self.rpc(
            "tools/call",
            {"name": "get_market_radar", "arguments": {}},
        )
        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["universe_count"], 500)

    def test_get_moving_coins_tool_filter(self):
        status, payload = self.rpc(
            "tools/call",
            {
                "name": "get_moving_coins",
                "arguments": {"decision": "LONG"},
            },
        )
        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertEqual(result["structuredContent"]["count"], 1)
        self.assertEqual(
            result["structuredContent"]["candidates"][0]["symbol"],
            "SOLUSDT",
        )

    def test_inspect_symbol_tool(self):
        status, payload = self.rpc(
            "tools/call",
            {
                "name": "inspect_symbol",
                "arguments": {"symbol": "SOLUSDT"},
            },
        )
        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertEqual(
            result["structuredContent"]["candidate"]["decision"],
            "LONG",
        )

    def test_unknown_tool_is_protocol_error(self):
        status, payload = self.rpc(
            "tools/call",
            {"name": "place_order", "arguments": {}},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["error"]["code"], -32601)

    def test_scan_not_ready_is_tool_error(self):
        missing = Path(self.tmp.name) / "missing.json"
        status, payload = mcp_dispatch(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "get_market_radar",
                    "arguments": {},
                },
            },
            scan_path=missing,
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["result"]["isError"])
        self.assertEqual(
            payload["result"]["structuredContent"]["error"],
            "scan_not_ready",
        )

    def test_initialized_notification_returns_202_without_body(self):
        status, payload = mcp_dispatch(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            scan_path=self.scan_path,
        )
        self.assertEqual(status, 202)
        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
