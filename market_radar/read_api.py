from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .binance import BinancePublicClient
from .control_state import (
    control_token_configured,
    get_control_state,
    set_control_mode,
    set_live_armed,
    valid_control_token,
)
from .execution_handoff import (
    default_execution_handoff_path,
    load_execution_handoff,
)
from .live_store import list_live_orders, list_open_live_positions, live_summary
from .live_trading import preflight as live_preflight
from .paper_store import list_paper_orders, paper_summary
from .persistence import (
    entry_approval_summary,
    list_entry_approvals,
    list_model_reviews,
    list_open_positions,
    list_position_evaluations,
    list_signals,
    model_review_summary,
    persistence_summary,
)


READ_API_VERSION = "stage7-v2"
MCP_PROTOCOL_VERSION = "2025-11-25"
MCP_SERVER_NAME = "bababot-market-radar"
MCP_SERVER_VERSION = "stage7-v1"

MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_market_radar",
        "description": "Read the latest compact BabaBot Market Radar scan and deterministic decisions.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_moving_coins",
        "description": "List current moving candidates, optionally filtered by final decision or movement stage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": ["LONG", "SHORT", "NO TRADE", "NO_TRADE"],
                },
                "stage": {
                    "type": "string",
                    "enum": ["IGNITION", "EXPANSION", "EXHAUSTION"],
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "inspect_symbol",
        "description": "Inspect one symbol from the latest radar scan. Returns full compact candidate context when moving, otherwise the latest Stage 1 snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "minLength": 1,
                }
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    },
]


def load_latest_scan(path: str | os.PathLike[str]) -> dict[str, Any]:
    scan_path = Path(path)
    if not scan_path.exists():
        raise FileNotFoundError(f"scan not available: {scan_path}")
    with scan_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("latest scan must be a JSON object")
    return payload


def compact_candidate(
    item: dict[str, Any],
    *,
    price: float | None = None,
) -> dict[str, Any]:
    """Return only fields AI/MCP/dashboard needs for inspection."""
    ctx = item.get("market_context") or {}
    return {
        "symbol": item.get("symbol"),
        "candle_close_time_ms": item.get("candle_close_time_ms"),
        "price": price,
        "stage": item.get("stage"),
        "decision": item.get("decision"),
        "long_score": item.get("long_score"),
        "short_score": item.get("short_score"),
        "score_gap": item.get("score_gap"),
        "score_edge": item.get("score_edge"),
        "direction_hint": item.get("direction_hint"),
        "ret_5m_pct": item.get("ret_5m_pct"),
        "ret_15m_pct": item.get("ret_15m_pct"),
        "ret_1h_pct": item.get("ret_1h_pct"),
        "volume_ratio": item.get("volume_ratio"),
        "structure_status": ctx.get("structure_status"),
        "taker_bias": ctx.get("taker_bias"),
        "taker_buy_share": ctx.get("taker_buy_share"),
        "raw_oi_change_pct": ctx.get("raw_oi_change_pct"),
        "oi_interpretation": ctx.get("oi_interpretation"),
        "funding_rate": ctx.get("funding_rate"),
        "market_regime": ctx.get("market_regime"),
        "context_errors": ctx.get("context_errors") or [],
        "decision_reasons": item.get("decision_reasons") or [],
        "decision_context_confirmations": item.get("decision_context_confirmations"),
        "decision_context_conflicts": item.get("decision_context_conflicts"),
        "decision_context_balance": item.get("decision_context_balance"),
    }


