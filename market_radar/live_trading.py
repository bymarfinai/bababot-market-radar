from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any

from .binance import BinanceTradingClient
from .control_state import get_control_state
from .live_store import (
    close_live_position,
    count_open_live_positions,
    create_live_order,
    create_live_position,
    get_live_position,
    has_open_live_symbol,
    initialize_live_store,
    list_live_entry_candidates,
    list_open_live_positions,
    list_pending_live_orders,
    list_unacted_live_lifecycle_actions,
    live_daily_pnl,
    live_recent_loss_streak,
    mark_live_order,
    paper_gate_stats,
    update_live_reduce,
)


LIVE_TRADING_VERSION = "stage15-v1"
_loop_lock = threading.Lock()
_loop_started = False


def live_env_enabled() -> bool:
    return os.environ.get("LIVE_TRADING_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def live_credentials_configured() -> bool:
    return bool(
        os.environ.get("BINANCE_API_KEY", "").strip()
        and os.environ.get("BINANCE_API_SECRET", "").strip()
    )


def _notional() -> float:
    return max(1.0, float(os.environ.get("LIVE_NOTIONAL_USDT", "25")))


def _max_notional() -> float:
    return max(1.0, float(os.environ.get("LIVE_MAX_NOTIONAL_USDT", "50")))


def _max_open() -> int:
    return max(1, min(int(os.environ.get("LIVE_MAX_OPEN_POSITIONS", "1")), 5))


def _leverage() -> int:
    return max(1, min(int(os.environ.get("LIVE_LEVERAGE", "1")), 3))


def _hard_stop_pct() -> float:
    return max(0.5, min(float(os.environ.get("LIVE_HARD_STOP_PCT", "1.5")), 5.0))


def _daily_loss_limit() -> float:
    return max(1.0, float(os.environ.get("LIVE_DAILY_LOSS_LIMIT_USDT", "10")))


def _max_loss_streak() -> int:
    return max(1, min(int(os.environ.get("LIVE_MAX_LOSS_STREAK", "3")), 10))


def _paper_min_closed() -> int:
    return max(0, int(os.environ.get("LIVE_MIN_PAPER_CLOSED_TRADES", "20")))


def _paper_net_nonnegative_required() -> bool:
    return os.environ.get(
        "LIVE_REQUIRE_PAPER_NET_PNL_NONNEGATIVE",
        "true",
    ).strip().lower() in {"1", "true", "yes", "on"}


def _entry_age_ms() -> int:
    minutes = max(1.0, float(os.environ.get("LIVE_ENTRY_MAX_AGE_MINUTES", "10")))
    return int(minutes * 60_000)


def _reduce_fraction() -> float:
    return max(0.10, min(float(os.environ.get("LIVE_REDUCE_FRACTION", "0.50")), 0.90))


def _max_spread_bps() -> float:
    return max(1.0, min(float(os.environ.get("LIVE_MAX_SPREAD_BPS", "20")), 100.0))


def _balance_buffer() -> float:
    return max(1.05, min(float(os.environ.get("LIVE_BALANCE_BUFFER_MULTIPLIER", "1.25")), 3.0))


def _poll_seconds() -> float:
    return max(5.0, min(float(os.environ.get("LIVE_POLL_SECONDS", "10")), 60.0))


def _stop_client_id(position_id: str) -> str:
    digest = hashlib.sha256(position_id.encode("utf-8")).hexdigest()[:23]
    return f"BBS{digest}"[:32]


def _emergency_client_id(position_id: str) -> str:
    digest = hashlib.sha256((position_id + ":EMERGENCY").encode("utf-8")).hexdigest()[:23]
    return f"BBE{digest}"[:32]


def _spread_bps(client: BinanceTradingClient, symbol: str) -> float:
    depth = client.depth(symbol, limit=5)
    bids = depth.get("bids") or []
    asks = depth.get("asks") or []
    if not bids or not asks:
        raise RuntimeError("order book unavailable")
    bid = float(bids[0][0])
    ask = float(asks[0][0])
    mid = (bid + ask) / 2.0
    if mid <= 0:
        raise RuntimeError("invalid order book mid")
    return 10_000.0 * (ask - bid) / mid


def _paper_gate() -> tuple[bool, list[str], dict[str, Any]]:
    stats = paper_gate_stats()
    reasons: list[str] = []
    if stats["closed"] < _paper_min_closed():
        reasons.append(
            f"paper_closed_trades_below_min:{stats['closed']}<{_paper_min_closed()}"
        )
    if _paper_net_nonnegative_required() and stats["net_pnl"] < 0:
        reasons.append(f"paper_net_pnl_negative:{stats['net_pnl']:.4f}")
    return not reasons, reasons, stats


def preflight(
    *,
    client: BinanceTradingClient | None = None,
    require_arm: bool = True,
    require_entry_mode: bool = True,
) -> dict[str, Any]:
    reasons: list[str] = []
    state = get_control_state()

    if not live_env_enabled():
        reasons.append("live_env_disabled")
    if not live_credentials_configured():
        reasons.append("live_credentials_missing")
    if require_arm and not state.get("live_armed"):
        reasons.append("live_not_armed")
    if require_entry_mode and state.get("mode") != "RUN":
        reasons.append(f"control_mode_{state.get('mode')}")
    if _notional() > _max_notional():
        reasons.append("live_notional_above_cap")
    if _leverage() > 3:
        reasons.append("leverage_above_stage15_cap")

    paper_ok, paper_reasons, paper_stats = _paper_gate()
    if not paper_ok:
        reasons.extend(paper_reasons)

    daily_pnl = live_daily_pnl()
    loss_streak = live_recent_loss_streak()
    if daily_pnl <= -_daily_loss_limit():
        reasons.append(
            f"daily_loss_limit_reached:{daily_pnl:.4f}"
        )
    if loss_streak >= _max_loss_streak():
        reasons.append(
            f"loss_streak_limit_reached:{loss_streak}"
        )
    if count_open_live_positions() >= _max_open() and require_entry_mode:
        reasons.append("max_open_live_positions")

    account_info: dict[str, Any] | None = None
    available_usdt: float | None = None
    dual_side: bool | None = None
    unmanaged: list[str] = []

    if client is not None and live_credentials_configured():
        try:
            account_info = client.account()
            if not bool(account_info.get("canTrade", False)):
                reasons.append("binance_account_cannot_trade")
        except Exception as exc:
            reasons.append(f"account_check_failed:{type(exc).__name__}")

        try:
            mode = client.position_mode()
            dual_side = bool(mode.get("dualSidePosition"))
            if dual_side:
                reasons.append("hedge_mode_not_supported")
        except Exception as exc:
            reasons.append(f"position_mode_check_failed:{type(exc).__name__}")

        try:
            available_usdt = client.available_usdt()
            required = _notional() * _balance_buffer() / max(1, _leverage())
            if available_usdt < required:
                reasons.append(
                    f"insufficient_available_usdt:{available_usdt:.2f}<{required:.2f}"
                )
        except Exception as exc:
            reasons.append(f"balance_check_failed:{type(exc).__name__}")

        try:
            managed = {
                str(item["symbol"]).upper()
                for item in list_open_live_positions()
            }
            for position in client.nonzero_positions():
                symbol = str(position.get("symbol") or "").upper()
                if symbol and symbol not in managed:
                    unmanaged.append(symbol)
            if unmanaged:
                reasons.append(
                    "unmanaged_binance_positions:" + ",".join(sorted(set(unmanaged)))
                )
        except Exception as exc:
            reasons.append(f"position_reconcile_check_failed:{type(exc).__name__}")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "live_version": LIVE_TRADING_VERSION,
        "control": state,
        "paper_gate": paper_stats,
        "daily_pnl": daily_pnl,
        "loss_streak": loss_streak,
        "notional_usdt": _notional(),
        "max_notional_usdt": _max_notional(),
        "max_open_positions": _max_open(),
        "leverage": _leverage(),
        "hard_stop_pct": _hard_stop_pct(),
        "available_usdt": available_usdt,
        "dual_side_position": dual_side,
        "unmanaged_positions": unmanaged,
    }


