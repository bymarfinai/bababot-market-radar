from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path
from typing import Any

from .parallel_protection_shadow import (
    BRANCH_KEYS,
    EXECUTION_AUTHORITY,
    PARALLEL_SHADOW_EVENT_VERSION,
    _canonical_json,
    _local_sqlite_connect,
    _record_issue_postgres,
    _record_issue_sqlite,
    _runtime_persistence,
    initialize_parallel_shadow_store,
)

ADAPTER_VERSION = "ps3-v1-protection-adapters"
RAW_EVENT_TYPES = {"AGG_TRADE"}
SAMPLE_EVENT_TYPES = {"PROTECTION_SAMPLE_5S"}

V42_SMALL_ARM = 0.50
V42_SMALL_RETAIN = 0.60
V42_SMALL_CONFIRM = 3
V42_REDUCE_FRACTION = 0.25

V43_SMALL_ARM = 0.50
V43_LONG_RETAIN = 0.97
V43_SHORT_RETAIN = 0.75
V43_SMALL_CONFIRM = 1

RUNNER_QUALIFY = 1.50
RUNNER_RETAIN = 0.90
RUNNER_CONFIRM = 2

DEFAULT_FEE_RATE = 0.0005
DEFAULT_SLIPPAGE_BPS = 2.0
_ADAPTER_LOCK = threading.Lock()