def latest_summary(scan: dict[str, Any]) -> dict[str, Any]:
    prices = {
        str(item.get("symbol") or "").upper(): item.get("close")
        for item in scan.get("symbols", [])
        if isinstance(item, dict)
    }
    candidates = [
        compact_candidate(
            item,
            price=prices.get(str(item.get("symbol") or "").upper()),
        )
        for item in scan.get("moving_candidates", [])
        if isinstance(item, dict)
    ]
    return {
        "api_version": READ_API_VERSION,
        "scan_started_at_ms": scan.get("scan_started_at_ms"),
        "scan_finished_at_ms": scan.get("scan_finished_at_ms"),
        "candle_close_time_ms": scan.get("candle_close_time_ms"),
        "interval": scan.get("interval"),
        "universe_count": scan.get("universe_count"),
        "completed_count": scan.get("completed_count"),
        "failed_count": scan.get("failed_count"),
        "moving_candidate_count": scan.get("moving_candidate_count"),
        "ignition_count": scan.get("ignition_count"),
        "expansion_count": scan.get("expansion_count"),
        "exhaustion_count": scan.get("exhaustion_count"),
        "long_decision_count": scan.get("long_decision_count"),
        "short_decision_count": scan.get("short_decision_count"),
        "no_trade_decision_count": scan.get("no_trade_decision_count"),
        "candidates": candidates,
    }


