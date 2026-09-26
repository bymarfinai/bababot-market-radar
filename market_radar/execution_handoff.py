from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .models import MarketScan


EXECUTION_HANDOFF_VERSION = "stage9-v1"
EXECUTION_MODE = "HANDOFF_ONLY"


def default_execution_handoff_path(
    scan_output_path: str | os.PathLike[str],
) -> Path:
    return Path(scan_output_path).with_name("execution_intents.json")


def load_execution_handoff(
    path: str | os.PathLike[str],
) -> dict[str, Any]:
    handoff_path = Path(path)
    if not handoff_path.exists():
        raise FileNotFoundError(f"execution handoff not available: {handoff_path}")
    with handoff_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("execution handoff must be a JSON object")
    return payload


def _intent_from_candidate(item: Any) -> dict[str, Any] | None:
    decision = getattr(item, "decision", None)
    if decision not in {"LONG", "SHORT"}:
        return None

    candle_close = int(getattr(item, "candle_close_time_ms", 0) or 0)
    symbol = str(getattr(item, "symbol", "") or "").upper()
    if not symbol or candle_close <= 0:
        return None

    ctx = getattr(item, "market_context", None)

    return {
        "handoff_version": EXECUTION_HANDOFF_VERSION,
        "execution_mode": EXECUTION_MODE,
        "intent_id": f"{symbol}:{candle_close}:{decision}",
        "symbol": symbol,
        "side": decision,
        "candle_close_time_ms": candle_close,
        "stage": getattr(item, "stage", None),
        "long_score": getattr(item, "long_score", None),
        "short_score": getattr(item, "short_score", None),
        "score_edge": getattr(item, "score_edge", None),
        "market_regime": getattr(ctx, "market_regime", None) if ctx else None,
        "structure_status": getattr(ctx, "structure_status", None) if ctx else None,
        "taker_bias": getattr(ctx, "taker_bias", None) if ctx else None,
        "raw_oi_change_pct": getattr(ctx, "raw_oi_change_pct", None) if ctx else None,
        "funding_rate": getattr(ctx, "funding_rate", None) if ctx else None,
        "decision_reasons": list(getattr(item, "decision_reasons", ()) or ()),
        "risk_confirmation": "PENDING",
        "execution_status": "BLOCKED",
        "executable": False,
        "entry_price": None,
        "quantity": None,
        "stop_loss": None,
        "take_profit": None,
    }


def build_execution_handoff(scan: MarketScan) -> dict[str, Any]:
    intents = []
    for candidate in scan.moving_candidates:
        intent = _intent_from_candidate(candidate)
        if intent is not None:
            intents.append(intent)

    return {
        "handoff_version": EXECUTION_HANDOFF_VERSION,
        "execution_mode": EXECUTION_MODE,
        "scan_finished_at_ms": scan.scan_finished_at_ms,
        "candle_close_time_ms": scan.candle_close_time_ms,
        "intent_count": len(intents),
        "intents": intents,
        "live_order_submission_enabled": False,
    }


def write_execution_handoff_atomic(
    scan: MarketScan,
    output_path: str | os.PathLike[str],
) -> Path:
    """Write the Stage 9 execution handoff without placing orders."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        build_execution_handoff(scan),
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return path