def _obj(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _gross_pct(side: str, entry: float, price: float) -> float:
    if side == "LONG":
        return 100.0 * (price - entry) / entry
    return 100.0 * (entry - price) / entry


def _exit_fill(side: str, price: float, slippage_bps: float) -> float:
    slip = float(slippage_bps) / 10_000.0
    return price * (1.0 - slip) if side == "LONG" else price * (1.0 + slip)


def _gross_usdt(side: str, entry: float, exit_price: float, quantity: float) -> float:
    if side == "LONG":
        return quantity * (exit_price - entry)
    return quantity * (entry - exit_price)


def _cost_model(parent: dict[str, Any]) -> dict[str, float]:
    meta = _obj(parent.get("metadata_json"))
    notional = float(parent["initial_notional_usdt"])
    fee_rate = float(meta.get("fee_rate") or DEFAULT_FEE_RATE)
    slippage_bps = float(meta.get("slippage_bps") or DEFAULT_SLIPPAGE_BPS)
    entry_fee = meta.get("entry_fee_total")
    if entry_fee is None:
        entry_fee = notional * fee_rate
    return {
        "fee_rate": fee_rate,
        "slippage_bps": slippage_bps,
        "entry_fee_total": float(entry_fee),
    }


def _full_close_mark(parent: dict[str, Any], price: float) -> tuple[float, float]:
    side = str(parent["side"]).upper()
    entry = float(parent["entry_price"])
    quantity = float(parent["initial_quantity"])
    notional = float(parent["initial_notional_usdt"])
    costs = _cost_model(parent)
    fill = _exit_fill(side, price, costs["slippage_bps"])
    exit_fee = quantity * fill * costs["fee_rate"]
    realized = (
        _gross_usdt(side, entry, fill, quantity)
        - costs["entry_fee_total"]
        - exit_fee
    )
    pct = 100.0 * realized / notional if notional > 0 else 0.0
    return realized, pct


def _branch_executable_mark(
    parent: dict[str, Any],
    branch: dict[str, Any],
    state: dict[str, Any],
    price: float,
) -> tuple[float, float]:
    if not state.get("settlement_version"):
        return _full_close_mark(parent, price)

    notional = float(parent["initial_notional_usdt"])
    realized = float(state.get("realized_pnl_usdt") or 0.0)
    if str(branch.get("status") or "OPEN").upper() == "CLOSED":
        return realized, (100.0 * realized / notional if notional > 0 else 0.0)

    remaining = float(branch.get("remaining_quantity") or 0.0)
    if remaining <= 1e-12:
        return realized, (100.0 * realized / notional if notional > 0 else 0.0)

    costs = _cost_model(parent)
    side = str(parent["side"]).upper()
    entry = float(parent["entry_price"])
    fill = _exit_fill(side, price, costs["slippage_bps"])
    exit_fee = remaining * fill * costs["fee_rate"]
    remaining_entry_fee = max(
        0.0,
        costs["entry_fee_total"] - float(state.get("entry_fee_allocated_usdt") or 0.0),
    )
    remaining_component = (
        _gross_usdt(side, entry, fill, remaining)
        - remaining_entry_fee
        - exit_fee
    )
    total = realized + remaining_component
    return total, (100.0 * total / notional if notional > 0 else 0.0)


def _base_state(branch_key: str) -> dict[str, Any]:
    return {
        "adapter_version": ADAPTER_VERSION,
        "processed_event_seq": 0,
        "logic_event_count": 0,
        "lane": (
            "V4.2"
            if branch_key == "V42_BASELINE"
            else "V4.3_LS"
            if branch_key == "V43_LS"
            else "BE0.25"
            if branch_key == "BE025_CONSERVATIVE"
            else "BE0.18"
        ),
        "action": "HOLD",
        "reason": "awaiting_protection_evidence",
        "decision_terminal": False,
        "small_running_peak_pct": None,
        "small_consecutive": 0,
        "small_fired": False,
        "runner_mode": False,
        "runner_consecutive": 0,
        "runner_qualified": False,
        "reduce_triggered": False,
        "be_gross_touched": False,
        "be_armed": False,
        "be_arm_event_seq": None,
        "be_superseded": False,
        "virtual_intent": None,
        "intent_history": [],
        "current_pnl_usdt": None,
        "current_pnl_pct": None,
        "gross_pnl_pct": None,
        "executable_net_pct": None,
    }


def _state(branch: dict[str, Any]) -> dict[str, Any]:
    state = _base_state(str(branch["branch_key"]))
    state.update(_obj(branch.get("state_json")))
    return state


def _track_excursion(
    branch: dict[str, Any],
    gross_pct: float,
    *,
    logic_relevant: bool,
) -> tuple[float | None, float | None]:
    prev_mfe = branch.get("mfe_pct")
    prev_mae = branch.get("mae_pct")
    if not logic_relevant:
        return (
            None if prev_mfe is None else float(prev_mfe),
            None if prev_mae is None else float(prev_mae),
        )
    mfe = max(0.0, gross_pct) if prev_mfe is None else max(float(prev_mfe), gross_pct)
    mae = min(0.0, gross_pct) if prev_mae is None else min(float(prev_mae), gross_pct)
    return mfe, mae


def _intent(
    *,
    action: str,
    reason: str,
    event: dict[str, Any],
    price: float,
    fraction: float,
    net_usdt: float,
    net_pct: float,
) -> dict[str, Any]:
    return {
        "action": action,
        "reason": reason,
        "event_seq": int(event["event_seq"]),
        "source_event_id": event["source_event_id"],
        "event_time_ms": int(event["event_time_ms"]),
        "market_price": price,
        "fraction": float(fraction),
        "signal_net_usdt": net_usdt,
        "signal_net_pct": net_pct,
        "settlement_authority": "PS4_NOT_AVAILABLE",
    }


def _emit_intent(state: dict[str, Any], intent: dict[str, Any]) -> None:
    history = list(state.get("intent_history") or [])
    key = (int(intent["event_seq"]), str(intent["action"]).upper())
    if not any(
        (int(item.get("event_seq") or -1), str(item.get("action") or "").upper()) == key
        for item in history
        if isinstance(item, dict)
    ):
        history.append(dict(intent))
        history.sort(key=lambda x: (int(x.get("event_seq") or 0), str(x.get("action") or "")))
    state["intent_history"] = history
    state["virtual_intent"] = dict(intent)


def _sample_peak_step(state: dict[str, Any], gross_pct: float) -> float:
    peak = state.get("small_running_peak_pct")
    if peak is None:
        peak = gross_pct
    else:
        peak = max(float(peak), gross_pct)
    state["small_running_peak_pct"] = peak
    return peak


def _runner_step(
    state: dict[str, Any],
    *,
    gross_pct: float,
    event: dict[str, Any],
    price: float,
    net_usdt: float,
    net_pct: float,
) -> bool:
    peak = _sample_peak_step(state, gross_pct)
    if not bool(state.get("runner_mode")) and peak >= RUNNER_QUALIFY:
        state["runner_mode"] = True
        state["runner_qualified"] = True
        state["small_consecutive"] = 0
        state["lane"] = "V4.2_RUNNER"
        state["reason"] = "runner_qualified"

    if not bool(state.get("runner_mode")):
        return False

    condition = gross_pct <= peak * RUNNER_RETAIN
    state["runner_consecutive"] = (
        int(state.get("runner_consecutive") or 0) + 1 if condition else 0
    )
    state["action"] = "HOLD"
    state["reason"] = (
        f"runner_giveback_confirm_{state['runner_consecutive']}/{RUNNER_CONFIRM}"
        if condition
        else "runner_preservation_monitoring"
    )
    if int(state["runner_consecutive"]) < RUNNER_CONFIRM:
        return False

    state["action"] = "CLOSE"
    state["reason"] = "v42_runner_retain90_confirm2"
    state["decision_terminal"] = True
    _emit_intent(state, _intent(
        action="CLOSE",
        reason=state["reason"],
        event=event,
        price=price,
        fraction=1.0,
        net_usdt=net_usdt,
        net_pct=net_pct,
    ))
    return True


def _v42_step(
    state: dict[str, Any],
    *,
    gross_pct: float,
    event: dict[str, Any],
    price: float,
    net_usdt: float,
    net_pct: float,
) -> None:
    if _runner_step(
        state,
        gross_pct=gross_pct,
        event=event,
        price=price,
        net_usdt=net_usdt,
        net_pct=net_pct,
    ):
        return
    if bool(state.get("runner_mode")) or bool(state.get("small_fired")):
        return

    peak = float(state["small_running_peak_pct"])
    condition = peak >= V42_SMALL_ARM and gross_pct <= peak * V42_SMALL_RETAIN
    state["small_consecutive"] = (
        int(state.get("small_consecutive") or 0) + 1 if condition else 0
    )
    state["action"] = "HOLD"
    state["reason"] = (
        f"v42_reduce_confirm_{state['small_consecutive']}/{V42_SMALL_CONFIRM}"
        if condition
        else "v42_small_profit_monitoring"
    )
    if int(state["small_consecutive"]) < V42_SMALL_CONFIRM:
        return

    state["small_fired"] = True
    state["small_consecutive"] = 0
    state["reduce_triggered"] = True
    state["action"] = "REDUCE"
    state["reason"] = "v42_reduce25_retain60_confirm3"
    _emit_intent(state, _intent(
        action="REDUCE",
        reason=state["reason"],
        event=event,
        price=price,
        fraction=V42_REDUCE_FRACTION,
        net_usdt=net_usdt,
        net_pct=net_pct,
    ))


def _v43_step(
    state: dict[str, Any],
    *,
    side: str,
    gross_pct: float,
    event: dict[str, Any],
    price: float,
    net_usdt: float,
    net_pct: float,
) -> None:
    if _runner_step(
        state,
        gross_pct=gross_pct,
        event=event,
        price=price,
        net_usdt=net_usdt,
        net_pct=net_pct,
    ):
        return
    if bool(state.get("runner_mode")):
        return

    peak = float(state["small_running_peak_pct"])
    retain = V43_LONG_RETAIN if side == "LONG" else V43_SHORT_RETAIN
    condition = peak >= V43_SMALL_ARM and gross_pct <= peak * retain
    state["small_consecutive"] = (
        int(state.get("small_consecutive") or 0) + 1 if condition else 0
    )
    state["action"] = "HOLD"
    state["reason"] = (
        f"v43_ls_full_close_confirm_{state['small_consecutive']}/{V43_SMALL_CONFIRM}"
        if condition
        else "v43_ls_monitoring"
    )
    if int(state["small_consecutive"]) < V43_SMALL_CONFIRM:
        return

    state["small_fired"] = True
    state["action"] = "CLOSE"
    state["reason"] = (
        "v43_ls_long_retain97_full_close"
        if side == "LONG"
        else "v43_ls_short_retain75_full_close"
    )
    state["decision_terminal"] = True
    _emit_intent(state, _intent(
        action="CLOSE",
        reason=state["reason"],
        event=event,
        price=price,
        fraction=1.0,
        net_usdt=net_usdt,
        net_pct=net_pct,
    ))


def _be_raw_step(
    state: dict[str, Any],
    *,
    arm_pct: float,
    gross_pct: float,
    event: dict[str, Any],
    price: float,
    net_usdt: float,
    net_pct: float,
) -> None:
    if bool(state.get("be_superseded")):
        return

    if gross_pct >= arm_pct:
        state["be_gross_touched"] = True

    if (
        bool(state.get("be_gross_touched"))
        and not bool(state.get("be_armed"))
        and net_pct >= 0.0
    ):
        state["be_armed"] = True
        state["be_arm_event_seq"] = int(event["event_seq"])
        state["action"] = "HOLD"
        state["reason"] = f"be{arm_pct:.2f}_armed_net_nonnegative"
        state["lane"] = f"BE{arm_pct:.2f}"

    arm_seq = state.get("be_arm_event_seq")
    if (
        bool(state.get("be_armed"))
        and arm_seq is not None
        and int(event["event_seq"]) > int(arm_seq)
        and net_pct <= 0.0
    ):
        state["action"] = "CLOSE"
        state["reason"] = f"be{arm_pct:.2f}_return_to_net_zero"
        state["decision_terminal"] = True
        _emit_intent(state, _intent(
            action="CLOSE",
            reason=state["reason"],
            event=event,
            price=price,
            fraction=1.0,
            net_usdt=net_usdt,
            net_pct=net_pct,
        ))


def _be_sample_step(
    state: dict[str, Any],
    *,
    side: str,
    gross_pct: float,
    event: dict[str, Any],
    price: float,
    net_usdt: float,
    net_pct: float,
) -> None:
    peak = _sample_peak_step(state, gross_pct)

    # The BE overlay only replaces the historical NO_ACTION lane. Once the
    # observed 5s path reaches the V4.3/V4.2 active-protector universe,
    # BE is causally superseded by that protector family.
    if peak >= V43_SMALL_ARM and not bool(state.get("be_superseded")):
        state["be_superseded"] = True
        state["be_armed"] = False
        state["reason"] = "be_superseded_by_observed_active_protector"

    _v43_step(
        state,
        side=side,
        gross_pct=gross_pct,
        event=event,
        price=price,
        net_usdt=net_usdt,
        net_pct=net_pct,
    )


def _evaluate_branch(
    *,
    parent: dict[str, Any],
    branch: dict[str, Any],
    event: dict[str, Any],
) -> tuple[dict[str, Any], float | None, float | None, str]:
    branch_key = str(branch["branch_key"])
    side = str(parent["side"]).upper()
    entry = float(parent["entry_price"])
    price = float(event["market_price"])
    event_type = str(event["event_type"]).upper()
    gross_pct = _gross_pct(side, entry, price)

    state = _state(branch)
    net_usdt, net_pct = _branch_executable_mark(
        parent,
        branch,
        state,
        price,
    )
    previous_seq = int(state.get("processed_event_seq") or 0)
    seq = int(event["event_seq"])
    if seq != previous_seq + 1:
        raise ValueError(
            f"adapter sequence gap for {branch_key}: expected {previous_seq + 1}, got {seq}"
        )

    terminal = bool(state.get("decision_terminal"))
    raw_event = event_type in RAW_EVENT_TYPES
    sample_event = event_type in SAMPLE_EVENT_TYPES

    # A settled/closed branch must remain a passive PS-2 consumer so all four
    # branch cursors stay sequence-aligned while sibling branches continue.
    if str(branch.get("status") or "OPEN").upper() == "CLOSED":
        state["processed_event_seq"] = seq
        state["last_event_type"] = event_type
        return state, branch.get("mfe_pct"), branch.get("mae_pct"), "CLOSED"

    if branch_key in {"V42_BASELINE", "V43_LS"}:
        logic_relevant = sample_event
    else:
        logic_relevant = raw_event

    mfe, mae = _track_excursion(branch, gross_pct, logic_relevant=logic_relevant)

    state["processed_event_seq"] = seq
    state["last_event_type"] = event_type
    state["gross_pnl_pct"] = gross_pct
    state["executable_net_pct"] = net_pct

    # Before PS-4 settlement, open-branch performance is an executable full
    # close mark. A terminal close signal freezes at its signal event.
    if not terminal:
        state["current_pnl_usdt"] = net_usdt
        state["current_pnl_pct"] = net_pct

    if terminal:
        current_state = "CLOSE_SIGNALLED"
        return state, mfe, mae, current_state

    if not (raw_event or sample_event):
        state["action"] = "HOLD"
        state["reason"] = "event_type_not_used_by_protection_logic"
        return state, mfe, mae, "MONITORING"

    if raw_event:
        if branch_key == "BE025_CONSERVATIVE":
            state["logic_event_count"] = int(state.get("logic_event_count") or 0) + 1
            _be_raw_step(
                state,
                arm_pct=0.25,
                gross_pct=gross_pct,
                event=event,
                price=price,
                net_usdt=net_usdt,
                net_pct=net_pct,
            )
        elif branch_key == "BE018_AGGRESSIVE":
            state["logic_event_count"] = int(state.get("logic_event_count") or 0) + 1
            _be_raw_step(
                state,
                arm_pct=0.18,
                gross_pct=gross_pct,
                event=event,
                price=price,
                net_usdt=net_usdt,
                net_pct=net_pct,
            )
        # V4.2/V4.3 receive raw events for parity/telemetry but do not evaluate.
    elif sample_event:
        if branch_key == "V42_BASELINE":
            state["logic_event_count"] = int(state.get("logic_event_count") or 0) + 1
            _v42_step(
                state,
                gross_pct=gross_pct,
                event=event,
                price=price,
                net_usdt=net_usdt,
                net_pct=net_pct,
            )
        elif branch_key == "V43_LS":
            state["logic_event_count"] = int(state.get("logic_event_count") or 0) + 1
            _v43_step(
                state,
                side=side,
                gross_pct=gross_pct,
                event=event,
                price=price,
                net_usdt=net_usdt,
                net_pct=net_pct,
            )
        elif branch_key in {"BE025_CONSERVATIVE", "BE018_AGGRESSIVE"}:
            state["logic_event_count"] = int(state.get("logic_event_count") or 0) + 1
            _be_sample_step(
                state,
                side=side,
                gross_pct=gross_pct,
                event=event,
                price=price,
                net_usdt=net_usdt,
                net_pct=net_pct,
            )

    if bool(state.get("decision_terminal")):
        current_state = "CLOSE_SIGNALLED"
    elif bool(state.get("runner_mode")):
        current_state = "RUNNER_MONITORING"
    elif state.get("action") == "REDUCE":
        current_state = "REDUCE25_SIGNALLED"
    elif bool(state.get("be_armed")):
        current_state = "BE_ARMED"
    else:
        current_state = "MONITORING"

    return state, mfe, mae, current_state


def _apply_sqlite(
    conn: Any,
    *,
    parent_id: str,
    event_seq: int,
) -> dict[str, Any]:
    parent_row = conn.execute(
        "select * from protection_shadow_parents where parent_id=?",
        (parent_id,),
    ).fetchone()
    if parent_row is None:
        raise KeyError(f"shadow parent not found: {parent_id}")
    parent = dict(parent_row)
    event_row = conn.execute(
        """select * from protection_shadow_events
           where parent_id=? and event_seq=?""",
        (parent_id, event_seq),
    ).fetchone()
    if event_row is None:
        raise KeyError(f"canonical shadow event not found: {parent_id}/{event_seq}")
    event = dict(event_row)
    branch_rows = [
        dict(r)
        for r in conn.execute(
            "select * from protection_shadow_branches where parent_id=?",
            (parent_id,),
        ).fetchall()
    ]
    by_key = {r["branch_key"]: r for r in branch_rows}
    if set(by_key) != set(BRANCH_KEYS):
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="ADAPTER_BRANCH_SET_MISMATCH",
            source_event_id=event["source_event_id"],
            event_seq=event_seq,
            details={"actual": sorted(by_key), "expected": sorted(BRANCH_KEYS)},
        )
        return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_BRANCH_SET_MISMATCH"}

    processed = {
        int(_state(by_key[key]).get("processed_event_seq") or 0)
        for key in BRANCH_KEYS
    }
    if len(processed) != 1:
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="ADAPTER_SEQUENCE_DIVERGENCE",
            source_event_id=event["source_event_id"],
            event_seq=event_seq,
            details={"processed_sequences": sorted(processed)},
        )
        return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_SEQUENCE_DIVERGENCE"}

    previous = next(iter(processed))
    if event_seq <= previous:
        return {
            "status": "ALREADY_PROCESSED",
            "parent_id": parent_id,
            "event_seq": event_seq,
            "processed_event_seq": previous,
        }
    if event_seq != previous + 1:
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="ADAPTER_SEQUENCE_GAP",
            source_event_id=event["source_event_id"],
            event_seq=event_seq,
            details={"expected": previous + 1, "actual": event_seq},
        )
        return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_SEQUENCE_GAP"}

    updates = {}
    now_ms = int(time.time() * 1000)
    for key in BRANCH_KEYS:
        state, mfe, mae, current_state = _evaluate_branch(
            parent=parent,
            branch=by_key[key],
            event=event,
        )
        updates[key] = {
            "state": state,
            "mfe_pct": mfe,
            "mae_pct": mae,
            "current_state": current_state,
        }

    for key in BRANCH_KEYS:
        item = updates[key]
        conn.execute(
            """update protection_shadow_branches
               set current_state=?,mfe_pct=?,mae_pct=?,state_json=?,updated_at_ms=?
               where parent_id=? and branch_key=?""",
            (
                item["current_state"],
                item["mfe_pct"],
                item["mae_pct"],
                _canonical_json(item["state"]),
                now_ms,
                parent_id,
                key,
            ),
        )

    return {
        "status": "ADAPTER_OK",
        "parent_id": parent_id,
        "event_seq": event_seq,
        "source_event_id": event["source_event_id"],
        "event_type": event["event_type"],
        "execution_authority": EXECUTION_AUTHORITY,
        "branches": {
            key: {
                "current_state": updates[key]["current_state"],
                "action": updates[key]["state"]["action"],
                "reason": updates[key]["state"]["reason"],
                "lane": updates[key]["state"]["lane"],
                "be_armed": updates[key]["state"]["be_armed"],
                "runner_qualified": updates[key]["state"]["runner_qualified"],
                "reduce_triggered": updates[key]["state"]["reduce_triggered"],
                "decision_terminal": updates[key]["state"]["decision_terminal"],
                "intent_event_seq": (
                    int((updates[key]["state"].get("virtual_intent") or {}).get("event_seq"))
                    if (updates[key]["state"].get("virtual_intent") or {}).get("event_seq") is not None
                    else None
                ),
            }
            for key in BRANCH_KEYS
        },
    }


