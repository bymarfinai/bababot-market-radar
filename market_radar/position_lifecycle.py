from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from typing import Any

from .ai_provider import active_model, call_model_review, primary_provider
from .binance import BinancePublicClient
from .direction_scorer import score_directions
from .market_context import _raw_oi_context, _structure_context, _taker_context
from .moving_detector import detect_movement
from .persistence import (
    latest_position_evaluation,
    list_open_positions,
    save_position_evaluation,
)
from .regime_context import classify_regime
from .stage1_scanner import latest_closed_kline
from .stage_classifier import classify_movement_stage


POSITION_LIFECYCLE_VERSION = "stage12-v2-adaptive-health"
_processing_lock = threading.Lock()

POSITION_SYSTEM_PROMPT = """You are BabaBot's AI Position Supervisor.

Review an already-open futures position. The deterministic Position Health
Engine is the primary controller.

Return JSON only using:
- APPROVE = HOLD the current position.
- WATCH = REDUCE exposure / protect the position.
- VETO = CLOSE the position.

Judge only the supplied position and current closed-candle context.
Never reverse the position. Never invent leverage, size, stop loss, or targets.
A hard-risk/deterministic CLOSE cannot be overridden by you.

Schema:
{"verdict":"APPROVE|WATCH|VETO","confidence":0.0,
 "reasons":["short factual reason"],"risk_flags":[]}
"""


def _side_return(side: str, entry: float, price: float) -> float:
    if entry <= 0:
        return 0.0
    raw = 100.0 * (price / entry - 1.0)
    return raw if side == "LONG" else -raw


def _mfe_mae(
    *,
    side: str,
    entry: float,
    high: float,
    low: float,
    previous_mfe: float | None,
    previous_mae: float | None,
) -> tuple[float, float]:
    if entry <= 0:
        return previous_mfe or 0.0, previous_mae or 0.0
    if side == "LONG":
        favorable = 100.0 * (high / entry - 1.0)
        adverse = 100.0 * (low / entry - 1.0)
    else:
        favorable = 100.0 * (entry - low) / entry if low > 0 else 0.0
        adverse = 100.0 * (entry - high) / entry if high > 0 else 0.0
    mfe = max(previous_mfe or 0.0, favorable)
    mae = min(previous_mae or 0.0, adverse)
    return round(mfe, 6), round(mae, 6)


def _position_memory_penalties(
    *,
    base_health_score: float,
    mfe_pct: float | None,
    mae_pct: float | None,
    unrealized_pnl_pct: float | None,
) -> dict[str, float]:
    """Add trade-path memory without replacing current market health.

    MAE matters only while the position is still below entry and market health
    is already weakening. Profit protection activates only after MFE >= 1%
    and a substantial giveback while base market health is below 70.
    """
    base_health = float(base_health_score)
    mfe = max(0.0, float(mfe_pct or 0.0))
    mae = min(0.0, float(mae_pct or 0.0))
    current = float(unrealized_pnl_pct or 0.0)

    mae_penalty = 0.0
    if current <= 0.0 and base_health < 60.0:
        if mae <= -1.5:
            mae_penalty = 15.0
        elif mae <= -1.0:
            mae_penalty = 8.0

    giveback_abs = max(0.0, mfe - current)
    giveback_ratio = giveback_abs / mfe if mfe > 0 else 0.0

    giveback_penalty = 0.0
    if mfe >= 1.0 and base_health < 70.0:
        if giveback_ratio >= 0.75:
            giveback_penalty = 20.0
        elif giveback_ratio >= 0.50:
            giveback_penalty = 10.0

    return {
        "mfe_pct": round(mfe, 6),
        "mae_pct": round(mae, 6),
        "unrealized_pnl_pct": round(current, 6),
        "giveback_abs_pct": round(giveback_abs, 6),
        "giveback_ratio": round(giveback_ratio, 6),
        "mae_penalty": mae_penalty,
        "giveback_penalty": giveback_penalty,
        "total_penalty": mae_penalty + giveback_penalty,
    }