def _trade_stats(
    client: BinanceTradingClient,
    *,
    symbol: str,
    order: dict[str, Any],
) -> dict[str, float]:
    order_id = order.get("orderId")
    trades = client.user_trades(
        symbol=symbol,
        order_id=order_id,
        limit=100,
    ) if order_id is not None else []

    executed = float(order.get("executedQty") or 0.0)
    avg = float(order.get("avgPrice") or 0.0)
    commission = 0.0
    realized = 0.0
    weighted = 0.0
    qty_sum = 0.0
    for trade in trades:
        qty = float(trade.get("qty") or 0.0)
        price = float(trade.get("price") or 0.0)
        qty_sum += qty
        weighted += qty * price
        if trade.get("commissionAsset") == "USDT":
            commission += float(trade.get("commission") or 0.0)
        realized += float(trade.get("realizedPnl") or 0.0)

    if qty_sum > 0:
        executed = qty_sum
        avg = weighted / qty_sum
    return {
        "executed_quantity": executed,
        "avg_price": avg,
        "commission": commission,
        "realized_pnl": realized,
    }


def _submit_market(
    client: BinanceTradingClient,
    *,
    order: dict[str, Any],
    exchange_side: str,
    quantity: str,
    reduce_only: bool,
) -> tuple[dict[str, Any], dict[str, float]]:
    order_id = str(order["order_id"])
    client_order_id = str(order["client_order_id"])
    symbol = str(order["symbol"])
    mark_live_order(
        order_id,
        status="SUBMITTING",
        submitted_at_ms=int(time.time() * 1000),
    )

    try:
        result = client.new_market_order(
            symbol=symbol,
            side=exchange_side,
            quantity=quantity,
            client_order_id=client_order_id,
            reduce_only=reduce_only,
        )
    except Exception as submit_exc:
        try:
            result = client.query_order(
                symbol=symbol,
                client_order_id=client_order_id,
            )
        except Exception:
            mark_live_order(
                order_id,
                status="ERROR",
                error_text=f"{type(submit_exc).__name__}: {str(submit_exc)[:300]}",
            )
            raise

    if str(result.get("status") or "").upper() != "FILLED":
        for _ in range(4):
            time.sleep(0.35)
            result = client.query_order(
                symbol=symbol,
                client_order_id=client_order_id,
            )
            if str(result.get("status") or "").upper() == "FILLED":
                break
    if str(result.get("status") or "").upper() != "FILLED":
        raise RuntimeError(
            f"market order not FILLED: {result.get('status')}"
        )

    stats = _trade_stats(client, symbol=symbol, order=result)
    return result, stats