def _apply_postgres(
    conn: Any,
    *,
    parent_id: str,
    event_seq: int,
) -> dict[str, Any]:
    runtime = _runtime_persistence()
    with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "select * from protection_shadow_parents where parent_id=%s for update",
            (parent_id,),
        )
        parent = cur.fetchone()
        if parent is None:
            raise KeyError(f"shadow parent not found: {parent_id}")
        parent = dict(parent)
        cur.execute(
            """select * from protection_shadow_events
               where parent_id=%s and event_seq=%s""",
            (parent_id, event_seq),
        )
        event = cur.fetchone()
        if event is None:
            raise KeyError(f"canonical shadow event not found: {parent_id}/{event_seq}")
        event = dict(event)
        cur.execute(
            "select * from protection_shadow_branches where parent_id=%s",
            (parent_id,),
        )
        by_key = {r["branch_key"]: dict(r) for r in cur.fetchall()}
        if set(by_key) != set(BRANCH_KEYS):
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="ADAPTER_BRANCH_SET_MISMATCH",
                source_event_id=event["source_event_id"],
                event_seq=event_seq,
                details={"actual": sorted(by_key), "expected": sorted(BRANCH_KEYS)},
            )
            return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_BRANCH_SET_MISMATCH"}

        processed = {
            int(_state(by_key[key]).get("processed_event_seq") or 0)
            for key in BRANCH_KEYS
        }
        if len(processed) != 1:
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="ADAPTER_SEQUENCE_DIVERGENCE",
                source_event_id=event["source_event_id"],
                event_seq=event_seq,
                details={"processed_sequences": sorted(processed)},
            )
            return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_SEQUENCE_DIVERGENCE"}
        previous = next(iter(processed))
        if event_seq <= previous:
            return {
                "status": "ALREADY_PROCESSED",
                "parent_id": parent_id,
                "event_seq": event_seq,
                "processed_event_seq": previous,
            }
        if event_seq != previous + 1:
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="ADAPTER_SEQUENCE_GAP",
                source_event_id=event["source_event_id"],
                event_seq=event_seq,
                details={"expected": previous + 1, "actual": event_seq},
            )
            return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_SEQUENCE_GAP"}

        updates = {}
        now_ms = int(time.time() * 1000)
        for key in BRANCH_KEYS:
            state, mfe, mae, current_state = _evaluate_branch(
                parent=parent,
                branch=by_key[key],
                event=event,
            )
            updates[key] = {
                "state": state,
                "mfe_pct": mfe,
                "mae_pct": mae,
                "current_state": current_state,
            }
        for key in BRANCH_KEYS:
            item = updates[key]
            cur.execute(
                """update protection_shadow_branches
                   set current_state=%s,mfe_pct=%s,mae_pct=%s,state_json=%s,updated_at_ms=%s
                   where parent_id=%s and branch_key=%s""",
                (
                    item["current_state"],
                    item["mfe_pct"],
                    item["mae_pct"],
                    _canonical_json(item["state"]),
                    now_ms,
                    parent_id,
                    key,
                ),
            )
        return {
            "status": "ADAPTER_OK",
            "parent_id": parent_id,
            "event_seq": event_seq,
            "source_event_id": event["source_event_id"],
            "event_type": event["event_type"],
            "execution_authority": EXECUTION_AUTHORITY,
            "branches": {
                key: {
                    "current_state": updates[key]["current_state"],
                    "action": updates[key]["state"]["action"],
                    "reason": updates[key]["state"]["reason"],
                    "lane": updates[key]["state"]["lane"],
                    "be_armed": updates[key]["state"]["be_armed"],
                    "runner_qualified": updates[key]["state"]["runner_qualified"],
                    "reduce_triggered": updates[key]["state"]["reduce_triggered"],
                    "decision_terminal": updates[key]["state"]["decision_terminal"],
                    "intent_event_seq": (
                        int((updates[key]["state"].get("virtual_intent") or {}).get("event_seq"))
                        if (updates[key]["state"].get("virtual_intent") or {}).get("event_seq") is not None
                        else None
                    ),
                }
                for key in BRANCH_KEYS
            },
        }