def _health_from_snapshot(
    side: str,
    snapshot: dict[str, Any],
    *,
    mfe_pct: float | None = None,
    mae_pct: float | None = None,
    unrealized_pnl_pct: float | None = None,
) -> dict[str, Any]:
    sign = 1.0 if side == "LONG" else -1.0
    r5 = sign * float(snapshot.get("ret_5m_pct") or 0.0)
    r15 = sign * float(snapshot.get("ret_15m_pct") or 0.0)
    r1h = sign * float(snapshot.get("ret_1h_pct") or 0.0)

    momentum = (6 if r5 > 0 else 0) + (10 if r15 > 0 else 0) + (14 if r1h > 0 else 0)

    structure = str(snapshot.get("structure_status") or "")
    if side == "LONG":
        structure_points = {
            "BREAKOUT": 20, "FAILED_BREAKDOWN": 16,
            "NO_STRUCTURAL_BREAK": 12, "FAILED_BOTH_SIDES": 8,
            "FAILED_BREAKOUT": 4, "BREAKDOWN": 0,
        }.get(structure, 8)
        structure_conflict = structure == "BREAKDOWN"
    else:
        structure_points = {
            "BREAKDOWN": 20, "FAILED_BREAKOUT": 16,
            "NO_STRUCTURAL_BREAK": 12, "FAILED_BOTH_SIDES": 8,
            "FAILED_BREAKDOWN": 4, "BREAKOUT": 0,
        }.get(structure, 8)
        structure_conflict = structure == "BREAKOUT"

    taker = str(snapshot.get("taker_bias") or "BALANCED")
    aligned_taker = "BUY" if side == "LONG" else "SELL"
    opposite_taker = "SELL" if side == "LONG" else "BUY"
    taker_points = 15 if taker == aligned_taker else 9 if taker == "BALANCED" else 2

    oi = str(snapshot.get("oi_interpretation") or "UNRESOLVED")
    if side == "LONG":
        oi_points = {
            "FRESH_LONG_PARTICIPATION": 15,
            "SHORT_COVERING": 10,
            "UNRESOLVED": 8,
            "LONG_LIQUIDATION": 3,
            "FRESH_SHORT_PARTICIPATION": 0,
        }.get(oi, 8)
        oi_conflict = oi == "FRESH_SHORT_PARTICIPATION"
    else:
        oi_points = {
            "FRESH_SHORT_PARTICIPATION": 15,
            "LONG_LIQUIDATION": 10,
            "UNRESOLVED": 8,
            "SHORT_COVERING": 3,
            "FRESH_LONG_PARTICIPATION": 0,
        }.get(oi, 8)
        oi_conflict = oi == "FRESH_LONG_PARTICIPATION"

    regime = str(snapshot.get("market_regime") or "SIDEWAYS")
    aligned_regime = "BULL" if side == "LONG" else "BEAR"
    opposite_regime = "BEAR" if side == "LONG" else "BULL"
    regime_points = 10 if regime == aligned_regime else 6 if regime == "SIDEWAYS" else 1

    stage = str(snapshot.get("stage") or "")
    stage_points = {"EXPANSION": 10, "IGNITION": 8, "EXHAUSTION": 3}.get(stage, 5)

    base_health = float(
        momentum
        + structure_points
        + taker_points
        + oi_points
        + regime_points
        + stage_points
    )
    position_memory = _position_memory_penalties(
        base_health_score=base_health,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        unrealized_pnl_pct=unrealized_pnl_pct,
    )
    health = max(0.0, base_health - position_memory["total_penalty"])

    contradictions: list[str] = []
    if structure_conflict:
        contradictions.append("structure_against_position")
    if taker == opposite_taker:
        contradictions.append("taker_flow_against_position")
    if oi_conflict:
        contradictions.append("fresh_oi_against_position")
    if regime == opposite_regime:
        contradictions.append("regime_against_position")
    if r15 < 0 and r1h < 0:
        contradictions.append("15m_and_1h_momentum_against_position")

    long_score = float(snapshot.get("long_score") or 0.0)
    short_score = float(snapshot.get("short_score") or 0.0)
    opposing_score = short_score if side == "LONG" else long_score
    score_edge = abs(long_score - short_score)
    if opposing_score >= 68 and score_edge >= 10:
        contradictions.append("opposing_direction_score_strong")

    if health < 35 or (
        len(contradictions) >= 3 and health < 45
    ) or (
        "opposing_direction_score_strong" in contradictions
        and structure_conflict
        and taker == opposite_taker
    ):
        action = "CLOSE"
    elif health < 55 or len(contradictions) >= 2:
        action = "REDUCE"
    else:
        action = "HOLD"

    return {
        "health_score": round(health, 2),
        "base_health_score": round(base_health, 2),
        "deterministic_action": action,
        "contradictions": contradictions,
        "position_memory": position_memory,
        "components": {
            "momentum": momentum,
            "structure": structure_points,
            "taker": taker_points,
            "oi": oi_points,
            "regime": regime_points,
            "stage": stage_points,
            "mae_penalty": -position_memory["mae_penalty"],
            "giveback_penalty": -position_memory["giveback_penalty"],
        },
    }


