from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from .binance import BinancePublicClient
from .control_state import get_control_state
from .fresh_entry_gate import check_fresh_entry, fill_max_age_ms
from .paper_store import (
    close_position,
    count_open_paper_positions,
    create_order,
    create_position,
    get_entry_candidate,
    get_paper_order,
    get_position,
    has_open_paper_symbol,
    initialize_paper_store,
    list_entry_candidates,
    list_pending_orders,
    list_unacted_lifecycle_actions,
    mark_order,
    update_position_reduce,
)


PAPER_TRADING_VERSION = "stage13-v2-event-driven"
_loop_lock = threading.Lock()
_entry_handoff_lock = threading.Lock()
_loop_started = False


def paper_trading_enabled() -> bool:
    value = os.environ.get("PAPER_TRADING_ENABLED", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _notional_usdt() -> float:
    return max(1.0, float(os.environ.get("PAPER_NOTIONAL_USDT", "500")))


def _max_open_positions() -> int:
    # 0 means unlimited paper positions. Positive values keep the old cap behavior.
    return max(0, min(int(os.environ.get("PAPER_MAX_OPEN_POSITIONS", "5")), 50))


def _at_open_capacity() -> bool:
    limit = _max_open_positions()
    return limit > 0 and count_open_paper_positions() >= limit


def _entry_max_age_ms() -> int:
    minutes = max(
        1.0,
        float(os.environ.get("PAPER_ENTRY_MAX_AGE_MINUTES", "15")),
    )
    return int(minutes * 60_000)


def _reduce_fraction() -> float:
    return max(
        0.05,
        min(float(os.environ.get("PAPER_REDUCE_FRACTION", "0.50")), 0.95),
    )


def _fee_rate() -> float:
    return max(
        0.0,
        min(float(os.environ.get("PAPER_FEE_RATE", "0.00075")), 0.01),
    )


def _slippage_bps() -> float:
    return max(
        0.0,
        min(float(os.environ.get("PAPER_SLIPPAGE_BPS", "2")), 100.0),
    )


def _hard_stop_pct() -> float:
    return max(
        0.0,
        min(float(os.environ.get("PAPER_HARD_STOP_PCT", "0")), 20.0),
    )


def _poll_seconds() -> float:
    return max(
        2.0,
        min(float(os.environ.get("PAPER_POLL_SECONDS", "10")), 60.0),
    )


def _fill_price(
    *,
    market_price: float,
    side: str,
    action: str,
) -> float:
    slip = _slippage_bps() / 10_000.0
    side = side.upper()
    action = action.upper()

    # OPEN LONG = buy; CLOSE/REDUCE SHORT = buy.
    buying = (
        (action == "OPEN" and side == "LONG")
        or (action in {"REDUCE", "CLOSE"} and side == "SHORT")
    )
    return market_price * (1.0 + slip if buying else 1.0 - slip)


def _gross_pnl(
    *,
    side: str,
    entry_price: float,
    exit_price: float,
    quantity: float,
) -> float:
    if side.upper() == "LONG":
        return quantity * (exit_price - entry_price)
    return quantity * (entry_price - exit_price)


def _metadata(position: dict[str, Any]) -> dict[str, Any]:
    raw = position.get("raw_json")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _stage11c_order_payload(
    candidate: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "approval_reviewed_at_ms": candidate["reviewed_at_ms"],
        "signal_time_ms": candidate["signal_time_ms"],
        "signal_price": candidate["signal_price"],
        "stage": candidate["stage"],
        "long_score": candidate["long_score"],
        "short_score": candidate["short_score"],
        "score_edge": candidate["score_edge"],
        "stage11c_checked_at_ms": gate.get("checked_at_ms"),
        "stage11c_verdict": gate.get("verdict"),
        "stage11c_reasons": gate.get("reasons") or [],
        "stage11c_snapshot": gate.get("snapshot") or {},
        "stage11c_version": gate.get("version"),
        "stage13_version": PAPER_TRADING_VERSION,
    }


def process_approved_signal(signal_id: str) -> dict[str, Any]:
    """Immediate Stage 11 -> 11C -> Stage 13 paper entry handoff.

    The polling loop remains a recovery path, but fresh APPROVE decisions no
    longer need to wait for PAPER_POLL_SECONDS before revalidation/execution.
    """
    if not paper_trading_enabled():
        return {"status": "DISABLED", "signal_id": signal_id}

    with _entry_handoff_lock:
        control = get_control_state()
        if not control.get("entries_enabled"):
            return {
                "status": "CONTROL_BLOCKED",
                "signal_id": signal_id,
            }

        candidate = get_entry_candidate(signal_id)
        if candidate is None:
            return {
                "status": "NOT_ELIGIBLE",
                "signal_id": signal_id,
            }

        if _at_open_capacity():
            return {
                "status": "DEFERRED",
                "reason": "max_open_positions",
                "signal_id": signal_id,
            }

        symbol = str(candidate["symbol"]).upper()
        if has_open_paper_symbol(symbol):
            return {
                "status": "SKIPPED",
                "reason": "symbol_position_already_open",
                "signal_id": signal_id,
            }

        client = BinancePublicClient(timeout=5.0, retries=1)
        gate = check_fresh_entry(client, candidate)
        verdict = str(gate.get("verdict") or "WAIT").upper()

        if verdict == "WAIT":
            return {
                "status": "WAIT",
                "signal_id": signal_id,
                "stage11c": gate,
            }

        payload = _stage11c_order_payload(candidate, gate)
        order_id = create_order(
            source_type="ENTRY",
            source_id=signal_id,
            position_id=f"PAPER:{signal_id}",
            signal_id=signal_id,
            symbol=symbol,
            side=str(candidate["side"]),
            action="OPEN",
            requested_quantity=None,
            reason=(
                "stage11c_enter"
                if verdict == "ENTER"
                else "stage11c_cancel"
            ),
            payload=payload,
        )

        if verdict == "CANCEL":
            mark_order(
                order_id,
                status="SKIPPED",
                reason="stage11c_cancel:" + ",".join(gate.get("reasons") or [])[:500],
            )
            return {
                "status": "CANCEL",
                "signal_id": signal_id,
                "order_id": order_id,
                "stage11c": gate,
            }

        order = get_paper_order(order_id)
        if order is None:
            return {
                "status": "ERROR",
                "reason": "created_order_not_found",
                "signal_id": signal_id,
                "order_id": order_id,
                "stage11c": gate,
            }

        execution = _execute_open(client, order)
        return {
            "status": execution.get("status"),
            "signal_id": signal_id,
            "order_id": order_id,
            "stage11c": gate,
            "execution": execution,
        }


def sync_entry_orders() -> dict[str, int]:
    if not paper_trading_enabled():
        return {
            "queued": 0,
            "capacity_blocked": 0,
            "symbol_blocked": 0,
            "control_blocked": 0,
            "stage11c_enter": 0,
            "stage11c_wait": 0,
            "stage11c_cancel": 0,
        }

    control = get_control_state()
    if not control.get("entries_enabled"):
        return {
            "queued": 0,
            "capacity_blocked": 0,
            "symbol_blocked": 0,
            "control_blocked": 1,
            "stage11c_enter": 0,
            "stage11c_wait": 0,
            "stage11c_cancel": 0,
        }

    queued = 0
    capacity_blocked = 0
    symbol_blocked = 0
    stage11c_enter = 0
    stage11c_wait = 0
    stage11c_cancel = 0
    client = BinancePublicClient(timeout=5.0, retries=1)
    candidates = list_entry_candidates(
        max_age_ms=_entry_max_age_ms(),
        limit=max(1, min(int(os.environ.get("STAGE11C_MAX_PER_CYCLE", "12")), 50)),
    )

    for candidate in candidates:
        if _at_open_capacity():
            capacity_blocked += 1
            break

        symbol = str(candidate["symbol"]).upper()
        if has_open_paper_symbol(symbol):
            symbol_blocked += 1
            continue

        gate = check_fresh_entry(client, candidate)
        verdict = str(gate.get("verdict") or "WAIT").upper()

        if verdict == "WAIT":
            stage11c_wait += 1
            continue

        payload = _stage11c_order_payload(candidate, gate)

        order_id = create_order(
            source_type="ENTRY",
            source_id=str(candidate["signal_id"]),
            position_id=f"PAPER:{candidate['signal_id']}",
            signal_id=str(candidate["signal_id"]),
            symbol=symbol,
            side=str(candidate["side"]),
            action="OPEN",
            requested_quantity=None,
            reason=(
                "stage11c_enter"
                if verdict == "ENTER"
                else "stage11c_cancel"
            ),
            payload=payload,
        )

        if verdict == "CANCEL":
            mark_order(
                order_id,
                status="SKIPPED",
                reason="stage11c_cancel:" + ",".join(gate.get("reasons") or [])[:500],
            )
            stage11c_cancel += 1
            continue

        queued += 1
        stage11c_enter += 1

    return {
        "queued": queued,
        "capacity_blocked": capacity_blocked,
        "symbol_blocked": symbol_blocked,
        "control_blocked": 0,
        "stage11c_enter": stage11c_enter,
        "stage11c_wait": stage11c_wait,
        "stage11c_cancel": stage11c_cancel,
    }


def sync_lifecycle_orders() -> dict[str, int]:
    if not paper_trading_enabled():
        return {"queued": 0}

    queued = 0
    latest_by_position: dict[str, dict[str, Any]] = {}
    for item in list_unacted_lifecycle_actions(limit=200):
        position_id = str(item["position_id"])
        previous = latest_by_position.get(position_id)
        if (
            previous is None
            or int(item["candle_close_time_ms"])
            > int(previous["candle_close_time_ms"])
        ):
            latest_by_position[position_id] = item

    for item in latest_by_position.values():
        action = str(item["final_action"]).upper()
        position = get_position(str(item["position_id"]))
        if not position or position.get("status") not in {"OPEN", "REDUCED"}:
            continue

        if action == "REDUCE" and position.get("status") == "REDUCED":
            # Only one 50% risk reduction per paper position.
            continue

        requested = None
        if action == "REDUCE":
            requested = float(position.get("quantity") or 0.0) * _reduce_fraction()

        create_order(
            source_type="LIFECYCLE",
            source_id=str(item["evaluation_id"]),
            position_id=str(item["position_id"]),
            signal_id=str(position.get("signal_id") or ""),
            symbol=str(position["symbol"]),
            side=str(position["side"]),
            action=action,
            requested_quantity=requested,
            reason=(
                "stage12_hard_risk"
                if item.get("hard_risk_triggered")
                else f"stage12_{action.lower()}"
            ),
            payload={
                "health_score": item["health_score"],
                "deterministic_action": item["deterministic_action"],
                "ai_action": item.get("ai_action"),
                "ai_confidence": item.get("ai_confidence"),
                "final_action": action,
                "candle_close_time_ms": item["candle_close_time_ms"],
            },
        )
        queued += 1

    return {"queued": queued}


def _execute_open(
    client: BinancePublicClient,
    order: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    try:
        payload = json.loads(order.get("payload_json") or "{}")
    except Exception:
        payload = {}

    now_ms = int(time.time() * 1000)
    approval_ms = int(payload.get("approval_reviewed_at_ms") or 0)
    if approval_ms > 0 and now_ms - approval_ms > _entry_max_age_ms():
        mark_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="approval_stale_before_fill",
        )
        return {"status": "SKIPPED", "reason": "approval_stale_before_fill"}

    gate_ms = int(payload.get("stage11c_checked_at_ms") or 0)
    if gate_ms <= 0 or now_ms - gate_ms > fill_max_age_ms():
        mark_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="stage11c_stale_before_fill",
        )
        return {"status": "SKIPPED", "reason": "stage11c_stale_before_fill"}

    if _at_open_capacity():
        return {"status": "DEFERRED", "reason": "max_open_positions"}

    symbol = str(order["symbol"]).upper()
    if has_open_paper_symbol(symbol):
        mark_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="symbol_position_already_open",
        )
        return {"status": "SKIPPED", "reason": "symbol_position_already_open"}

    market_price = client.ticker_price(symbol)
    fill = _fill_price(
        market_price=market_price,
        side=str(order["side"]),
        action="OPEN",
    )
    notional = _notional_usdt()
    quantity = notional / fill
    fee = notional * _fee_rate()
    opened_at_ms = int(time.time() * 1000)

    stop_loss: float | None = None
    stop_pct = _hard_stop_pct()
    if stop_pct > 0:
        delta = stop_pct / 100.0
        stop_loss = (
            fill * (1.0 - delta)
            if str(order["side"]).upper() == "LONG"
            else fill * (1.0 + delta)
        )

    metadata = {
        "paper_trading_version": PAPER_TRADING_VERSION,
        "initial_notional_usdt": notional,
        "initial_quantity": quantity,
        "entry_market_price": market_price,
        "entry_fill_price": fill,
        "entry_fee_total": fee,
        "allocated_entry_fee": 0.0,
        "exit_fees": 0.0,
        "realized_gross": 0.0,
        "realized_net": 0.0,
        "closed_quantity": 0.0,
        "slippage_bps": _slippage_bps(),
        "fee_rate": _fee_rate(),
        "hard_stop_pct": stop_pct,
    }

    create_position(
        position_id=str(order["position_id"]),
        signal_id=str(order["signal_id"]),
        symbol=symbol,
        side=str(order["side"]),
        opened_at_ms=opened_at_ms,
        entry_price=fill,
        quantity=quantity,
        stop_loss=stop_loss,
        metadata=metadata,
    )
    mark_order(
        str(order["order_id"]),
        status="FILLED",
        executed_at_ms=opened_at_ms,
        executed_quantity=quantity,
        market_price=market_price,
        fill_price=fill,
        fee=fee,
        reason="paper_market_entry",
    )
    return {
        "status": "FILLED",
        "action": "OPEN",
        "symbol": symbol,
        "fill_price": fill,
        "quantity": quantity,
        "fee": fee,
    }