def _apply_through_sqlite(
    conn: Any,
    *,
    parent_id: str,
    through_event_seq: int,
) -> dict[str, Any]:
    parent_row = conn.execute(
        "select * from protection_shadow_parents where parent_id=?",
        (parent_id,),
    ).fetchone()
    if parent_row is None:
        raise KeyError(f"shadow parent not found: {parent_id}")
    parent = dict(parent_row)
    branch_rows = [
        dict(r)
        for r in conn.execute(
            "select * from protection_shadow_branches where parent_id=?",
            (parent_id,),
        ).fetchall()
    ]
    by_key = {r["branch_key"]: r for r in branch_rows}
    if set(by_key) != set(BRANCH_KEYS):
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="ADAPTER_BRANCH_SET_MISMATCH",
            event_seq=through_event_seq,
            details={"actual": sorted(by_key), "expected": sorted(BRANCH_KEYS)},
        )
        return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_BRANCH_SET_MISMATCH"}

    processed = {
        int(_state(by_key[key]).get("processed_event_seq") or 0)
        for key in BRANCH_KEYS
    }
    if len(processed) != 1:
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="ADAPTER_SEQUENCE_DIVERGENCE",
            event_seq=through_event_seq,
            details={"processed_sequences": sorted(processed)},
        )
        return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_SEQUENCE_DIVERGENCE"}
    previous = next(iter(processed))
    if through_event_seq <= previous:
        return {
            "status": "ALREADY_PROCESSED",
            "parent_id": parent_id,
            "processed_event_seq": previous,
            "through_event_seq": through_event_seq,
            "processed_n": 0,
        }

    events = [
        dict(r)
        for r in conn.execute(
            """select * from protection_shadow_events
               where parent_id=? and event_seq>? and event_seq<=?
               order by event_seq""",
            (parent_id, previous, through_event_seq),
        ).fetchall()
    ]
    expected = list(range(previous + 1, through_event_seq + 1))
    got = [int(e["event_seq"]) for e in events]
    if got != expected:
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="ADAPTER_SEQUENCE_GAP",
            event_seq=through_event_seq,
            details={"expected": expected[:20], "actual": got[:20]},
        )
        return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_SEQUENCE_GAP"}

    updates: dict[str, dict[str, Any]] = {}
    for event in events:
        for key in BRANCH_KEYS:
            state, mfe, mae, current_state = _evaluate_branch(
                parent=parent,
                branch=by_key[key],
                event=event,
            )
            by_key[key]["state_json"] = _canonical_json(state)
            by_key[key]["mfe_pct"] = mfe
            by_key[key]["mae_pct"] = mae
            by_key[key]["current_state"] = current_state
            updates[key] = {
                "state": state,
                "mfe_pct": mfe,
                "mae_pct": mae,
                "current_state": current_state,
            }

    now_ms = int(time.time() * 1000)
    for key in BRANCH_KEYS:
        item = updates[key]
        conn.execute(
            """update protection_shadow_branches
               set current_state=?,mfe_pct=?,mae_pct=?,state_json=?,updated_at_ms=?
               where parent_id=? and branch_key=?""",
            (
                item["current_state"],
                item["mfe_pct"],
                item["mae_pct"],
                _canonical_json(item["state"]),
                now_ms,
                parent_id,
                key,
            ),
        )

    last = events[-1]
    return {
        "status": "ADAPTER_BATCH_OK",
        "parent_id": parent_id,
        "from_event_seq": previous + 1,
        "through_event_seq": through_event_seq,
        "processed_n": len(events),
        "source_event_id": last["source_event_id"],
        "event_type": last["event_type"],
        "execution_authority": EXECUTION_AUTHORITY,
        "branches": {
            key: {
                "current_state": updates[key]["current_state"],
                "action": updates[key]["state"]["action"],
                "reason": updates[key]["state"]["reason"],
                "lane": updates[key]["state"]["lane"],
                "decision_terminal": updates[key]["state"]["decision_terminal"],
            }
            for key in BRANCH_KEYS
        },
    }


