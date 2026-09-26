from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


READ_API_VERSION = "stage7-v1"


def load_latest_scan(path: str | os.PathLike[str]) -> dict[str, Any]:
    scan_path = Path(path)
    if not scan_path.exists():
        raise FileNotFoundError(f"scan not available: {scan_path}")
    with scan_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("latest scan must be a JSON object")
    return payload


def compact_candidate(item: dict[str, Any]) -> dict[str, Any]:
    """Return only fields AI/MCP needs for inspection.

    Full raw scan remains on disk. The read API deliberately avoids duplicating
    internal detector state that is not useful to an MCP caller.
    """
    ctx = item.get("market_context") or {}
    return {
        "symbol": item.get("symbol"),
        "candle_close_time_ms": item.get("candle_close_time_ms"),
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
    candidates = [
        compact_candidate(item)
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
    rows = [
        compact_candidate(item)
        for item in scan.get("moving_candidates", [])
        if isinstance(item, dict)
    ]

    if decision:
        wanted = decision.strip().upper().replace("_", " ")
        rows = [row for row in rows if str(row.get("decision") or "").upper() == wanted]

    if stage:
        wanted_stage = stage.strip().upper()
        rows = [row for row in rows if str(row.get("stage") or "").upper() == wanted_stage]

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
                "candidate": compact_candidate(item),
            }

    # Symbol may be in the full scan but not currently moving.
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


class RadarReadHandler(BaseHTTPRequestHandler):
    scan_path = "data/latest_scan.json"

    def log_message(self, _format: str, *_args: Any) -> None:
        # Keep scanner logs clean; Railway already records request status.
        return

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler method
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._json(
                HTTPStatus.OK,
                {"ok": True, "service": "bababot-market-radar", "api_version": READ_API_VERSION},
            )
            return

        try:
            scan = load_latest_scan(self.scan_path)
        except FileNotFoundError:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "scan_not_ready"})
            return
        except Exception as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "scan_read_failed", "detail": str(exc)},
            )
            return

        if parsed.path == "/radar/latest":
            self._json(HTTPStatus.OK, latest_summary(scan))
            return

        if parsed.path == "/radar/candidates":
            query = parse_qs(parsed.query)
            decision = query.get("decision", [None])[0]
            stage = query.get("stage", [None])[0]
            self._json(
                HTTPStatus.OK,
                candidates_view(scan, decision=decision, stage=stage),
            )
            return

        prefix = "/radar/symbol/"
        if parsed.path.startswith(prefix):
            symbol = parsed.path[len(prefix) :].strip()
            if not symbol:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "symbol_required"})
                return
            view = symbol_view(scan, symbol)
            if view is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "symbol_not_found", "symbol": symbol.upper()})
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
