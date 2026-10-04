from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from .profit_discriminator_v2 import evaluate_stage5_discriminator
from .profit_discriminator_stage7 import evaluate_stage7_ambiguous
from .profit_protection_v2 import (
    evaluate_pp_decision_v2,
    save_pp_decision_v2_observation,
)
from .regime_context import classify_regime
from .stage1_scanner import latest_closed_kline
from .stage_classifier import classify_movement_stage


POSITION_LIFECYCLE_VERSION = "stage12-v3.1-entry-boundary"
_processing_lock = threading.Lock()
_fast_loop_lock = threading.Lock()
_fast_loop_started = False
_v2_decay_lock = threading.Lock()
_v2_decay_samples: dict[str, tuple[int, float]] = {}

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


def _post_entry_closed_excursion(
    rows: list[list[Any]],
    *,
    opened_at_ms: int,
    now_ms: int,
    current_price: float,
) -> dict[str, Any]:
    """Return excursion bounds that cannot include pre-entry candle prices.

    Only fully closed candles whose open timestamp is at or after the position
    entry are eligible. A candle that straddles entry is intentionally excluded
    because its high/low cannot be split causally without tick-level history.
    Current price remains eligible immediately after entry.
    """
    current = float(current_price)
    eligible: list[list[Any]] = []
    for row in rows:
        if len(row) <= 6:
            continue
        try:
            open_ms = int(row[0])
            close_ms = int(row[6])
        except (TypeError, ValueError, IndexError):
            continue
        if close_ms >= int(now_ms):
            continue
        if open_ms < int(opened_at_ms):
            continue
        eligible.append(row)

    high = current
    low = current
    if eligible:
        high = max(current, *(float(row[2]) for row in eligible))
        low = min(current, *(float(row[3]) for row in eligible))

    return {
        "high": high,
        "low": low,
        "full_closed_bar_count": len(eligible),
        "first_full_bar_open_ms": int(eligible[0][0]) if eligible else None,
        "last_full_bar_close_ms": int(eligible[-1][6]) if eligible else None,
        "entry_boundary_clipped": True,
    }


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




_ACTION_RANK = {"HOLD": 0, "REDUCE": 1, "CLOSE": 2}


def _cfg_float(name: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(value, hi))


def _fast_guards_enabled() -> bool:
    return os.environ.get("STAGE12_V3_FAST_GUARD_ENABLED", "0").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _fast_poll_seconds() -> float:
    return _cfg_float("STAGE12_FAST_POLL_SECONDS", 15.0, 5.0, 60.0)