def sync_live_entry_orders() -> dict[str, Any]:
    if not live_env_enabled() or not live_credentials_configured():
        return {"queued": 0, "blocked": True, "reasons": ["live_locked"]}

    client = BinanceTradingClient()
    guard = preflight(client=client, require_arm=True, require_entry_mode=True)
    if not guard["ok"]:
        return {"queued": 0, "blocked": True, "reasons": guard["reasons"]}

    queued = 0
    for candidate in list_live_entry_candidates(
        max_age_ms=_entry_age_ms(),
        limit=10,
    ):
        if count_open_live_positions() >= _max_open():
            break
        symbol = str(candidate["symbol"]).upper()
        if has_open_live_symbol(symbol):
            continue
        create_live_order(
            source_type="ENTRY",
            source_id=str(candidate["signal_id"]),
            position_id=f"LIVE:{candidate['signal_id']}",
            signal_id=str(candidate["signal_id"]),
            symbol=symbol,
            side=str(candidate["side"]),
            action="OPEN",
            requested_quantity=None,
            reason="stage11_final_approve",
            payload={
                "approval_reviewed_at_ms": candidate["reviewed_at_ms"],
                "signal_time_ms": candidate["signal_time_ms"],
                "signal_price": candidate["signal_price"],
                "stage": candidate["stage"],
                "long_score": candidate["long_score"],
                "short_score": candidate["short_score"],
                "score_edge": candidate["score_edge"],
            },
        )
        queued += 1
        if queued >= _max_open():
            break
    return {"queued": queued, "blocked": False, "reasons": []}


def sync_live_lifecycle_orders() -> dict[str, int]:
    if not live_env_enabled() or not live_credentials_configured():
        return {"queued": 0}

    queued = 0
    for item in list_unacted_live_lifecycle_actions(limit=50):
        position = get_live_position(str(item["position_id"]))
        if not position:
            continue
        action = str(item["final_action"]).upper()
        if action == "REDUCE" and position.get("status") == "REDUCED":
            continue
        create_live_order(
            source_type="LIFECYCLE",
            source_id=str(item["evaluation_id"]),
            position_id=str(item["position_id"]),
            signal_id=str(position.get("signal_id") or ""),
            symbol=str(position["symbol"]),
            side=str(position["side"]),
            action=action,
            requested_quantity=None,
            reason=(
                "stage12_hard_risk"
                if item.get("hard_risk_triggered")
                else f"stage12_{action.lower()}"
            ),
            payload={
                "health_score": item["health_score"],
                "deterministic_action": item["deterministic_action"],
                "ai_action": item.get("ai_action"),
                "final_action": action,
                "candle_close_time_ms": item["candle_close_time_ms"],
            },
        )
        queued += 1
    return {"queued": queued}