def _execute_exit(
    client: BinancePublicClient,
    order: dict[str, Any],
) -> dict[str, Any]:
    position = get_position(str(order["position_id"]))
    if not position or position.get("status") not in {"OPEN", "REDUCED"}:
        mark_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="position_not_open",
        )
        return {"status": "SKIPPED", "reason": "position_not_open"}

    action = str(order["action"]).upper()
    if action == "REDUCE" and position.get("status") == "REDUCED":
        mark_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="already_reduced",
        )
        return {"status": "SKIPPED", "reason": "already_reduced"}

    current_qty = float(position.get("quantity") or 0.0)
    if current_qty <= 0:
        mark_order(
            str(order["order_id"]),
            status="SKIPPED",
            reason="zero_quantity",
        )
        return {"status": "SKIPPED", "reason": "zero_quantity"}

    if action == "REDUCE":
        requested = float(order.get("requested_quantity") or 0.0)
        qty = min(current_qty, max(0.0, requested))
        if qty <= 0:
            qty = current_qty * _reduce_fraction()
    else:
        qty = current_qty

    symbol = str(position["symbol"]).upper()
    market_price = client.ticker_price(symbol)
    fill = _fill_price(
        market_price=market_price,
        side=str(position["side"]),
        action=action,
    )
    exit_fee = qty * fill * _fee_rate()

    metadata = _metadata(position)
    initial_qty = float(metadata.get("initial_quantity") or current_qty)
    entry_fee_total = float(metadata.get("entry_fee_total") or 0.0)
    allocated_before = float(metadata.get("allocated_entry_fee") or 0.0)
    allocated_entry_fee = (
        entry_fee_total * (qty / initial_qty)
        if initial_qty > 0
        else 0.0
    )

    gross = _gross_pnl(
        side=str(position["side"]),
        entry_price=float(position["entry_price"]),
        exit_price=fill,
        quantity=qty,
    )
    net_increment = gross - allocated_entry_fee - exit_fee

    realized_gross = float(metadata.get("realized_gross") or 0.0) + gross
    realized_net = float(metadata.get("realized_net") or 0.0) + net_increment
    exit_fees = float(metadata.get("exit_fees") or 0.0) + exit_fee
    closed_qty = float(metadata.get("closed_quantity") or 0.0) + qty
    allocated_total = allocated_before + allocated_entry_fee
    initial_notional = float(
        metadata.get("initial_notional_usdt") or _notional_usdt()
    )
    realized_pct = (
        100.0 * realized_net / initial_notional
        if initial_notional > 0
        else 0.0
    )

    metadata.update(
        {
            "allocated_entry_fee": allocated_total,
            "exit_fees": exit_fees,
            "realized_gross": realized_gross,
            "realized_net": realized_net,
            "closed_quantity": closed_qty,
            "last_exit_market_price": market_price,
            "last_exit_fill_price": fill,
            "last_exit_action": action,
            "last_exit_at_ms": int(time.time() * 1000),
        }
    )

    executed_at = int(time.time() * 1000)
    if action == "REDUCE":
        new_qty = max(0.0, current_qty - qty)
        update_position_reduce(
            position_id=str(position["position_id"]),
            event_time_ms=executed_at,
            new_quantity=new_qty,
            realized_pnl=realized_net,
            realized_pnl_pct=realized_pct,
            metadata=metadata,
        )
    else:
        close_position(
            position_id=str(position["position_id"]),
            event_time_ms=executed_at,
            exit_price=fill,
            realized_pnl=realized_net,
            realized_pnl_pct=realized_pct,
            close_reason=str(order.get("reason") or "stage12_close"),
            metadata=metadata,
        )

    mark_order(
        str(order["order_id"]),
        status="FILLED",
        executed_at_ms=executed_at,
        executed_quantity=qty,
        market_price=market_price,
        fill_price=fill,
        fee=exit_fee,
        reason=str(order.get("reason") or action.lower()),
    )
    return {
        "status": "FILLED",
        "action": action,
        "symbol": symbol,
        "fill_price": fill,
        "quantity": qty,
        "fee": exit_fee,
        "realized_net_increment": net_increment,
        "realized_net_total": realized_net,
        "realized_pnl_pct": realized_pct,
    }