def _apply_through_postgres(
    conn: Any,
    *,
    parent_id: str,
    through_event_seq: int,
) -> dict[str, Any]:
    runtime = _runtime_persistence()
    with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "select * from protection_shadow_parents where parent_id=%s for update",
            (parent_id,),
        )
        parent = cur.fetchone()
        if parent is None:
            raise KeyError(f"shadow parent not found: {parent_id}")
        parent = dict(parent)
        cur.execute(
            "select * from protection_shadow_branches where parent_id=%s",
            (parent_id,),
        )
        by_key = {r["branch_key"]: dict(r) for r in cur.fetchall()}
        if set(by_key) != set(BRANCH_KEYS):
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="ADAPTER_BRANCH_SET_MISMATCH",
                event_seq=through_event_seq,
                details={"actual": sorted(by_key), "expected": sorted(BRANCH_KEYS)},
            )
            return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_BRANCH_SET_MISMATCH"}

        processed = {
            int(_state(by_key[key]).get("processed_event_seq") or 0)
            for key in BRANCH_KEYS
        }
        if len(processed) != 1:
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="ADAPTER_SEQUENCE_DIVERGENCE",
                event_seq=through_event_seq,
                details={"processed_sequences": sorted(processed)},
            )
            return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_SEQUENCE_DIVERGENCE"}
        previous = next(iter(processed))
        if through_event_seq <= previous:
            return {
                "status": "ALREADY_PROCESSED",
                "parent_id": parent_id,
                "processed_event_seq": previous,
                "through_event_seq": through_event_seq,
                "processed_n": 0,
            }

        cur.execute(
            """select * from protection_shadow_events
               where parent_id=%s and event_seq>%s and event_seq<=%s
               order by event_seq""",
            (parent_id, previous, through_event_seq),
        )
        events = [dict(r) for r in cur.fetchall()]
        expected = list(range(previous + 1, through_event_seq + 1))
        got = [int(e["event_seq"]) for e in events]
        if got != expected:
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="ADAPTER_SEQUENCE_GAP",
                event_seq=through_event_seq,
                details={"expected": expected[:20], "actual": got[:20]},
            )
            return {"status": "ADAPTER_ERROR", "reason": "ADAPTER_SEQUENCE_GAP"}

        updates: dict[str, dict[str, Any]] = {}
        for event in events:
            for key in BRANCH_KEYS:
                state, mfe, mae, current_state = _evaluate_branch(
                    parent=parent,
                    branch=by_key[key],
                    event=event,
                )
                by_key[key]["state_json"] = _canonical_json(state)
                by_key[key]["mfe_pct"] = mfe
                by_key[key]["mae_pct"] = mae
                by_key[key]["current_state"] = current_state
                updates[key] = {
                    "state": state,
                    "mfe_pct": mfe,
                    "mae_pct": mae,
                    "current_state": current_state,
                }

        now_ms = int(time.time() * 1000)
        for key in BRANCH_KEYS:
            item = updates[key]
            cur.execute(
                """update protection_shadow_branches
                   set current_state=%s,mfe_pct=%s,mae_pct=%s,state_json=%s,updated_at_ms=%s
                   where parent_id=%s and branch_key=%s""",
                (
                    item["current_state"],
                    item["mfe_pct"],
                    item["mae_pct"],
                    _canonical_json(item["state"]),
                    now_ms,
                    parent_id,
                    key,
                ),
            )

        last = events[-1]
        return {
            "status": "ADAPTER_BATCH_OK",
            "parent_id": parent_id,
            "from_event_seq": previous + 1,
            "through_event_seq": through_event_seq,
            "processed_n": len(events),
            "source_event_id": last["source_event_id"],
            "event_type": last["event_type"],
            "execution_authority": EXECUTION_AUTHORITY,
            "branches": {
                key: {
                    "current_state": updates[key]["current_state"],
                    "action": updates[key]["state"]["action"],
                    "reason": updates[key]["state"]["reason"],
                    "lane": updates[key]["state"]["lane"],
                    "decision_terminal": updates[key]["state"]["decision_terminal"],
                }
                for key in BRANCH_KEYS
            },
        }