def _execute_open(
    client: BinanceTradingClient,
    order: dict[str, Any],
) -> dict[str, Any]:
    payload = json.loads(order.get("payload_json") or "{}")
    approval_ms = int(payload.get("approval_reviewed_at_ms") or 0)
    if approval_ms <= 0 or int(time.time() * 1000) - approval_ms > _entry_age_ms():
        mark_live_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="approval_stale_before_live_fill",
        )
        return {"status": "SKIPPED", "reason": "stale_approval"}

    guard = preflight(client=client, require_arm=True, require_entry_mode=True)
    if not guard["ok"]:
        mark_live_order(
            str(order["order_id"]),
            status="BLOCKED",
            reason=";".join(guard["reasons"])[:1000],
        )
        return {"status": "BLOCKED", "reasons": guard["reasons"]}

    symbol = str(order["symbol"]).upper()
    if has_open_live_symbol(symbol):
        mark_live_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="live_symbol_already_open",
        )
        return {"status": "SKIPPED", "reason": "symbol_already_open"}

    exchange_existing = [
        item for item in client.position_risk(symbol)
        if abs(float(item.get("positionAmt") or 0.0)) > 0
    ]
    if exchange_existing:
        mark_live_order(
            str(order["order_id"]),
            status="BLOCKED",
            reason="exchange_symbol_position_already_open",
        )
        return {"status": "BLOCKED", "reason": "exchange_position_exists"}

    spread = _spread_bps(client, symbol)
    if spread > _max_spread_bps():
        mark_live_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason=f"spread_too_wide:{spread:.2f}bps",
        )
        return {"status": "SKIPPED", "reason": "spread_too_wide"}

    reference = client.ticker_price(symbol)
    quantity = client.market_quantity(
        symbol=symbol,
        notional_usdt=_notional(),
        reference_price=reference,
    )
    client.set_margin_type(symbol, "ISOLATED")
    client.set_leverage(symbol, _leverage())

    side = str(order["side"]).upper()
    exchange_side = "BUY" if side == "LONG" else "SELL"
    result, stats = _submit_market(
        client,
        order=order,
        exchange_side=exchange_side,
        quantity=quantity,
        reduce_only=False,
    )
    fill = float(stats["avg_price"])
    executed = float(stats["executed_quantity"])
    if fill <= 0 or executed <= 0:
        raise RuntimeError("live market fill returned zero price/quantity")

    stop_pct = _hard_stop_pct() / 100.0
    raw_stop = fill * (1.0 - stop_pct if side == "LONG" else 1.0 + stop_pct)
    stop_price_text = client.price_to_tick(
        symbol=symbol,
        price=raw_stop,
        round_up=side == "SHORT",
    )
    stop_price = float(stop_price_text)
    stop_client_id = _stop_client_id(str(order["position_id"]))

    metadata = {
        "live_trading_version": LIVE_TRADING_VERSION,
        "binance_entry_order_id": str(result.get("orderId") or ""),
        "entry_client_order_id": str(order["client_order_id"]),
        "entry_commission_usdt": float(stats["commission"]),
        "initial_quantity": executed,
        "initial_notional_usdt": executed * fill,
        "leverage": _leverage(),
        "margin_type": "ISOLATED",
        "protective_stop_pct": _hard_stop_pct(),
        "protective_stop_price": stop_price,
        "protective_stop_client_id": stop_client_id,
        "realized_net": -float(stats["commission"]),
        "exit_commission_usdt": 0.0,
        "exchange_realized_pnl": 0.0,
    }

    try:
        stop_result = client.new_stop_close_algo(
            symbol=symbol,
            side="SELL" if side == "LONG" else "BUY",
            trigger_price=stop_price_text,
            client_algo_id=stop_client_id,
        )
        metadata["protective_stop_algo_id"] = str(
            stop_result.get("algoId") or ""
        )
        metadata["protection_status"] = "ACTIVE"
    except Exception as stop_exc:
        # Do not leave a newly opened live position unprotected.
        emergency_id = _emergency_client_id(str(order["position_id"]))
        emergency = {
            **order,
            "order_id": str(order["order_id"]) + ":EMERGENCY",
            "client_order_id": emergency_id,
        }
        try:
            close_result, close_stats = _submit_market(
                client,
                order=emergency,
                exchange_side="SELL" if side == "LONG" else "BUY",
                quantity=client.market_quantity(
                    symbol=symbol,
                    notional_usdt=executed * fill,
                    reference_price=fill,
                ),
                reduce_only=True,
            )
            metadata["protection_status"] = "FAILED_EMERGENCY_CLOSED"
            metadata["protective_stop_error"] = str(stop_exc)[:300]
            create_live_position(
                position_id=str(order["position_id"]),
                signal_id=str(order["signal_id"]),
                symbol=symbol,
                side=side,
                opened_at_ms=int(result.get("updateTime") or time.time() * 1000),
                entry_price=fill,
                quantity=executed,
                stop_loss=stop_price,
                metadata=metadata,
            )
            net = (
                float(close_stats["realized_pnl"])
                - float(stats["commission"])
                - float(close_stats["commission"])
            )
            close_live_position(
                position_id=str(order["position_id"]),
                event_time_ms=int(time.time() * 1000),
                exit_price=float(close_stats["avg_price"]),
                realized_pnl=net,
                realized_pnl_pct=100.0 * net / max(executed * fill, 1e-9),
                close_reason="protective_stop_failed_emergency_close",
                metadata=metadata,
            )
            mark_live_order(
                str(order["order_id"]),
                status="FILLED_EMERGENCY_CLOSED",
                filled_at_ms=int(time.time() * 1000),
                executed_quantity=executed,
                reference_price=reference,
                avg_price=fill,
                commission=float(stats["commission"]),
                binance_order_id=str(result.get("orderId") or ""),
                error_text=f"protective_stop_failed:{str(stop_exc)[:240]}",
            )
            return {
                "status": "EMERGENCY_CLOSED",
                "symbol": symbol,
                "reason": "protective_stop_failed",
            }
        except Exception as close_exc:
            mark_live_order(
                str(order["order_id"]),
                status="CRITICAL_UNPROTECTED",
                filled_at_ms=int(time.time() * 1000),
                executed_quantity=executed,
                reference_price=reference,
                avg_price=fill,
                commission=float(stats["commission"]),
                binance_order_id=str(result.get("orderId") or ""),
                error_text=(
                    f"stop={str(stop_exc)[:180]} "
                    f"emergency_close={str(close_exc)[:180]}"
                ),
            )
            raise RuntimeError(
                "CRITICAL: live position opened but protection and emergency close failed"
            )

    create_live_position(
        position_id=str(order["position_id"]),
        signal_id=str(order["signal_id"]),
        symbol=symbol,
        side=side,
        opened_at_ms=int(result.get("updateTime") or time.time() * 1000),
        entry_price=fill,
        quantity=executed,
        stop_loss=stop_price,
        metadata=metadata,
    )
    mark_live_order(
        str(order["order_id"]),
        status="FILLED",
        filled_at_ms=int(time.time() * 1000),
        executed_quantity=executed,
        reference_price=reference,
        avg_price=fill,
        commission=float(stats["commission"]),
        realized_pnl=float(stats["realized_pnl"]),
        binance_order_id=str(result.get("orderId") or ""),
        reason="guarded_live_market_entry",
    )
    return {
        "status": "FILLED",
        "action": "OPEN",
        "symbol": symbol,
        "avg_price": fill,
        "quantity": executed,
        "stop_loss": stop_price,
        "spread_bps": spread,
    }