def execute_pending_orders(
    *,
    actions: set[str] | None = None,
) -> dict[str, Any]:
    if not paper_trading_enabled():
        return {"processed": 0, "filled": 0, "skipped": 0, "deferred": 0}

    client = BinancePublicClient(timeout=8.0, retries=2)
    filled = 0
    skipped = 0
    deferred = 0
    errors: list[str] = []
    fill_details: list[dict[str, Any]] = []

    orders = list_pending_orders(limit=100)
    if actions is not None:
        wanted = {item.upper() for item in actions}
        orders = [
            order for order in orders
            if str(order.get("action") or "").upper() in wanted
        ]

    for order in orders:
        try:
            if str(order["action"]).upper() == "OPEN":
                result = _execute_open(client, order)
            else:
                result = _execute_exit(client, order)

            if result["status"] == "FILLED":
                filled += 1
                fill_details.append(result)
            elif result["status"] == "SKIPPED":
                skipped += 1
            elif result["status"] == "DEFERRED":
                deferred += 1
        except Exception as exc:
            errors.append(
                f"{order.get('order_id')}: "
                f"{type(exc).__name__}: {str(exc)[:240]}"
            )

    return {
        "processed": len(orders),
        "filled": filled,
        "skipped": skipped,
        "deferred": deferred,
        "errors": errors,
        "fills": fill_details,
    }