def _build_snapshot(
    client: BinancePublicClient,
    position: dict[str, Any],
) -> dict[str, Any]:
    symbol = str(position["symbol"]).upper()
    now_ms = client.server_time_ms()
    tickers = client.ticker_24h()
    ticker = next(
        (item for item in tickers if item.get("symbol") == symbol),
        {},
    )
    rows = client.klines(symbol=symbol, interval="5m", limit=50)
    latest = latest_closed_kline(rows, now_ms)
    movement = detect_movement(
        symbol=symbol,
        klines=rows,
        now_ms=now_ms,
        ret_24h_pct=float(ticker.get("priceChangePercent") or 0.0),
    )
    movement = classify_movement_stage(movement)
    movement = score_directions(movement)

    structure = _structure_context([r for r in rows if int(r[6]) < now_ms])
    taker = _taker_context(latest)

    oi_hist = client.open_interest_hist(symbol, period="5m", limit=7)
    oi = _raw_oi_context(
        oi_hist,
        movement.candle_close_time_ms,
        movement,
    )
    premium = client.premium_index(symbol)
    regime = classify_regime(
        client.klines(symbol=symbol, interval="4h", limit=500),
        now_ms=now_ms,
    )

    return {
        "symbol": symbol,
        "candle_close_time_ms": int(latest[6]),
        "open": float(latest[1]),
        "high": float(latest[2]),
        "low": float(latest[3]),
        "close": float(latest[4]),
        "movement_state": movement.movement_state,
        "stage": movement.stage,
        "ret_5m_pct": movement.ret_5m_pct,
        "ret_15m_pct": movement.ret_15m_pct,
        "ret_1h_pct": movement.ret_1h_pct,
        "long_score": movement.long_score,
        "short_score": movement.short_score,
        "score_edge": movement.score_edge,
        "structure_status": structure["structure_status"],
        "taker_bias": taker["taker_bias"],
        "taker_buy_share": taker["taker_buy_share"],
        "raw_oi_change_pct": oi["raw_oi_change_pct"],
        "oi_interpretation": oi["oi_interpretation"],
        "funding_rate": float(premium.get("lastFundingRate") or 0.0),
        "market_regime": regime.regime,
    }


def _ai_position_view(
    position: dict[str, Any],
    snapshot: dict[str, Any],
    health: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "position": {
            "position_id": position["position_id"],
            "symbol": position["symbol"],
            "side": position["side"],
            "entry_price": position["entry_price"],
            "stop_loss": position.get("stop_loss"),
        },
        "current": snapshot,
        "deterministic_health": health,
    }
    review = call_model_review(
        payload,
        system_prompt=POSITION_SYSTEM_PROMPT,
        model=active_model(),
        provider=primary_provider(),
    )
    mapped = {
        "APPROVE": "HOLD",
        "WATCH": "REDUCE",
        "VETO": "CLOSE",
    }[review["verdict"]]
    return {
        "action": mapped,
        "confidence": review["confidence"],
        "reasons": review.get("reasons") or [],
        "model": review.get("model"),
        "provider": review.get("provider"),
    }


def _arbitrate(
    deterministic_action: str,
    ai_action: str | None,
    health_score: float,
    *,
    hard_risk: bool,
) -> str:
    if hard_risk or deterministic_action == "CLOSE":
        return "CLOSE"
    if ai_action is None:
        return deterministic_action
    if deterministic_action == "REDUCE":
        if ai_action == "CLOSE" and health_score < 45:
            return "CLOSE"
        return "REDUCE"
    if deterministic_action == "HOLD":
        if ai_action in {"REDUCE", "CLOSE"} and health_score < 65:
            return "REDUCE"
        return "HOLD"
    return deterministic_action