def _execute_exit(
    client: BinanceTradingClient,
    order: dict[str, Any],
) -> dict[str, Any]:
    position = get_live_position(str(order["position_id"]))
    if not position or position.get("status") not in {"OPEN", "REDUCED"}:
        mark_live_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="live_position_not_open",
        )
        return {"status": "SKIPPED", "reason": "position_not_open"}

    rows = client.position_risk(str(position["symbol"]))
    active = next(
        (
            item for item in rows
            if abs(float(item.get("positionAmt") or 0.0)) > 0
        ),
        None,
    )
    if active is None:
        mark_live_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="exchange_position_already_flat",
        )
        return {"status": "SKIPPED", "reason": "exchange_already_flat"}

    exchange_qty = abs(float(active.get("positionAmt") or 0.0))
    action = str(order["action"]).upper()
    if action == "REDUCE" and position.get("status") == "REDUCED":
        mark_live_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="already_reduced_once",
        )
        return {"status": "SKIPPED", "reason": "already_reduced"}

    qty = exchange_qty * (_reduce_fraction() if action == "REDUCE" else 1.0)
    reference = client.ticker_price(str(position["symbol"]))
    qty_text = client.market_quantity(
        symbol=str(position["symbol"]),
        notional_usdt=max(qty * reference, 1.0),
        reference_price=reference,
    )
    exchange_side = "SELL" if position["side"] == "LONG" else "BUY"
    result, stats = _submit_market(
        client,
        order=order,
        exchange_side=exchange_side,
        quantity=qty_text,
        reduce_only=True,
    )

    metadata = json.loads(position.get("raw_json") or "{}")
    realized_before = float(metadata.get("exchange_realized_pnl") or 0.0)
    commission_before = (
        float(metadata.get("entry_commission_usdt") or 0.0)
        + float(metadata.get("exit_commission_usdt") or 0.0)
    )
    realized_total = realized_before + float(stats["realized_pnl"])
    exit_commission = (
        float(metadata.get("exit_commission_usdt") or 0.0)
        + float(stats["commission"])
    )
    total_commission = (
        float(metadata.get("entry_commission_usdt") or 0.0)
        + exit_commission
    )
    net = realized_total - total_commission
    initial_notional = float(metadata.get("initial_notional_usdt") or 0.0)
    net_pct = 100.0 * net / max(initial_notional, 1e-9)
    metadata.update(
        {
            "exchange_realized_pnl": realized_total,
            "exit_commission_usdt": exit_commission,
            "realized_net": net,
            "last_exit_order_id": str(result.get("orderId") or ""),
            "last_exit_client_order_id": str(order["client_order_id"]),
        }
    )

    post_rows = client.position_risk(str(position["symbol"]))
    post_active = next(
        (
            item for item in post_rows
            if abs(float(item.get("positionAmt") or 0.0)) > 0
        ),
        None,
    )
    remaining = abs(float(post_active.get("positionAmt") or 0.0)) if post_active else 0.0

    if action == "REDUCE" and remaining > 0:
        update_live_reduce(
            position_id=str(position["position_id"]),
            event_time_ms=int(time.time() * 1000),
            new_quantity=remaining,
            realized_pnl=net,
            realized_pnl_pct=net_pct,
            metadata=metadata,
        )
    else:
        stop_id = metadata.get("protective_stop_client_id")
        if stop_id:
            try:
                client.cancel_algo_order(client_algo_id=str(stop_id))
                metadata["protection_status"] = "CANCELED_AFTER_CLOSE"
            except Exception as exc:
                metadata["stop_cancel_note"] = str(exc)[:240]
        close_live_position(
            position_id=str(position["position_id"]),
            event_time_ms=int(time.time() * 1000),
            exit_price=float(stats["avg_price"]),
            realized_pnl=net,
            realized_pnl_pct=net_pct,
            close_reason=str(order.get("reason") or "stage12_close"),
            metadata=metadata,
        )

    mark_live_order(
        str(order["order_id"]),
        status="FILLED",
        filled_at_ms=int(time.time() * 1000),
        executed_quantity=float(stats["executed_quantity"]),
        reference_price=reference,
        avg_price=float(stats["avg_price"]),
        commission=float(stats["commission"]),
        realized_pnl=float(stats["realized_pnl"]),
        binance_order_id=str(result.get("orderId") or ""),
    )
    return {
        "status": "FILLED",
        "action": action,
        "symbol": position["symbol"],
        "remaining_quantity": remaining,
        "realized_net_total": net,
    }