def paper_cycle() -> dict[str, Any]:
    if not paper_trading_enabled():
        return {"status": "DISABLED"}

    lifecycle = sync_lifecycle_orders()
    exits = execute_pending_orders(actions={"REDUCE", "CLOSE"})
    control = get_control_state()
    with _entry_handoff_lock:
        entries = sync_entry_orders()
        if control.get("entries_enabled"):
            entry_exec = execute_pending_orders(actions={"OPEN"})
        else:
            entry_exec = {
                "processed": 0,
                "filled": 0,
                "skipped": 0,
                "deferred": 0,
                "errors": [],
                "fills": [],
            }
    return {
        "status": "COMPLETE",
        "lifecycle_queued": lifecycle["queued"],
        "exit_execution": exits,
        "entry_queued": entries["queued"],
        "entry_capacity_blocked": entries["capacity_blocked"],
        "entry_symbol_blocked": entries["symbol_blocked"],
        "entry_control_blocked": entries.get("control_blocked", 0),
        "stage11c_enter": entries.get("stage11c_enter", 0),
        "stage11c_wait": entries.get("stage11c_wait", 0),
        "stage11c_cancel": entries.get("stage11c_cancel", 0),
        "entry_execution": entry_exec,
    }


def start_paper_trading_loop() -> bool:
    global _loop_started

    if not paper_trading_enabled():
        return False

    with _loop_lock:
        if _loop_started:
            return False
        _loop_started = True

    initialize_paper_store()

    def _runner() -> None:
        while True:
            try:
                result = paper_cycle()
                exit_exec = result.get("exit_execution") or {}
                entry_exec = result.get("entry_execution") or {}
                meaningful = (
                    result.get("lifecycle_queued", 0)
                    or result.get("entry_queued", 0)
                    or exit_exec.get("processed", 0)
                    or entry_exec.get("processed", 0)
                    or exit_exec.get("errors")
                    or entry_exec.get("errors")
                )
                if meaningful:
                    exit_sample = ";".join(
                        (
                            f"{item.get('action')}:{item.get('symbol')}:"
                            f"{float(item.get('realized_net_increment') or 0.0):+.4f}"
                        )
                        for item in (exit_exec.get("fills") or [])[:5]
                    )
                    entry_sample = ";".join(
                        (
                            f"{item.get('action')}:{item.get('symbol')}:"
                            f"{float(item.get('fill_price') or 0.0):.8g}"
                        )
                        for item in (entry_exec.get("fills") or [])[:5]
                    )
                    print(
                        "Stage 13 paper: "
                        f"lifecycle_queued={result.get('lifecycle_queued', 0)} "
                        f"entry_queued={result.get('entry_queued', 0)} "
                        f"exit_filled={exit_exec.get('filled', 0)} "
                        f"entry_filled={entry_exec.get('filled', 0)} "
                        f"deferred={exit_exec.get('deferred', 0) + entry_exec.get('deferred', 0)} "
                        f"control_blocked={result.get('entry_control_blocked', 0)} "
                        f"11c_enter={result.get('stage11c_enter', 0)} "
                        f"11c_wait={result.get('stage11c_wait', 0)} "
                        f"11c_cancel={result.get('stage11c_cancel', 0)} "
                        f"errors={len(exit_exec.get('errors') or []) + len(entry_exec.get('errors') or [])} "
                        f"exit_sample={exit_sample or '-'} "
                        f"entry_sample={entry_sample or '-'}",
                        flush=True,
                    )
            except Exception as exc:
                print(
                    "Stage 13 paper loop error: "
                    f"{type(exc).__name__}: {str(exc)[:300]}",
                    flush=True,
                )
            time.sleep(_poll_seconds())

    threading.Thread(
        target=_runner,
        name="stage13-paper-trading",
        daemon=True,
    ).start()
    return True