def evaluate_position(
    client: BinancePublicClient,
    position: dict[str, Any],
) -> dict[str, Any]:
    snapshot = _build_snapshot(client, position)
    side = str(position["side"]).upper()
    entry = float(position["entry_price"])
    price = float(snapshot["close"])
    pnl = _side_return(side, entry, price)

    previous = latest_position_evaluation(str(position["position_id"]))
    prev_mfe = float(previous["mfe_pct"]) if previous and previous.get("mfe_pct") is not None else None
    prev_mae = float(previous["mae_pct"]) if previous and previous.get("mae_pct") is not None else None
    mfe, mae = _mfe_mae(
        side=side,
        entry=entry,
        high=float(snapshot["high"]),
        low=float(snapshot["low"]),
        previous_mfe=prev_mfe,
        previous_mae=prev_mae,
    )

    hard_risk = False
    hard_reasons: list[str] = []
    stop = position.get("stop_loss")
    if stop is not None:
        stop = float(stop)
        if side == "LONG" and float(snapshot["low"]) <= stop:
            hard_risk = True
            hard_reasons.append("hard_stop_crossed")
        elif side == "SHORT" and float(snapshot["high"]) >= stop:
            hard_risk = True
            hard_reasons.append("hard_stop_crossed")

    health = _health_from_snapshot(
        side,
        snapshot,
        mfe_pct=mfe,
        mae_pct=mae,
        unrealized_pnl_pct=pnl,
    )
    ai_view: dict[str, Any] | None = None
    if not hard_risk:
        try:
            ai_view = _ai_position_view(position, snapshot, health)
        except Exception as exc:
            ai_view = {
                "action": None,
                "confidence": None,
                "reasons": ["ai_position_supervisor_unavailable"],
                "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            }

    final_action = _arbitrate(
        health["deterministic_action"],
        ai_view.get("action") if ai_view else None,
        health["health_score"],
        hard_risk=hard_risk,
    )

    evaluated_at = int(time.time() * 1000)
    result = {
        "evaluation_id": (
            f"{position['position_id']}:{snapshot['candle_close_time_ms']}"
        ),
        "position_id": position["position_id"],
        "evaluated_at_ms": evaluated_at,
        "candle_close_time_ms": snapshot["candle_close_time_ms"],
        "current_price": price,
        "unrealized_pnl_pct": round(pnl, 6),
        "mfe_pct": mfe,
        "mae_pct": mae,
        "health_score": health["health_score"],
        "deterministic_action": health["deterministic_action"],
        "ai_action": ai_view.get("action") if ai_view else None,
        "ai_confidence": ai_view.get("confidence") if ai_view else None,
        "final_action": final_action,
        "hard_risk_triggered": hard_risk,
        "reasons_json": json.dumps(
            hard_reasons + (ai_view.get("reasons") if ai_view else []),
            separators=(",", ":"),
        ),
        "contradictions_json": json.dumps(
            health["contradictions"],
            separators=(",", ":"),
        ),
        "snapshot_json": json.dumps(
            {
                **snapshot,
                "health_components": health["components"],
            },
            separators=(",", ":"),
            allow_nan=False,
        ),
        "ai_json": json.dumps(
            ai_view,
            separators=(",", ":"),
            allow_nan=False,
        ) if ai_view else None,
        "lifecycle_version": POSITION_LIFECYCLE_VERSION,
    }
    save_position_evaluation(result)
    return result


def process_open_positions() -> dict[str, Any]:
    if not _processing_lock.acquire(blocking=False):
        return {"status": "BUSY", "processed": 0}

    try:
        positions = list_open_positions()
        if not positions:
            return {
                "status": "IDLE",
                "processed": 0,
                "hold": 0,
                "reduce": 0,
                "close": 0,
            }

        client = BinancePublicClient(timeout=8.0, retries=2)
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        for position in positions:
            try:
                results.append(evaluate_position(client, position))
            except Exception as exc:
                errors.append(
                    f"{position.get('position_id')}: "
                    f"{type(exc).__name__}: {str(exc)[:240]}"
                )

        counts = {"HOLD": 0, "REDUCE": 0, "CLOSE": 0}
        for item in results:
            counts[item["final_action"]] += 1
        return {
            "status": "COMPLETE",
            "processed": len(results),
            "hold": counts["HOLD"],
            "reduce": counts["REDUCE"],
            "close": counts["CLOSE"],
            "errors": errors,
            "results": results,
        }
    finally:
        _processing_lock.release()


def start_position_lifecycle_worker() -> bool:
    if _processing_lock.locked():
        return False

    def _runner() -> None:
        result = process_open_positions()
        print(
            "Stage 12 lifecycle: "
            f"status={result.get('status')} "
            f"processed={result.get('processed', 0)} "
            f"hold={result.get('hold', 0)} "
            f"reduce={result.get('reduce', 0)} "
            f"close={result.get('close', 0)} "
            f"errors={len(result.get('errors') or [])}",
            flush=True,
        )

    threading.Thread(
        target=_runner,
        name="stage12-position-lifecycle",
        daemon=True,
    ).start()
    return True