def execute_pending_live_orders() -> dict[str, Any]:
    if not live_env_enabled() or not live_credentials_configured():
        return {"processed": 0, "filled": 0, "blocked": 0, "errors": []}

    client = BinanceTradingClient()
    orders = list_pending_live_orders(limit=20)
    # Exits first; opening a new position is never more important than reducing risk.
    orders.sort(key=lambda item: 1 if item["action"] == "OPEN" else 0)

    filled = 0
    blocked = 0
    errors: list[str] = []
    details: list[dict[str, Any]] = []
    for order in orders:
        try:
            if order["action"] == "OPEN":
                result = _execute_open(client, order)
            else:
                result = _execute_exit(client, order)
            details.append(result)
            if result.get("status") in {"FILLED", "EMERGENCY_CLOSED"}:
                filled += 1
            elif result.get("status") == "BLOCKED":
                blocked += 1
        except Exception as exc:
            errors.append(
                f"{order.get('order_id')}: {type(exc).__name__}: {str(exc)[:300]}"
            )
    return {
        "processed": len(orders),
        "filled": filled,
        "blocked": blocked,
        "errors": errors,
        "details": details,
    }


def reconcile_exchange_positions() -> dict[str, Any]:
    if not live_env_enabled() or not live_credentials_configured():
        return {"checked": 0, "exchange_flat": 0, "errors": []}
    client = BinanceTradingClient()
    flat = 0
    errors: list[str] = []
    positions = list_open_live_positions()
    for position in positions:
        try:
            active = [
                item for item in client.position_risk(str(position["symbol"]))
                if abs(float(item.get("positionAmt") or 0.0)) > 0
            ]
            if active:
                continue
            metadata = json.loads(position.get("raw_json") or "{}")
            trades = client.user_trades(
                symbol=str(position["symbol"]),
                limit=100,
            )
            after = [
                t for t in trades
                if int(t.get("time") or 0) >= int(position.get("opened_at_ms") or 0)
            ]
            realized = sum(float(t.get("realizedPnl") or 0.0) for t in after)
            commission = sum(
                float(t.get("commission") or 0.0)
                for t in after
                if t.get("commissionAsset") == "USDT"
            )
            net = realized - commission
            last_price = (
                float(after[-1].get("price") or position["entry_price"])
                if after else float(position["entry_price"])
            )
            initial_notional = float(
                metadata.get("initial_notional_usdt")
                or float(position["entry_price"]) * float(metadata.get("initial_quantity") or 0.0)
            )
            close_live_position(
                position_id=str(position["position_id"]),
                event_time_ms=int(time.time() * 1000),
                exit_price=last_price,
                realized_pnl=net,
                realized_pnl_pct=100.0 * net / max(initial_notional, 1e-9),
                close_reason="exchange_flat_reconciled",
                metadata={
                    **metadata,
                    "reconciled_exchange_flat": True,
                    "realized_net": net,
                },
            )
            flat += 1
        except Exception as exc:
            errors.append(
                f"{position.get('position_id')}: {type(exc).__name__}: {str(exc)[:240]}"
            )
    return {"checked": len(positions), "exchange_flat": flat, "errors": errors}