def candidates_view(
    scan: dict[str, Any],
    *,
    decision: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    prices = {
        str(item.get("symbol") or "").upper(): item.get("close")
        for item in scan.get("symbols", [])
        if isinstance(item, dict)
    }
    rows = [
        compact_candidate(
            item,
            price=prices.get(str(item.get("symbol") or "").upper()),
        )
        for item in scan.get("moving_candidates", [])
        if isinstance(item, dict)
    ]

    if decision:
        wanted = decision.strip().upper().replace("_", " ")
        rows = [
            row
            for row in rows
            if str(row.get("decision") or "").upper() == wanted
        ]

    if stage:
        wanted_stage = stage.strip().upper()
        rows = [
            row
            for row in rows
            if str(row.get("stage") or "").upper() == wanted_stage
        ]

    return {
        "api_version": READ_API_VERSION,
        "candle_close_time_ms": scan.get("candle_close_time_ms"),
        "count": len(rows),
        "candidates": rows,
    }


def symbol_view(scan: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    wanted = symbol.strip().upper()
    for item in scan.get("moving_candidates", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("symbol") or "").upper() == wanted:
            return {
                "api_version": READ_API_VERSION,
                "candidate": compact_candidate(
                    item,
                    price=next(
                        (
                            snap.get("close")
                            for snap in scan.get("symbols", [])
                            if isinstance(snap, dict)
                            and str(snap.get("symbol") or "").upper() == wanted
                        ),
                        None,
                    ),
                ),
            }

    for item in scan.get("symbols", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("symbol") or "").upper() == wanted:
            return {
                "api_version": READ_API_VERSION,
                "candidate": None,
                "snapshot": {
                    "symbol": item.get("symbol"),
                    "candle_close_time_ms": item.get("candle_close_time_ms"),
                    "close": item.get("close"),
                    "quote_volume_5m": item.get("quote_volume_5m"),
                    "quote_volume_24h": item.get("quote_volume_24h"),
                    "price_change_pct_24h": item.get("price_change_pct_24h"),
                },
            }
    return None


def _rpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _rpc_error(
    request_id: Any,
    code: int,
    message: str,
    data: Any | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _tool_result(payload: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    payload,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            }
        ],
        "structuredContent": payload,
        "isError": is_error,
    }


def mcp_dispatch(
    request: Any,
    *,
    scan_path: str | os.PathLike[str],
) -> tuple[int, dict[str, Any] | None]:
    """Handle the minimal read-only MCP surface.

    The server intentionally implements the latest handshake-era MCP revision
    (2025-11-25). Modern MCP clients can negotiate/fallback to this revision.
    No session state is required because all tools read the latest immutable
    scan snapshot from disk.
    """
    if not isinstance(request, dict):
        return HTTPStatus.BAD_REQUEST, _rpc_error(
            None, -32600, "Invalid Request"
        )

    request_id = request.get("id")
    if request.get("jsonrpc") != "2.0":
        return HTTPStatus.BAD_REQUEST, _rpc_error(
            request_id, -32600, "Invalid Request"
        )

    method = request.get("method")
    params = request.get("params") or {}
    if not isinstance(params, dict):
        return HTTPStatus.BAD_REQUEST, _rpc_error(
            request_id, -32602, "Invalid params"
        )

    if method == "notifications/initialized":
        return HTTPStatus.ACCEPTED, None

    if method == "initialize":
        return HTTPStatus.OK, _rpc_result(
            request_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": MCP_SERVER_NAME,
                    "version": MCP_SERVER_VERSION,
                },
                "instructions": (
                    "Read-only live BabaBot Market Radar. "
                    "Market data, scores, context, and decisions are produced "
                    "deterministically by the radar before MCP exposure."
                ),
            },
        )

    if method == "ping":
        return HTTPStatus.OK, _rpc_result(request_id, {})

    if method == "tools/list":
        return HTTPStatus.OK, _rpc_result(
            request_id,
            {"tools": MCP_TOOLS},
        )

    if method != "tools/call":
        return HTTPStatus.OK, _rpc_error(
            request_id, -32601, "Method not found"
        )

    name = params.get("name")
    arguments = params.get("arguments") or {}
    if not isinstance(name, str) or not isinstance(arguments, dict):
        return HTTPStatus.OK, _rpc_error(
            request_id, -32602, "Invalid params"
        )

    try:
        scan = load_latest_scan(scan_path)
    except FileNotFoundError:
        return HTTPStatus.OK, _rpc_result(
            request_id,
            _tool_result(
                {"error": "scan_not_ready"},
                is_error=True,
            ),
        )
    except Exception as exc:
        return HTTPStatus.OK, _rpc_result(
            request_id,
            _tool_result(
                {"error": "scan_read_failed", "detail": str(exc)},
                is_error=True,
            ),
        )

    if name == "get_market_radar":
        if arguments:
            return HTTPStatus.OK, _rpc_result(
                request_id,
                _tool_result(
                    {"error": "get_market_radar takes no arguments"},
                    is_error=True,
                ),
            )
        return HTTPStatus.OK, _rpc_result(
            request_id,
            _tool_result(latest_summary(scan)),
        )

    if name == "get_moving_coins":
        decision = arguments.get("decision")
        stage = arguments.get("stage")
        allowed_decisions = {None, "LONG", "SHORT", "NO TRADE", "NO_TRADE"}
        allowed_stages = {None, "IGNITION", "EXPANSION", "EXHAUSTION"}
        if decision not in allowed_decisions or stage not in allowed_stages:
            return HTTPStatus.OK, _rpc_result(
                request_id,
                _tool_result(
                    {"error": "invalid decision or stage filter"},
                    is_error=True,
                ),
            )
        extra = set(arguments) - {"decision", "stage"}
        if extra:
            return HTTPStatus.OK, _rpc_result(
                request_id,
                _tool_result(
                    {"error": "unexpected arguments", "fields": sorted(extra)},
                    is_error=True,
                ),
            )
        return HTTPStatus.OK, _rpc_result(
            request_id,
            _tool_result(
                candidates_view(
                    scan,
                    decision=decision,
                    stage=stage,
                )
            ),
        )

    if name == "inspect_symbol":
        extra = set(arguments) - {"symbol"}
        symbol = arguments.get("symbol")
        if extra or not isinstance(symbol, str) or not symbol.strip():
            return HTTPStatus.OK, _rpc_result(
                request_id,
                _tool_result(
                    {"error": "symbol is required"},
                    is_error=True,
                ),
            )
        view = symbol_view(scan, symbol)
        if view is None:
            return HTTPStatus.OK, _rpc_result(
                request_id,
                _tool_result(
                    {
                        "error": "symbol_not_found",
                        "symbol": symbol.strip().upper(),
                    },
                    is_error=True,
                ),
            )
        return HTTPStatus.OK, _rpc_result(
            request_id,
            _tool_result(view),
        )

    return HTTPStatus.OK, _rpc_error(
        request_id,
        -32601,
        "Unknown tool",
        {"name": name},
    )