def process_shadow_events_through(
    *,
    parent_id: str,
    through_event_seq: int,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Efficiently evaluate every pending canonical event through one sequence."""
    initialize_parallel_shadow_store(path)
    parent_id = str(parent_id).strip()
    through_event_seq = int(through_event_seq)
    if not parent_id:
        raise ValueError("parent_id is required")
    if through_event_seq <= 0:
        raise ValueError("through_event_seq must be positive")

    with _ADAPTER_LOCK:
        if path is not None:
            with _local_sqlite_connect(path) as conn:
                with conn:
                    return _apply_through_sqlite(
                        conn,
                        parent_id=parent_id,
                        through_event_seq=through_event_seq,
                    )
        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                with conn:
                    return _apply_through_sqlite(
                        conn,
                        parent_id=parent_id,
                        through_event_seq=through_event_seq,
                    )
        with runtime._postgres_connect() as conn:
            return _apply_through_postgres(
                conn,
                parent_id=parent_id,
                through_event_seq=through_event_seq,
            )


def process_shadow_event(
    *,
    parent_id: str,
    event_seq: int,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate one already-fanned-out canonical event across all four branches.

    PS-3 emits only virtual intents/state. It never changes branch status,
    remaining quantity, or source-position execution authority.
    """
    initialize_parallel_shadow_store(path)
    parent_id = str(parent_id).strip()
    event_seq = int(event_seq)
    if not parent_id:
        raise ValueError("parent_id is required")
    if event_seq <= 0:
        raise ValueError("event_seq must be positive")

    with _ADAPTER_LOCK:
        if path is not None:
            with _local_sqlite_connect(path) as conn:
                with conn:
                    return _apply_sqlite(conn, parent_id=parent_id, event_seq=event_seq)

        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                with conn:
                    return _apply_sqlite(conn, parent_id=parent_id, event_seq=event_seq)

        with runtime._postgres_connect() as conn:
            return _apply_postgres(conn, parent_id=parent_id, event_seq=event_seq)


def process_pending_shadow_events(
    parent_id: str,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Catch a parent up sequentially to the canonical PS-2 ledger."""
    initialize_parallel_shadow_store(path)

    def read_max_and_processed(conn: Any, postgres: bool = False) -> tuple[int, int]:
        if not postgres:
            event = conn.execute(
                "select max(event_seq) from protection_shadow_events where parent_id=?",
                (parent_id,),
            ).fetchone()
            branches = conn.execute(
                "select state_json from protection_shadow_branches where parent_id=?",
                (parent_id,),
            ).fetchall()
            max_seq = int((event[0] if event else 0) or 0)
            processed = {
                int(_obj(r[0]).get("processed_event_seq") or 0)
                for r in branches
            }
        else:
            runtime = _runtime_persistence()
            with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "select max(event_seq) as max_seq from protection_shadow_events where parent_id=%s",
                    (parent_id,),
                )
                max_seq = int((cur.fetchone()["max_seq"] or 0))
                cur.execute(
                    "select state_json from protection_shadow_branches where parent_id=%s",
                    (parent_id,),
                )
                processed = {
                    int(_obj(r["state_json"]).get("processed_event_seq") or 0)
                    for r in cur.fetchall()
                }
        if len(processed) > 1:
            raise RuntimeError("adapter sequence divergence before catch-up")
        return max_seq, (next(iter(processed)) if processed else 0)

    if path is not None:
        with _local_sqlite_connect(path) as conn:
            max_seq, processed = read_max_and_processed(conn)
    else:
        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                max_seq, processed = read_max_and_processed(conn)
        else:
            with runtime._postgres_connect() as conn:
                max_seq, processed = read_max_and_processed(conn, postgres=True)

    results = []
    for seq in range(processed + 1, max_seq + 1):
        result = process_shadow_event(parent_id=parent_id, event_seq=seq, path=path)
        results.append(result)
        if result["status"] == "ADAPTER_ERROR":
            break
    return {
        "status": "COMPLETE" if all(r["status"] == "ADAPTER_OK" for r in results) else "ERROR",
        "parent_id": parent_id,
        "from_event_seq": processed + 1 if results else None,
        "to_event_seq": results[-1]["event_seq"] if results else processed,
        "processed_n": len(results),
        "execution_authority": EXECUTION_AUTHORITY,
        "results": results,
    }


def adapter_contract() -> dict[str, Any]:
    return {
        "adapter_version": ADAPTER_VERSION,
        "execution_authority": EXECUTION_AUTHORITY,
        "raw_event_types": sorted(RAW_EVENT_TYPES),
        "sample_event_types": sorted(SAMPLE_EVENT_TYPES),
        "v42": {
            "small_arm_pct": V42_SMALL_ARM,
            "small_retain": V42_SMALL_RETAIN,
            "small_confirm": V42_SMALL_CONFIRM,
            "reduce_fraction": V42_REDUCE_FRACTION,
            "runner_qualify_pct": RUNNER_QUALIFY,
            "runner_retain": RUNNER_RETAIN,
            "runner_confirm": RUNNER_CONFIRM,
        },
        "v43_ls": {
            "small_arm_pct": V43_SMALL_ARM,
            "long_retain": V43_LONG_RETAIN,
            "short_retain": V43_SHORT_RETAIN,
            "small_confirm": V43_SMALL_CONFIRM,
            "small_close_fraction": 1.0,
            "runner": "V4.2",
            "prospective_scope": "causal_from_entry_until_runner_is_observed",
            "frozen_research_scope": "ex_post_v42_reduce25_only",
            "comparability_warning": (
                "Prospective full-cohort V4.3 is not expected to reproduce the "
                "frozen ex-post -43.31 result because future runner membership "
                "is not knowable at the early V4.3 close trigger."
            ),
        },
        "be025": {
            "gross_arm_pct": 0.25,
            "arm_requires_executable_net_nonnegative": True,
            "close_on_later_executable_net_le_zero": True,
            "superseded_by_observed_active_protector_at_pct": V43_SMALL_ARM,
            "reduce25_logic": "V4.3_LS",
            "runner_logic": "V4.2",
            "comparability_warning": (
                "Frozen BE+V4.3 results used ex-post V4.2 lane membership. "
                "Prospective shadow is causal and may diverge on future runners."
            ),
        },
        "be018": {
            "gross_arm_pct": 0.18,
            "arm_requires_executable_net_nonnegative": True,
            "close_on_later_executable_net_le_zero": True,
            "superseded_by_observed_active_protector_at_pct": V43_SMALL_ARM,
            "reduce25_logic": "V4.3_LS",
            "runner_logic": "V4.2",
            "comparability_warning": (
                "Frozen BE+V4.3 results used ex-post V4.2 lane membership. "
                "Prospective shadow is causal and may diverge on future runners."
            ),
        },
        "cost_defaults": {
            "fee_rate": DEFAULT_FEE_RATE,
            "slippage_bps": DEFAULT_SLIPPAGE_BPS,
        },
        "research_scope_warning": {
            "v43_frozen": (
                "Frozen V4.3 historical headline replaced only ex-post V4.2 "
                "REDUCE25 trades. The forward shadow branch is causal and may "
                "close trades that would later become runners."
            ),
            "be_frozen": (
                "Frozen BE integration replaced ex-post NO_ACTION trades. "
                "Forward BE branches use causal evidence/handoff and must be "
                "judged by prospective shadow results, not the frozen headline."
            ),
        },
        "settlement": "PS4_AVAILABLE_VIRTUAL_ONLY",
    }