def live_cycle() -> dict[str, Any]:
    reconciliation = reconcile_exchange_positions()
    lifecycle = sync_live_lifecycle_orders()
    exit_exec = execute_pending_live_orders()
    entries = sync_live_entry_orders()
    entry_exec = execute_pending_live_orders()
    return {
        "status": "COMPLETE",
        "reconciliation": reconciliation,
        "lifecycle_queued": lifecycle["queued"],
        "entry": entries,
        "exit_execution": exit_exec,
        "entry_execution": entry_exec,
    }


def start_live_trading_loop() -> bool:
    global _loop_started
    initialize_live_store()

    if not live_env_enabled():
        return False

    with _loop_lock:
        if _loop_started:
            return False
        _loop_started = True

    def _runner() -> None:
        while True:
            try:
                result = live_cycle()
                exit_exec = result["exit_execution"]
                entry_exec = result["entry_execution"]
                if (
                    result["lifecycle_queued"]
                    or result["entry"].get("queued")
                    or exit_exec.get("processed")
                    or entry_exec.get("processed")
                    or exit_exec.get("errors")
                    or entry_exec.get("errors")
                ):
                    print(
                        "Stage 15 live: "
                        f"lifecycle_queued={result['lifecycle_queued']} "
                        f"entry_queued={result['entry'].get('queued', 0)} "
                        f"exit_filled={exit_exec.get('filled', 0)} "
                        f"entry_filled={entry_exec.get('filled', 0)} "
                        f"blocked={exit_exec.get('blocked', 0) + entry_exec.get('blocked', 0)} "
                        f"errors={len(exit_exec.get('errors') or []) + len(entry_exec.get('errors') or [])}",
                        flush=True,
                    )
            except Exception as exc:
                print(
                    "Stage 15 live loop error: "
                    f"{type(exc).__name__}: {str(exc)[:350]}",
                    flush=True,
                )
            time.sleep(_poll_seconds())

    threading.Thread(
        target=_runner,
        name="stage15-guarded-live",
        daemon=True,
    ).start()
    return True