class RadarReadHandler(BaseHTTPRequestHandler):
    scan_path = "data/latest_scan.json"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        mcp: bool = False,
    ) -> None:
        body = json.dumps(
            payload,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        if mcp:
            self.send_header("MCP-Protocol-Version", MCP_PROTOCOL_VERSION)
        self.end_headers()
        self.wfile.write(body)

    def _empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler method
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type,MCP-Protocol-Version,X-Baba-Control-Token",
        )
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler method
        parsed = urlparse(self.path)

        if parsed.path == "/control/live-arm":
            if not control_token_configured():
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"error": "control_token_not_configured"},
                )
                return
            token = self.headers.get("X-Baba-Control-Token")
            if not valid_control_token(token):
                self._json(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": "invalid_control_token"},
                )
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 16_384:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_request_body"},
                )
                return
            try:
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise ValueError("body must be an object")
                armed = request.get("armed")
                if not isinstance(armed, bool):
                    raise ValueError("armed must be boolean")
                note = request.get("note")
                if armed:
                    guard = live_preflight(
                        client=None,
                        require_arm=False,
                        require_entry_mode=True,
                    )
                    if not guard["ok"]:
                        self._json(
                            HTTPStatus.CONFLICT,
                            {
                                "error": "live_preflight_failed",
                                "preflight": guard,
                            },
                        )
                        return
                state = set_live_armed(armed, note=note)
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_live_arm_request", "detail": str(exc)},
                )
                return
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "live_arm_update_failed", "detail": str(exc)},
                )
                return
            self._json(HTTPStatus.OK, state)
            return

        if parsed.path == "/control/state":
            if not control_token_configured():
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"error": "control_token_not_configured"},
                )
                return

            token = self.headers.get("X-Baba-Control-Token")
            if not valid_control_token(token):
                self._json(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": "invalid_control_token"},
                )
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 16_384:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_request_body"},
                )
                return

            try:
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict):
                    raise ValueError("body must be an object")
                mode = str(request.get("mode") or "")
                note = request.get("note")
                state = set_control_mode(mode, note=note)
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_control_mode", "detail": str(exc)},
                )
                return
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "control_update_failed", "detail": str(exc)},
                )
                return

            self._json(HTTPStatus.OK, state)
            return

        if parsed.path != "/mcp":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 1_000_000:
            self._json(
                HTTPStatus.BAD_REQUEST,
                _rpc_error(None, -32700, "Invalid request body"),
                mcp=True,
            )
            return

        try:
            request = json.loads(self.rfile.read(length))
        except Exception:
            self._json(
                HTTPStatus.BAD_REQUEST,
                _rpc_error(None, -32700, "Parse error"),
                mcp=True,
            )
            return

        status, payload = mcp_dispatch(
            request,
            scan_path=self.scan_path,
        )
        if payload is None:
            self._empty(status)
            return
        self._json(status, payload, mcp=True)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler method
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "service": "bababot-market-radar",
                    "api_version": READ_API_VERSION,
                    "mcp": "/mcp",
                    "mcp_protocol_version": MCP_PROTOCOL_VERSION,
                    "execution_handoff": "/execution/intents",
                    "execution_mode": "HANDOFF_ONLY",
                    "signal_history": "/history/signals",
                    "persistence_summary": "/history/summary",
                    "entry_approvals": "/approval/reviews",
                    "entry_approval_summary": "/approval/summary",
                    "model_reviews": "/approval/models",
                    "model_review_summary": "/approval/models/summary",
                    "open_positions": "/positions/open",
                    "position_evaluations": "/positions/evaluations",
                    "paper_summary": "/paper/summary",
                    "paper_orders": "/paper/orders",
                    "candles": "/market/klines",
                    "control_state": "/control/state",
                    "live_preflight": "/live/preflight",
                    "live_summary": "/live/summary",
                    "live_orders": "/live/orders",
                    "live_positions": "/live/positions",
                    "live_arm": "/control/live-arm",
                    "control_token_configured": control_token_configured(),
                },
            )
            return

        if parsed.path == "/mcp":
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        try:
            scan = load_latest_scan(self.scan_path)
        except FileNotFoundError:
            self._json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "scan_not_ready"},
            )
            return
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "scan_read_failed", "detail": str(exc)},
            )
            return

        if parsed.path == "/live/preflight":
            try:
                self._json(
                    HTTPStatus.OK,
                    live_preflight(
                        client=None,
                        require_arm=True,
                        require_entry_mode=True,
                    ),
                )
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "live_preflight_failed", "detail": str(exc)},
                )
            return

        if parsed.path == "/live/summary":
            try:
                self._json(HTTPStatus.OK, live_summary())
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "live_summary_failed", "detail": str(exc)},
                )
            return

        if parsed.path == "/live/orders":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["100"])[0])
                rows = list_live_orders(limit=limit)
                self._json(
                    HTTPStatus.OK,
                    {"count": len(rows), "orders": rows},
                )
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "live_orders_read_failed", "detail": str(exc)},
                )
            return

        if parsed.path == "/live/positions":
            try:
                rows = list_open_live_positions()
                self._json(
                    HTTPStatus.OK,
                    {"count": len(rows), "positions": rows},
                )
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "live_positions_read_failed", "detail": str(exc)},
                )
            return

        if parsed.path == "/control/state":
            try:
                state = get_control_state()
                state["control_token_configured"] = control_token_configured()
                self._json(HTTPStatus.OK, state)
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "control_state_read_failed", "detail": str(exc)},
                )
            return

        if parsed.path == "/market/klines":
            query = parse_qs(parsed.query)
            symbol = str(query.get("symbol", [""])[0] or "").strip().upper()
            interval = str(query.get("interval", ["5m"])[0] or "5m").strip()
            try:
                limit = int(query.get("limit", ["120"])[0])
            except ValueError:
                limit = 120

            allowed_intervals = {"1m", "5m", "15m", "1h", "4h"}
            if not symbol:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "symbol_required"},
                )
                return
            if interval not in allowed_intervals:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_interval"},
                )
                return
            limit = max(20, min(limit, 500))

            try:
                client = BinancePublicClient(timeout=8.0, retries=2)
                rows = client.klines(
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                )
                candles = [
                    {
                        "open_time_ms": int(row[0]),
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                        "close_time_ms": int(row[6]),
                        "quote_volume": float(row[7]),
                        "trades": int(row[8]),
                    }
                    for row in rows
                ]
                self._json(
                    HTTPStatus.OK,
                    {
                        "symbol": symbol,
                        "interval": interval,
                        "count": len(candles),
                        "candles": candles,
                    },
                )
            except Exception as exc:
                self._json(
                    HTTPStatus.BAD_GATEWAY,
                    {"error": "klines_fetch_failed", "detail": str(exc)},
                )
            return

        if parsed.path == "/radar/latest":
            self._json(HTTPStatus.OK, latest_summary(scan))
            return

        if parsed.path == "/execution/intents":
            try:
                handoff = load_execution_handoff(
                    default_execution_handoff_path(self.scan_path)
                )
            except FileNotFoundError:
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"error": "execution_handoff_not_ready"},
                )
                return
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "execution_handoff_read_failed",
                        "detail": str(exc),
                    },
                )
                return
            self._json(HTTPStatus.OK, handoff)
            return

        if parsed.path == "/history/summary":
            try:
                self._json(HTTPStatus.OK, persistence_summary())
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "persistence_summary_failed",
                        "detail": str(exc),
                    },
                )
            return

        if parsed.path == "/history/signals":
            query = parse_qs(parsed.query)
            try:
                raw_limit = query.get("limit", ["100"])[0]
                limit = int(raw_limit)
                symbol = query.get("symbol", [None])[0]
                side = query.get("side", [None])[0]
                rows = list_signals(
                    limit=limit,
                    symbol=symbol,
                    side=side,
                )
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_history_filter", "detail": str(exc)},
                )
                return
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "signal_history_read_failed",
                        "detail": str(exc),
                    },
                )
                return
            self._json(
                HTTPStatus.OK,
                {
                    "count": len(rows),
                    "signals": rows,
                },
            )
            return

        if parsed.path == "/approval/summary":
            try:
                self._json(HTTPStatus.OK, entry_approval_summary())
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "entry_approval_summary_failed",
                        "detail": str(exc),
                    },
                )
            return

        if parsed.path == "/approval/reviews":
            query = parse_qs(parsed.query)
            try:
                raw_limit = query.get("limit", ["100"])[0]
                limit = int(raw_limit)
                verdict = query.get("verdict", [None])[0]
                rows = list_entry_approvals(
                    limit=limit,
                    verdict=verdict,
                )
            except ValueError as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "invalid_approval_filter", "detail": str(exc)},
                )
                return
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "entry_approval_read_failed",
                        "detail": str(exc),
                    },
                )
                return
            self._json(
                HTTPStatus.OK,
                {
                    "count": len(rows),
                    "reviews": rows,
                },
            )
            return

        if parsed.path == "/approval/models/summary":
            try:
                self._json(HTTPStatus.OK, model_review_summary())
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "model_review_summary_failed",
                        "detail": str(exc),
                    },
                )
            return

        if parsed.path == "/approval/models":
            query = parse_qs(parsed.query)
            try:
                raw_limit = query.get("limit", ["100"])[0]
                limit = int(raw_limit)
                model = query.get("model", [None])[0]
                role = query.get("role", [None])[0]
                rows = list_model_reviews(
                    limit=limit,
                    model=model,
                    role=role,
                )
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "model_review_read_failed",
                        "detail": str(exc),
                    },
                )
                return
            self._json(
                HTTPStatus.OK,
                {
                    "count": len(rows),
                    "reviews": rows,
                },
            )
            return

        if parsed.path == "/positions/open":
            try:
                rows = list_open_positions()
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "open_positions_read_failed",
                        "detail": str(exc),
                    },
                )
                return
            self._json(
                HTTPStatus.OK,
                {
                    "count": len(rows),
                    "positions": rows,
                },
            )
            return

        if parsed.path == "/positions/evaluations":
            query = parse_qs(parsed.query)
            try:
                raw_limit = query.get("limit", ["100"])[0]
                limit = int(raw_limit)
                position_id = query.get("position_id", [None])[0]
                rows = list_position_evaluations(
                    position_id=position_id,
                    limit=limit,
                )
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "position_evaluations_read_failed",
                        "detail": str(exc),
                    },
                )
                return
            self._json(
                HTTPStatus.OK,
                {
                    "count": len(rows),
                    "evaluations": rows,
                },
            )
            return

        if parsed.path == "/paper/summary":
            try:
                self._json(HTTPStatus.OK, paper_summary())
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "paper_summary_failed",
                        "detail": str(exc),
                    },
                )
            return

        if parsed.path == "/paper/orders":
            query = parse_qs(parsed.query)
            try:
                raw_limit = query.get("limit", ["100"])[0]
                limit = int(raw_limit)
                rows = list_paper_orders(limit=limit)
            except Exception as exc:
                self._json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "paper_orders_read_failed",
                        "detail": str(exc),
                    },
                )
                return
            self._json(
                HTTPStatus.OK,
                {
                    "count": len(rows),
                    "orders": rows,
                },
            )
            return

        if parsed.path == "/radar/candidates":
            query = parse_qs(parsed.query)
            decision = query.get("decision", [None])[0]
            stage = query.get("stage", [None])[0]
            self._json(
                HTTPStatus.OK,
                candidates_view(
                    scan,
                    decision=decision,
                    stage=stage,
                ),
            )
            return

        prefix = "/radar/symbol/"
        if parsed.path.startswith(prefix):
            symbol = parsed.path[len(prefix) :].strip()
            if not symbol:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "symbol_required"},
                )
                return
            view = symbol_view(scan, symbol)
            if view is None:
                self._json(
                    HTTPStatus.NOT_FOUND,
                    {
                        "error": "symbol_not_found",
                        "symbol": symbol.upper(),
                    },
                )
                return
            self._json(HTTPStatus.OK, view)
            return

        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})


def serve_read_api(
    *,
    host: str = "0.0.0.0",
    port: int = 8080,
    scan_path: str = "data/latest_scan.json",
) -> None:
    handler = type(
        "ConfiguredRadarReadHandler",
        (RadarReadHandler,),
        {"scan_path": scan_path},
    )
    server = ThreadingHTTPServer((host, port), handler)
    server.serve_forever()