def _v2_fast_shadow_enabled() -> bool:
    return os.environ.get("PP_DECISION_V2_STAGE3_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _v2_fast_shadow_start_ms() -> int:
    try:
        return int(os.environ.get("PP_DECISION_V2_STAGE3_START_MS", "0") or 0)
    except (TypeError, ValueError):
        return 0


def _v2_fast_danger_score(snapshot: dict[str, Any]) -> int:
    momentum = int(float(snapshot.get("side_ret_3m_pct") or 0.0) <= -_fast_price_ret3_threshold_pct())
    structure = int(bool(snapshot.get("opposite_micro_structure")))
    flow = int(bool(snapshot.get("flow_opposite")))
    positioning = int(bool(snapshot.get("positioning_opposite")))
    return 2 * momentum + 2 * structure + flow + positioning


def _v2_shadow_evaluation(
    *,
    position_id: str,
    opened_at_ms: int,
    status: str,
    current_price: float,
    mfe_pct: float,
    current_pnl_pct: float,
    snapshot: dict[str, Any],
    evaluated_at_ms: int,
) -> dict[str, Any] | None:
    if not _v2_fast_shadow_enabled():
        return None
    if int(opened_at_ms) <= _v2_fast_shadow_start_ms():
        return None
    with _v2_decay_lock:
        previous = _v2_decay_samples.get(str(position_id))
        _v2_decay_samples[str(position_id)] = (int(evaluated_at_ms), float(current_pnl_pct))
    previous_pnl = previous[1] if previous is not None else None
    elapsed_seconds = (
        max(0.001, (int(evaluated_at_ms) - int(previous[0])) / 1000.0)
        if previous is not None
        else None
    )
    result = evaluate_pp_decision_v2(
        mfe_pct=float(mfe_pct),
        current_pnl_pct=float(current_pnl_pct),
        previous_pnl_pct=previous_pnl,
        elapsed_seconds=elapsed_seconds,
        danger_score=_v2_fast_danger_score(snapshot),
        status=str(status).upper(),
    )
    try:
        save_pp_decision_v2_observation(
            position_id=str(position_id),
            opened_at_ms=int(opened_at_ms),
            evaluated_at_ms=int(evaluated_at_ms),
            current_price=float(current_price),
            current_pnl_pct=float(current_pnl_pct),
            mfe_pct=float(mfe_pct),
            previous_pnl_pct=previous_pnl,
            position_status=str(status).upper(),
            result=result,
            snapshot=snapshot,
        )
    except Exception as exc:
        result["observation_logging_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    try:
        discriminator = evaluate_stage5_discriminator(
            position_id=str(position_id),
            opened_at_ms=int(opened_at_ms),
            evaluated_at_ms=int(evaluated_at_ms),
            mfe_pct=float(mfe_pct),
            current_pnl_pct=float(current_pnl_pct),
            v2_result=result,
        )
        if discriminator is not None:
            result["stage5_discriminator"] = discriminator
            try:
                stage7 = evaluate_stage7_ambiguous(
                    position_id=str(position_id),
                    opened_at_ms=int(opened_at_ms),
                    stage5_state=discriminator,
                )
                if stage7 is not None:
                    result["stage7_ambiguous_gate"] = stage7
            except Exception as exc:
                result["stage7_ambiguous_gate_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    except Exception as exc:
        result["stage5_discriminator_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    return result


def _early_window_minutes() -> float:
    return _cfg_float("STAGE12_EARLY_WINDOW_MINUTES", 30.0, 5.0, 120.0)


def _early_mfe_max_pct() -> float:
    return _cfg_float("STAGE12_EARLY_MFE_MAX_PCT", 0.35, 0.05, 2.0)


def _early_close_mae_pct() -> float:
    return -abs(_cfg_float("STAGE12_EARLY_CLOSE_MAE_PCT", 1.0, 0.25, 5.0))


def _early_close_pnl_pct() -> float:
    return -abs(_cfg_float("STAGE12_EARLY_CLOSE_PNL_PCT", 0.60, 0.10, 5.0))


def _early_reduce_pnl_pct() -> float:
    return -abs(_cfg_float("STAGE12_EARLY_REDUCE_PNL_PCT", 0.35, 0.05, 3.0))


def _early_min_contradictions() -> int:
    return int(_cfg_float("STAGE12_EARLY_MIN_CONTRADICTIONS", 2, 1, 3))


def _protect_arm_mfe_pct() -> float:
    return _cfg_float("STAGE12_PROTECT_ARM_MFE_PCT", 0.50, 0.10, 5.0)


def _protect_reduce_ratio() -> float:
    return _cfg_float("STAGE12_PROTECT_REDUCE_GIVEBACK_RATIO", 0.55, 0.20, 1.50)


def _protect_close_ratio() -> float:
    return _cfg_float("STAGE12_PROTECT_CLOSE_GIVEBACK_RATIO", 0.80, 0.30, 2.0)


def _fast_price_ret3_threshold_pct() -> float:
    return _cfg_float("STAGE12_FAST_RET3_THRESHOLD_PCT", 0.10, 0.01, 2.0)


def _fast_oi_floor_pct() -> float:
    return _cfg_float("STAGE12_FAST_OI_MIN_CHANGE_PCT", 0.05, 0.0, 5.0)


def _max_action(*actions: str) -> str:
    return max(actions, key=lambda item: _ACTION_RANK.get(str(item).upper(), 0)).upper()


def _should_persist_fast_evaluation(action: str, *, has_previous: bool) -> bool:
    """Persist actionable fast guards plus the first monitoring snapshot.

    Subsequent fast HOLDs remain ephemeral so they cannot mask an unexecuted
    5m REDUCE/CLOSE in the lifecycle-order reader.
    """
    return (not has_previous) or str(action).upper() in {"REDUCE", "CLOSE"}


def _early_invalidation_guard(
    *,
    age_minutes: float,
    status: str,
    mfe_pct: float,
    mae_pct: float,
    current_pnl_pct: float,
    contradiction_count: int,
) -> dict[str, Any]:
    """Detect a thesis that was wrong almost immediately after entry."""
    mfe = max(0.0, float(mfe_pct))
    mae = min(0.0, float(mae_pct))
    current = float(current_pnl_pct)
    contradictions = max(0, int(contradiction_count))
    reasons: list[str] = []

    if age_minutes > _early_window_minutes() or mfe > _early_mfe_max_pct():
        return {
            "action": "HOLD",
            "active": False,
            "reasons": [],
            "age_minutes": round(age_minutes, 3),
        }

    severe_mae = mae <= _early_close_mae_pct()
    strong_loss = current <= _early_close_pnl_pct()
    weak_loss = current <= _early_reduce_pnl_pct()
    enough_conflict = contradictions >= _early_min_contradictions()

    if severe_mae and current < 0 and (
        contradictions >= 2 or (mae <= -1.5 and contradictions >= 1)
    ):
        reasons.extend(["early_low_mfe", "early_severe_mae", "independent_fresh_contradictions"])
        action = "CLOSE"
    elif severe_mae and weak_loss and contradictions >= 1:
        reasons.extend(["early_low_mfe", "early_severe_mae", "single_fresh_contradiction"])
        action = "REDUCE"
    elif strong_loss and enough_conflict:
        reasons.extend(["early_low_mfe", "early_strong_loss", "multiple_fresh_contradictions"])
        action = "CLOSE"
    elif weak_loss and enough_conflict:
        reasons.extend(["early_low_mfe", "early_adverse_move", "multiple_fresh_contradictions"])
        action = "REDUCE"
    else:
        action = "HOLD"

    if str(status).upper() == "REDUCED" and action == "REDUCE":
        action = "CLOSE"
        reasons.append("already_reduced_escalate_close")

    return {
        "action": action,
        "active": action != "HOLD",
        "reasons": reasons,
        "age_minutes": round(age_minutes, 3),
        "mfe_pct": round(mfe, 6),
        "mae_pct": round(mae, 6),
        "current_pnl_pct": round(current, 6),
        "contradiction_count": contradictions,
    }


def _profit_protection_guard(
    *,
    status: str,
    mfe_pct: float,
    current_pnl_pct: float,
    contradiction_count: int,
) -> dict[str, Any]:
    """Protect a trade that was demonstrably right before it gives profit back."""
    mfe = max(0.0, float(mfe_pct))
    current = float(current_pnl_pct)
    contradictions = max(0, int(contradiction_count))
    giveback_abs = max(0.0, mfe - current)
    giveback_ratio = giveback_abs / mfe if mfe > 0 else 0.0
    reasons: list[str] = []

    if mfe < _protect_arm_mfe_pct():
        return {
            "action": "HOLD",
            "active": False,
            "reasons": [],
            "mfe_pct": round(mfe, 6),
            "giveback_ratio": round(giveback_ratio, 6),
        }

    if mfe >= 1.0 and giveback_ratio >= _protect_close_ratio():
        action = "CLOSE"
        reasons.extend(["profit_protection_armed", "major_mfe_giveback"])
    elif current <= 0.0 and giveback_ratio >= 1.0 and contradictions >= 1:
        action = "CLOSE"
        reasons.extend(["profit_protection_armed", "gave_back_all_profit", "fresh_contradiction"])
    elif mfe >= 1.0 and giveback_ratio >= _protect_reduce_ratio():
        action = "REDUCE"
        reasons.extend(["profit_protection_armed", "mfe_giveback_reduce"])
    elif mfe >= _protect_arm_mfe_pct() and giveback_ratio >= 0.75 and contradictions >= 1:
        action = "REDUCE"
        reasons.extend(["profit_protection_armed", "small_mfe_giveback", "fresh_contradiction"])
    else:
        action = "HOLD"

    if str(status).upper() == "REDUCED" and action == "REDUCE":
        action = "CLOSE"
        reasons.append("already_reduced_escalate_close")

    return {
        "action": action,
        "active": action != "HOLD",
        "reasons": reasons,
        "mfe_pct": round(mfe, 6),
        "current_pnl_pct": round(current, 6),
        "giveback_abs_pct": round(giveback_abs, 6),
        "giveback_ratio": round(giveback_ratio, 6),
        "contradiction_count": contradictions,
    }


def _lifecycle_guards(
    *,
    age_minutes: float,
    status: str,
    mfe_pct: float,
    mae_pct: float,
    current_pnl_pct: float,
    contradiction_count: int,
) -> dict[str, Any]:
    early = _early_invalidation_guard(
        age_minutes=age_minutes,
        status=status,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        current_pnl_pct=current_pnl_pct,
        contradiction_count=contradiction_count,
    )
    protection = _profit_protection_guard(
        status=status,
        mfe_pct=mfe_pct,
        current_pnl_pct=current_pnl_pct,
        contradiction_count=contradiction_count,
    )
    action = _max_action(early["action"], protection["action"])
    reasons: list[str] = []
    if early["action"] == action and early["active"]:
        reasons.extend(early["reasons"])
    if protection["action"] == action and protection["active"]:
        reasons.extend(protection["reasons"])
    return {
        "action": action,
        "reasons": list(dict.fromkeys(reasons)),
        "early_invalidation": early,
        "profit_protection": protection,
    }


def _fast_taker_share(row: list[Any]) -> float:
    try:
        total = max(0.0, float(row[7]))
        buy = min(total, max(0.0, float(row[10])))
    except (TypeError, ValueError, IndexError):
        return 0.5
    return buy / total if total > 0 else 0.5


def _fast_oi_change_pct(rows: list[dict[str, Any]], now_ms: int) -> float | None:
    valid: list[tuple[int, float]] = []
    for item in rows:
        try:
            ts = int(item.get("timestamp") or 0)
            value = float(item.get("sumOpenInterest"))
        except (TypeError, ValueError):
            continue
        if ts <= now_ms and value > 0:
            valid.append((ts, value))
    valid.sort()
    if len(valid) < 2:
        return None
    first = valid[-2][1]
    last = valid[-1][1]
    return 100.0 * (last / first - 1.0) if first > 0 else None


def _build_fast_snapshot(
    client: BinancePublicClient,
    position: dict[str, Any],
) -> dict[str, Any]:
    symbol = str(position["symbol"]).upper()
    now_ms = int(time.time() * 1000)
    rows = client.klines(symbol=symbol, interval="1m", limit=7)
    closed = [row for row in rows if len(row) > 10 and int(row[6]) < now_ms]
    if len(closed) < 4:
        raise RuntimeError("insufficient closed 1m bars for Stage 12 V3 fast guard")

    current_price = float(client.ticker_price(symbol))
    excursion = _post_entry_closed_excursion(
        rows,
        opened_at_ms=int(position.get("opened_at_ms") or now_ms),
        now_ms=now_ms,
        current_price=current_price,
    )
    try:
        oi_rows = client.open_interest_hist(symbol, period="5m", limit=3)
    except Exception:
        oi_rows = []

    latest = closed[-1]
    prev = closed[-2]
    base3 = closed[-4]
    latest_close = float(latest[4])
    prev_close = float(prev[4])
    base3_close = float(base3[4])
    if min(latest_close, prev_close, base3_close, current_price) <= 0:
        raise RuntimeError("invalid fast lifecycle price")

    side = str(position["side"]).upper()
    sign = 1.0 if side == "LONG" else -1.0
    ret1 = 100.0 * (latest_close / prev_close - 1.0)
    ret3 = 100.0 * (latest_close / base3_close - 1.0)
    side_ret1 = sign * ret1
    side_ret3 = sign * ret3
    taker_buy_share = _fast_taker_share(latest)

    prior3 = closed[-4:-1]
    prior_high = max(float(row[2]) for row in prior3)
    prior_low = min(float(row[3]) for row in prior3)
    if side == "LONG":
        opposite_structure = latest_close < prior_low
        flow_opposite = taker_buy_share <= 0.45
        flow_aligned = taker_buy_share >= 0.55
    else:
        opposite_structure = latest_close > prior_high
        flow_opposite = taker_buy_share >= 0.55
        flow_aligned = taker_buy_share <= 0.45

    price_opposite = (
        opposite_structure
        or side_ret3 <= -_fast_price_ret3_threshold_pct()
    )
    oi_change = _fast_oi_change_pct(oi_rows, now_ms)
    positioning_opposite = bool(
        oi_change is not None
        and abs(oi_change) >= _fast_oi_floor_pct()
        and side_ret3 <= -_fast_price_ret3_threshold_pct()
    )

    contradictions: list[str] = []
    if price_opposite:
        contradictions.append("fast_price_structure_against_position")
    if flow_opposite:
        contradictions.append("fast_taker_flow_against_position")
    if positioning_opposite:
        contradictions.append("fast_positioning_against_position")

    return {
        "evaluation_layer": "FAST_GUARD",
        "symbol": symbol,
        "now_ms": now_ms,
        "candle_close_time_ms": int(latest[6]),
        "current_price": current_price,
        "latest_1m_open": float(latest[1]),
        "latest_1m_high": float(latest[2]),
        "latest_1m_low": float(latest[3]),
        "latest_1m_close": latest_close,
        # Market-context rolling bounds may include pre-entry candles and are
        # intentionally kept separate from position-path excursion accounting.
        "rolling_1m_high": max(float(row[2]) for row in closed[-5:]),
        "rolling_1m_low": min(float(row[3]) for row in closed[-5:]),
        "position_excursion_high": float(excursion["high"]),
        "position_excursion_low": float(excursion["low"]),
        "position_excursion_full_closed_bar_count": int(excursion["full_closed_bar_count"]),
        "position_excursion_first_full_bar_open_ms": excursion["first_full_bar_open_ms"],
        "position_excursion_last_full_bar_close_ms": excursion["last_full_bar_close_ms"],
        "position_excursion_entry_boundary_clipped": True,
        "ret_1m_pct": ret1,
        "ret_3m_pct": ret3,
        "side_ret_1m_pct": side_ret1,
        "side_ret_3m_pct": side_ret3,
        "taker_buy_share_1m": taker_buy_share,
        "flow_aligned": flow_aligned,
        "flow_opposite": flow_opposite,
        "opposite_micro_structure": opposite_structure,
        "fresh_oi_change_pct": oi_change,
        "positioning_opposite": positioning_opposite,
        "contradictions": contradictions,
    }


def evaluate_fast_position(
    client: BinancePublicClient,
    position: dict[str, Any],
    *,
    persist: bool = True,
) -> dict[str, Any]:
    snapshot = _build_fast_snapshot(client, position)
    side = str(position["side"]).upper()
    entry = float(position["entry_price"])
    current = float(snapshot["current_price"])
    pnl = _side_return(side, entry, current)

    previous = latest_position_evaluation(str(position["position_id"]))
    prev_mfe = (
        float(previous["mfe_pct"])
        if previous and previous.get("mfe_pct") is not None
        else None
    )
    prev_mae = (
        float(previous["mae_pct"])
        if previous and previous.get("mae_pct") is not None
        else None
    )

    # Position excursion bounds are entry-clipped. Market-context rolling
    # highs/lows remain available in the snapshot but must never feed MFE/MAE
    # or hard-stop decisions because they can contain pre-entry prices.
    high = float(snapshot.get("position_excursion_high") or current)
    low = float(snapshot.get("position_excursion_low") or current)
    mfe, mae = _mfe_mae(
        side=side,
        entry=entry,
        high=high,
        low=low,
        previous_mfe=prev_mfe,
        previous_mae=prev_mae,
    )

    age_minutes = max(
        0.0,
        (int(snapshot["now_ms"]) - int(position.get("opened_at_ms") or snapshot["now_ms"]))
        / 60_000.0,
    )
    contradictions = list(snapshot["contradictions"])
    guards = _lifecycle_guards(
        age_minutes=age_minutes,
        status=str(position.get("status") or "OPEN"),
        mfe_pct=mfe,
        mae_pct=mae,
        current_pnl_pct=pnl,
        contradiction_count=len(contradictions),
    )

    hard_risk = False
    hard_reasons: list[str] = []
    stop = position.get("stop_loss")
    if stop is not None:
        stop_f = float(stop)
        if side == "LONG" and low <= stop_f:
            hard_risk = True
        elif side == "SHORT" and high >= stop_f:
            hard_risk = True
        if hard_risk:
            hard_reasons.append("hard_stop_crossed_fast_guard")

    action = "CLOSE" if hard_risk else str(guards["action"])
    previous_health = (
        float(previous["health_score"])
        if previous and previous.get("health_score") is not None
        else 100.0
    )
    evaluated_at = int(time.time() * 1000)
    v2_shadow = _v2_shadow_evaluation(
        position_id=str(position["position_id"]),
        opened_at_ms=int(position.get("opened_at_ms") or evaluated_at),
        status=str(position.get("status") or "OPEN"),
        current_price=current,
        mfe_pct=mfe,
        current_pnl_pct=pnl,
        snapshot=snapshot,
        evaluated_at_ms=evaluated_at,
    )
    bucket_ms = int(_fast_poll_seconds() * 1000)
    evaluation_id = (
        f"{position['position_id']}:FAST:"
        f"{evaluated_at // max(bucket_ms, 1)}"
    )
    result = {
        "evaluation_id": evaluation_id,
        "position_id": position["position_id"],
        "evaluated_at_ms": evaluated_at,
        "candle_close_time_ms": snapshot["candle_close_time_ms"],
        "current_price": current,
        "unrealized_pnl_pct": round(pnl, 6),
        "mfe_pct": mfe,
        "mae_pct": mae,
        "health_score": previous_health,
        "deterministic_action": action,
        "ai_action": None,
        "ai_confidence": None,
        "final_action": action,
        "hard_risk_triggered": hard_risk,
        "reasons_json": json.dumps(
            hard_reasons + guards["reasons"],
            separators=(",", ":"),
        ),
        "contradictions_json": json.dumps(contradictions, separators=(",", ":")),
        "snapshot_json": json.dumps(
            {
                **snapshot,
                "age_minutes": round(age_minutes, 3),
                "v3_guards": guards,
                "thesis_health_score": (
                    previous_health if previous is not None else None
                ),
                "monitoring_state": (
                    "INITIAL_FAST" if previous is None else "FAST_GUARD"
                ),
                "awaiting_thesis_health": previous is None,
                "pp_decision_v2_shadow": v2_shadow,
            },
            separators=(",", ":"),
            allow_nan=False,
        ),
        "ai_json": None,
        "lifecycle_version": POSITION_LIFECYCLE_VERSION,
    }

    # Persist the first fast snapshot so a newly opened position has immediate
    # current price/PnL/MFE/MAE visibility. Later HOLDs remain ephemeral, which
    # prevents them from masking a still-unexecuted 5m REDUCE/CLOSE.
    if persist and _should_persist_fast_evaluation(
        action,
        has_previous=previous is not None,
    ):
        save_position_evaluation(result)
    return result


def process_fast_guards(*, persist: bool = True) -> dict[str, Any]:
    if not _fast_guards_enabled() and persist:
        return {"status": "DISABLED", "processed": 0, "hold": 0, "reduce": 0, "close": 0}

    positions = list_open_positions()
    if not positions:
        return {"status": "IDLE", "processed": 0, "hold": 0, "reduce": 0, "close": 0}

    client = BinancePublicClient(timeout=5.0, retries=1)
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    workers = max(1, min(int(_cfg_float("STAGE12_FAST_WORKERS", 8, 1, 16)), len(positions)))

    def _one(position: dict[str, Any]) -> dict[str, Any]:
        return evaluate_fast_position(client, position, persist=persist)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(_one, position): position for position in positions}
        for future in as_completed(future_map):
            position = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append(
                    f"{position.get('position_id')}: {type(exc).__name__}: {str(exc)[:240]}"
                )

    counts = {"HOLD": 0, "REDUCE": 0, "CLOSE": 0}
    for item in results:
        counts[str(item["final_action"]).upper()] += 1
    return {
        "status": "COMPLETE",
        "processed": len(results),
        "hold": counts["HOLD"],
        "reduce": counts["REDUCE"],
        "close": counts["CLOSE"],
        "errors": errors,
        "results": results,
    }


def start_fast_lifecycle_loop() -> bool:
    global _fast_loop_started
    if not _fast_guards_enabled():
        return False

    with _fast_loop_lock:
        if _fast_loop_started:
            return False
        _fast_loop_started = True

    def _runner() -> None:
        while True:
            started = time.time()
            try:
                result = process_fast_guards(persist=True)
                meaningful = (
                    result.get("reduce", 0)
                    or result.get("close", 0)
                    or result.get("errors")
                )
                if meaningful:
                    print(
                        "Stage 12 V3 fast guard: "
                        f"processed={result.get('processed', 0)} "
                        f"hold={result.get('hold', 0)} "
                        f"reduce={result.get('reduce', 0)} "
                        f"close={result.get('close', 0)} "
                        f"errors={len(result.get('errors') or [])}",
                        flush=True,
                    )
            except Exception as exc:
                print(
                    "Stage 12 V3 fast guard error: "
                    f"{type(exc).__name__}: {str(exc)[:300]}",
                    flush=True,
                )
            elapsed = time.time() - started
            time.sleep(max(1.0, _fast_poll_seconds() - elapsed))

    threading.Thread(
        target=_runner,
        name="stage12-v3-fast-guard",
        daemon=True,
    ).start()
    return True


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

    opened_at_ms = int(position.get("opened_at_ms") or now_ms)
    latest_open_ms = int(latest[0])
    ticker_last = float(ticker.get("lastPrice") or latest[4])
    # If the latest closed 5m candle started before entry, its close is not a
    # valid position-path price. Use current ticker until a full post-entry 5m
    # candle exists; afterwards keep thesis PnL on the closed-candle cadence.
    position_price = (
        float(latest[4]) if latest_open_ms >= opened_at_ms else ticker_last
    )
    excursion = _post_entry_closed_excursion(
        rows,
        opened_at_ms=opened_at_ms,
        now_ms=now_ms,
        current_price=position_price,
    )

    return {
        "symbol": symbol,
        "candle_close_time_ms": int(latest[6]),
        "open": float(latest[1]),
        "high": float(latest[2]),
        "low": float(latest[3]),
        "close": float(latest[4]),
        "position_price": position_price,
        "position_excursion_high": float(excursion["high"]),
        "position_excursion_low": float(excursion["low"]),
        "position_excursion_full_closed_bar_count": int(excursion["full_closed_bar_count"]),
        "position_excursion_first_full_bar_open_ms": excursion["first_full_bar_open_ms"],
        "position_excursion_last_full_bar_close_ms": excursion["last_full_bar_close_ms"],
        "position_excursion_entry_boundary_clipped": True,
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
    price = float(snapshot.get("position_price") or snapshot["close"])
    pnl = _side_return(side, entry, price)

    previous = latest_position_evaluation(str(position["position_id"]))
    prev_mfe = float(previous["mfe_pct"]) if previous and previous.get("mfe_pct") is not None else None
    prev_mae = float(previous["mae_pct"]) if previous and previous.get("mae_pct") is not None else None
    excursion_high = float(snapshot.get("position_excursion_high") or price)
    excursion_low = float(snapshot.get("position_excursion_low") or price)
    mfe, mae = _mfe_mae(
        side=side,
        entry=entry,
        high=excursion_high,
        low=excursion_low,
        previous_mfe=prev_mfe,
        previous_mae=prev_mae,
    )

    hard_risk = False
    hard_reasons: list[str] = []
    stop = position.get("stop_loss")
    if stop is not None:
        stop = float(stop)
        if side == "LONG" and excursion_low <= stop:
            hard_risk = True
            hard_reasons.append("hard_stop_crossed")
        elif side == "SHORT" and excursion_high >= stop:
            hard_risk = True
            hard_reasons.append("hard_stop_crossed")

    age_minutes = max(
        0.0,
        (int(time.time() * 1000) - int(position.get("opened_at_ms") or 0))
        / 60_000.0,
    )
    if _fast_guards_enabled():
        # V3 keeps Thesis Health independent from path-memory guards.
        health = _health_from_snapshot(side, snapshot)
        guards = _lifecycle_guards(
            age_minutes=age_minutes,
            status=str(position.get("status") or "OPEN"),
            mfe_pct=mfe,
            mae_pct=mae,
            current_pnl_pct=pnl,
            contradiction_count=len(health["contradictions"]),
        )
        deterministic_action = _max_action(
            health["deterministic_action"],
            guards["action"],
        )
    else:
        # Validation/rollback mode: preserve Stage 12 V2 behavior exactly.
        health = _health_from_snapshot(
            side,
            snapshot,
            mfe_pct=mfe,
            mae_pct=mae,
            unrealized_pnl_pct=pnl,
        )
        guards = {
            "action": "HOLD",
            "reasons": [],
            "early_invalidation": {"action": "HOLD", "active": False, "reasons": []},
            "profit_protection": {"action": "HOLD", "active": False, "reasons": []},
            "disabled": True,
        }
        deterministic_action = health["deterministic_action"]

    ai_view: dict[str, Any] | None = None
    if not hard_risk and deterministic_action != "CLOSE":
        try:
            ai_view = _ai_position_view(
                position,
                snapshot,
                {
                    **health,
                    "deterministic_action": deterministic_action,
                    "v3_guards": guards,
                },
            )
        except Exception as exc:
            ai_view = {
                "action": None,
                "confidence": None,
                "reasons": ["ai_position_supervisor_unavailable"],
                "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            }

    final_action = _arbitrate(
        deterministic_action,
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
        "deterministic_action": deterministic_action,
        "ai_action": ai_view.get("action") if ai_view else None,
        "ai_confidence": ai_view.get("confidence") if ai_view else None,
        "final_action": final_action,
        "hard_risk_triggered": hard_risk,
        "reasons_json": json.dumps(
            hard_reasons + guards["reasons"] + (ai_view.get("reasons") if ai_view else []),
            separators=(",", ":"),
        ),
        "contradictions_json": json.dumps(
            health["contradictions"],
            separators=(",", ":"),
        ),
        "snapshot_json": json.dumps(
            {
                **snapshot,
                "evaluation_layer": "THESIS_5M",
                "base_health_score": health["base_health_score"],
                "position_memory": health["position_memory"],
                "health_components": health["components"],
                "age_minutes": round(age_minutes, 3),
                "v3_guards": guards,
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
