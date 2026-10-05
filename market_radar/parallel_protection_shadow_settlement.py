from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from .parallel_protection_shadow import (
    BRANCH_KEYS,
    EXECUTION_AUTHORITY,
    _canonical_json,
    _local_sqlite_connect,
    _runtime_persistence,
    audit_shadow_parity,
    initialize_parallel_shadow_store,
)
from .parallel_protection_shadow_adapters import (
    _cost_model,
    _exit_fill,
    _gross_usdt,
    _obj,
)

SETTLEMENT_VERSION = "ps4-v1-shadow-settlement"
SOURCE_REDUCE_EVENT = "SOURCE_POSITION_REDUCE"
SOURCE_CLOSE_EVENT = "SOURCE_POSITION_CLOSE"
_SETTLEMENT_LOCK = threading.Lock()
_READY: set[tuple[str, str]] = set()
_EPS = 1e-12

_SQLITE_SCHEMA = """
create table if not exists protection_shadow_settlements (
    settlement_id text primary key,
    parent_id text not null,
    branch_key text not null,
    event_seq integer not null check (event_seq > 0),
    source_event_id text not null,
    event_time_ms integer not null,
    intent_source text not null check (intent_source in ('PROTECTION','SOURCE_LIFECYCLE')),
    action text not null check (action in ('REDUCE','CLOSE')),
    reason text not null,
    requested_fraction real not null check (requested_fraction >= 0 and requested_fraction <= 1),
    quantity_before real not null check (quantity_before >= 0),
    executed_quantity real not null check (executed_quantity >= 0),
    quantity_after real not null check (quantity_after >= 0),
    market_price real not null check (market_price > 0),
    fill_price real,
    entry_fee_allocated_usdt real not null,
    exit_fee_usdt real not null,
    realized_delta_usdt real not null,
    realized_total_usdt real not null,
    status text not null check (status in ('VIRTUAL_FILLED','VIRTUAL_SKIPPED')),
    settlement_version text not null,
    created_at_ms integer not null,
    unique(parent_id, branch_key, event_seq, intent_source, action)
);
create index if not exists idx_shadow_settlement_parent_branch
on protection_shadow_settlements(parent_id, branch_key, event_seq);
create index if not exists idx_shadow_settlement_parent_event
on protection_shadow_settlements(parent_id, event_seq);
"""

_POSTGRES_SCHEMA = _SQLITE_SCHEMA.replace(" integer not null", " bigint not null").replace(
    " integer,", " bigint,"
)


def initialize_shadow_settlement_store(path: str | Path | None = None) -> None:
    initialize_parallel_shadow_store(path)
    if path is not None:
        key = ("sqlite", str(Path(path).resolve()))
        with _SETTLEMENT_LOCK:
            if key in _READY:
                return
            with _local_sqlite_connect(path) as conn:
                conn.executescript(_SQLITE_SCHEMA)
            _READY.add(key)
        return

    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        key = ("sqlite", str(runtime.database_path().resolve()))
        with _SETTLEMENT_LOCK:
            if key in _READY:
                return
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                conn.executescript(_SQLITE_SCHEMA)
            _READY.add(key)
        return

    key = ("postgres", "primary")
    with _SETTLEMENT_LOCK:
        if key in _READY:
            return
        with runtime._postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_POSTGRES_SCHEMA)
        _READY.add(key)


def _settlement_id(
    parent_id: str,
    branch_key: str,
    event_seq: int,
    intent_source: str,
    action: str,
) -> str:
    raw = f"{parent_id}|{branch_key}|{event_seq}|{intent_source}|{action}"
    return "PSS:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _effective_mark(
    *,
    parent: dict[str, Any],
    remaining_quantity: float,
    realized_total: float,
    entry_fee_allocated: float,
    price: float,
) -> tuple[float, float, float]:
    notional = float(parent["initial_notional_usdt"])
    if remaining_quantity <= _EPS:
        pct = 100.0 * realized_total / notional if notional > 0 else 0.0
        return realized_total, pct, 0.0

    costs = _cost_model(parent)
    side = str(parent["side"]).upper()
    entry = float(parent["entry_price"])
    fill = _exit_fill(side, price, costs["slippage_bps"])
    exit_fee = remaining_quantity * fill * costs["fee_rate"]
    remaining_entry_fee = max(
        0.0,
        costs["entry_fee_total"] - entry_fee_allocated,
    )
    unrealized_component = (
        _gross_usdt(side, entry, fill, remaining_quantity)
        - remaining_entry_fee
        - exit_fee
    )
    total = realized_total + unrealized_component
    pct = 100.0 * total / notional if notional > 0 else 0.0
    return total, pct, unrealized_component


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    return _obj(event.get("payload_json"))


def _intent_candidates(
    *,
    branch_state: dict[str, Any],
    events: dict[int, dict[str, Any]],
    upto_event_seq: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in branch_state.get("intent_history") or []:
        if not isinstance(item, dict):
            continue
        seq = int(item.get("event_seq") or 0)
        action = str(item.get("action") or "").upper()
        if seq <= 0 or seq > upto_event_seq or action not in {"REDUCE", "CLOSE"}:
            continue
        event = events.get(seq)
        if event is None:
            continue
        candidates.append(
            {
                "event_seq": seq,
                "source_event_id": str(event["source_event_id"]),
                "event_time_ms": int(event["event_time_ms"]),
                "intent_source": "PROTECTION",
                "action": action,
                "reason": str(item.get("reason") or "protection_intent"),
                "fraction": float(item.get("fraction") or (1.0 if action == "CLOSE" else 0.0)),
                "event": event,
            }
        )

    for seq, event in events.items():
        if seq > upto_event_seq:
            continue
        event_type = str(event["event_type"]).upper()
        payload = _event_payload(event)
        if event_type == SOURCE_REDUCE_EVENT:
            fraction = float(payload.get("fraction") or 0.0)
            requested_quantity = float(payload.get("executed_quantity") or 0.0)
            if requested_quantity <= 0 and (fraction <= 0 or fraction > 1):
                raise ValueError(
                    "SOURCE_POSITION_REDUCE requires payload.executed_quantity > 0 "
                    "or payload.fraction in (0,1]"
                )
            candidates.append(
                {
                    "event_seq": seq,
                    "source_event_id": str(event["source_event_id"]),
                    "event_time_ms": int(event["event_time_ms"]),
                    "intent_source": "SOURCE_LIFECYCLE",
                    "action": "REDUCE",
                    "reason": str(payload.get("reason") or "source_position_reduce"),
                    "fraction": fraction,
                    "requested_quantity": requested_quantity if requested_quantity > 0 else None,
                    "payload": payload,
                    "event": event,
                }
            )
        elif event_type == SOURCE_CLOSE_EVENT:
            candidates.append(
                {
                    "event_seq": seq,
                    "source_event_id": str(event["source_event_id"]),
                    "event_time_ms": int(event["event_time_ms"]),
                    "intent_source": "SOURCE_LIFECYCLE",
                    "action": "CLOSE",
                    "reason": str(payload.get("reason") or "source_position_close"),
                    "fraction": 1.0,
                    "requested_quantity": None,
                    "payload": payload,
                    "event": event,
                }
            )

    candidates.sort(
        key=lambda x: (
            int(x["event_seq"]),
            0 if x["intent_source"] == "SOURCE_LIFECYCLE" else 1,
            str(x["action"]),
        )
    )
    return candidates


def _annotate_intents(
    state: dict[str, Any],
    settlements: list[dict[str, Any]],
) -> None:
    by_key = {
        (int(r["event_seq"]), str(r["action"]).upper(), str(r["intent_source"])): r
        for r in settlements
    }
    history = []
    for item in state.get("intent_history") or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        key = (int(row.get("event_seq") or 0), str(row.get("action") or "").upper(), "PROTECTION")
        settled = by_key.get(key)
        if settled:
            row["settlement_status"] = settled["status"]
            row["settlement_id"] = settled["settlement_id"]
            row["fill_price"] = settled.get("fill_price")
            row["executed_quantity"] = settled.get("executed_quantity")
            row["realized_delta_usdt"] = settled.get("realized_delta_usdt")
        history.append(row)
    state["intent_history"] = history

    current = state.get("virtual_intent")
    if isinstance(current, dict):
        row = dict(current)
        key = (int(row.get("event_seq") or 0), str(row.get("action") or "").upper(), "PROTECTION")
        settled = by_key.get(key)
        if settled:
            row["settlement_status"] = settled["status"]
            row["settlement_id"] = settled["settlement_id"]
            row["fill_price"] = settled.get("fill_price")
            row["executed_quantity"] = settled.get("executed_quantity")
            row["realized_delta_usdt"] = settled.get("realized_delta_usdt")
            row["settlement_authority"] = SETTLEMENT_VERSION
        state["virtual_intent"] = row


def _settle_branch(
    *,
    parent: dict[str, Any],
    branch: dict[str, Any],
    events: dict[int, dict[str, Any]],
    upto_event_seq: int,
    existing: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], float, str, str]:
    state = _obj(branch.get("state_json"))
    initial_qty = float(branch["initial_quantity"])
    notional = float(parent["initial_notional_usdt"])
    costs = _cost_model(parent)

    filled = [r for r in existing if r["status"] == "VIRTUAL_FILLED"]
    if filled:
        last_filled = sorted(filled, key=lambda r: (int(r["event_seq"]), r["settlement_id"]))[-1]
        remaining = float(last_filled["quantity_after"])
        realized_total = float(last_filled["realized_total_usdt"])
        entry_fee_allocated = sum(float(r["entry_fee_allocated_usdt"]) for r in filled)
        exit_fees_paid = sum(float(r["exit_fee_usdt"]) for r in filled)
    else:
        remaining = initial_qty
        realized_total = 0.0
        entry_fee_allocated = 0.0
        exit_fees_paid = 0.0

    existing_keys = {
        (
            int(r["event_seq"]),
            str(r["intent_source"]),
            str(r["action"]),
        )
        for r in existing
    }
    overlay_diverged = any(
        r["intent_source"] == "PROTECTION" and r["status"] == "VIRTUAL_FILLED"
        for r in existing
    )
    new_rows: list[dict[str, Any]] = []
    branch_closed_at: dict[str, Any] | None = None

    for candidate in _intent_candidates(
        branch_state=state,
        events=events,
        upto_event_seq=upto_event_seq,
    ):
        key = (
            int(candidate["event_seq"]),
            candidate["intent_source"],
            candidate["action"],
        )
        if key in existing_keys:
            continue

        event = candidate["event"]
        action = candidate["action"]
        intent_source = candidate["intent_source"]
        fraction = float(candidate["fraction"])
        quantity_before = remaining
        skipped = False

        if remaining <= _EPS:
            skipped = True
        elif (
            intent_source == "SOURCE_LIFECYCLE"
            and action == "REDUCE"
            and overlay_diverged
        ):
            # Mirrors historical overlay semantics: source partial actions after
            # the first protection divergence are not applied.
            skipped = True

        market_price = float(event["market_price"])
        fill_price = None
        executed_qty = 0.0
        entry_fee_piece = 0.0
        exit_fee = 0.0
        realized_delta = 0.0

        if not skipped:
            if action == "CLOSE":
                executed_qty = remaining
            else:
                requested_quantity = candidate.get("requested_quantity")
                if requested_quantity is not None:
                    executed_qty = min(remaining, float(requested_quantity))
                else:
                    executed_qty = min(remaining, remaining * fraction)

            if executed_qty <= _EPS:
                skipped = True
            else:
                payload = candidate.get("payload") or {}
                if (
                    intent_source == "SOURCE_LIFECYCLE"
                    and payload.get("fill_price") is not None
                ):
                    fill_price = float(payload["fill_price"])
                else:
                    fill_price = _exit_fill(
                        str(parent["side"]).upper(),
                        market_price,
                        costs["slippage_bps"],
                    )
                entry_fee_piece = (
                    costs["entry_fee_total"] * (executed_qty / initial_qty)
                    if initial_qty > 0
                    else 0.0
                )
                if (
                    intent_source == "SOURCE_LIFECYCLE"
                    and payload.get("fee") is not None
                    and not (action == "CLOSE" and overlay_diverged)
                ):
                    # Before protection divergence, source orders are mirrored
                    # exactly, including their executed fee. After divergence,
                    # the source final CLOSE contributes only its actual fill
                    # price; fee must be recomputed on the shadow remainder.
                    exit_fee = float(payload["fee"])
                else:
                    exit_fee = executed_qty * fill_price * costs["fee_rate"]
                realized_delta = (
                    _gross_usdt(
                        str(parent["side"]).upper(),
                        float(parent["entry_price"]),
                        fill_price,
                        executed_qty,
                    )
                    - entry_fee_piece
                    - exit_fee
                )
                remaining = max(0.0, remaining - executed_qty)
                if remaining <= _EPS:
                    remaining = 0.0
                realized_total += realized_delta
                entry_fee_allocated += entry_fee_piece
                exit_fees_paid += exit_fee
                if intent_source == "PROTECTION":
                    overlay_diverged = True

        settlement_id = _settlement_id(
            str(parent["parent_id"]),
            str(branch["branch_key"]),
            int(candidate["event_seq"]),
            intent_source,
            action,
        )
        row = {
            "settlement_id": settlement_id,
            "parent_id": parent["parent_id"],
            "branch_key": branch["branch_key"],
            "event_seq": int(candidate["event_seq"]),
            "source_event_id": candidate["source_event_id"],
            "event_time_ms": int(candidate["event_time_ms"]),
            "intent_source": intent_source,
            "action": action,
            "reason": candidate["reason"],
            "requested_fraction": fraction,
            "quantity_before": quantity_before,
            "executed_quantity": executed_qty,
            "quantity_after": remaining,
            "market_price": market_price,
            "fill_price": fill_price,
            "entry_fee_allocated_usdt": entry_fee_piece,
            "exit_fee_usdt": exit_fee,
            "realized_delta_usdt": realized_delta,
            "realized_total_usdt": realized_total,
            "status": "VIRTUAL_SKIPPED" if skipped else "VIRTUAL_FILLED",
            "settlement_version": SETTLEMENT_VERSION,
            "created_at_ms": int(time.time() * 1000),
        }
        new_rows.append(row)
        existing_keys.add(key)

        if not skipped and action == "CLOSE":
            branch_closed_at = row

    combined = sorted(
        existing + new_rows,
        key=lambda r: (int(r["event_seq"]), str(r["intent_source"]), str(r["action"])),
    )
    if branch_closed_at is None:
        filled_close = [
            r for r in combined
            if r["status"] == "VIRTUAL_FILLED" and r["action"] == "CLOSE"
        ]
        if filled_close:
            branch_closed_at = filled_close[-1]

    mark_event = events.get(upto_event_seq)
    if mark_event is None:
        raise KeyError(f"mark event not found: {parent['parent_id']}/{upto_event_seq}")
    current_total, current_pct, unrealized_component = _effective_mark(
        parent=parent,
        remaining_quantity=remaining,
        realized_total=realized_total,
        entry_fee_allocated=entry_fee_allocated,
        price=float(mark_event["market_price"]),
    )

    realized_pct = 100.0 * realized_total / notional if notional > 0 else 0.0
    state["settlement_version"] = SETTLEMENT_VERSION
    state["settled_through_event_seq"] = upto_event_seq
    state["settled_intent_count"] = sum(
        1 for r in combined if r["intent_source"] == "PROTECTION"
    )
    state["overlay_diverged"] = bool(overlay_diverged)
    state["realized_quantity"] = initial_qty - remaining
    state["realized_pnl_usdt"] = realized_total
    state["realized_pnl_pct"] = realized_pct
    state["unrealized_component_usdt"] = unrealized_component
    state["entry_fee_allocated_usdt"] = entry_fee_allocated
    state["exit_fees_paid_usdt"] = exit_fees_paid
    state["current_pnl_usdt"] = current_total
    state["current_pnl_pct"] = current_pct
    _annotate_intents(state, combined)

    if remaining <= _EPS:
        status = "CLOSED"
        current_state = "CLOSED"
        if branch_closed_at:
            state["closed_at_ms"] = int(branch_closed_at["event_time_ms"])
            state["close_price"] = branch_closed_at["fill_price"]
            state["close_reason"] = branch_closed_at["reason"]
            state["close_event_seq"] = int(branch_closed_at["event_seq"])
    else:
        status = "OPEN"
        state["closed_at_ms"] = None
        state["close_price"] = None
        state["close_reason"] = None
        state["close_event_seq"] = None
        if state.get("runner_mode"):
            current_state = "RUNNER_MONITORING"
        elif state.get("reduce_triggered") or (initial_qty - remaining) > _EPS:
            current_state = "REDUCED_MONITORING"
        elif state.get("be_armed"):
            current_state = "BE_ARMED"
        else:
            current_state = "MONITORING"

    return new_rows, state, remaining, status, current_state


def _insert_sqlite(conn: Any, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    conn.executemany(
        """insert or ignore into protection_shadow_settlements (
            settlement_id,parent_id,branch_key,event_seq,source_event_id,event_time_ms,
            intent_source,action,reason,requested_fraction,quantity_before,
            executed_quantity,quantity_after,market_price,fill_price,
            entry_fee_allocated_usdt,exit_fee_usdt,realized_delta_usdt,
            realized_total_usdt,status,settlement_version,created_at_ms
        ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                r["settlement_id"], r["parent_id"], r["branch_key"], r["event_seq"],
                r["source_event_id"], r["event_time_ms"], r["intent_source"], r["action"],
                r["reason"], r["requested_fraction"], r["quantity_before"],
                r["executed_quantity"], r["quantity_after"], r["market_price"],
                r["fill_price"], r["entry_fee_allocated_usdt"], r["exit_fee_usdt"],
                r["realized_delta_usdt"], r["realized_total_usdt"], r["status"],
                r["settlement_version"], r["created_at_ms"],
            )
            for r in rows
        ],
    )


def _insert_postgres(cur: Any, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    cur.executemany(
        """insert into protection_shadow_settlements (
            settlement_id,parent_id,branch_key,event_seq,source_event_id,event_time_ms,
            intent_source,action,reason,requested_fraction,quantity_before,
            executed_quantity,quantity_after,market_price,fill_price,
            entry_fee_allocated_usdt,exit_fee_usdt,realized_delta_usdt,
            realized_total_usdt,status,settlement_version,created_at_ms
        ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict(settlement_id) do nothing""",
        [
            (
                r["settlement_id"], r["parent_id"], r["branch_key"], r["event_seq"],
                r["source_event_id"], r["event_time_ms"], r["intent_source"], r["action"],
                r["reason"], r["requested_fraction"], r["quantity_before"],
                r["executed_quantity"], r["quantity_after"], r["market_price"],
                r["fill_price"], r["entry_fee_allocated_usdt"], r["exit_fee_usdt"],
                r["realized_delta_usdt"], r["realized_total_usdt"], r["status"],
                r["settlement_version"], r["created_at_ms"],
            )
            for r in rows
        ],
    )


def _settlement_event_seqs(
    branches: list[dict[str, Any]],
    upto_event_seq: int,
) -> list[int]:
    wanted = {int(upto_event_seq)}
    for branch in branches:
        state = _obj(branch.get("state_json"))
        for item in state.get("intent_history") or []:
            if not isinstance(item, dict):
                continue
            seq = int(item.get("event_seq") or 0)
            if 0 < seq <= int(upto_event_seq):
                wanted.add(seq)
    return sorted(wanted)


def _settle_sqlite(
    conn: Any,
    *,
    parent_id: str,
    upto_event_seq: int,
) -> dict[str, Any]:
    parent_row = conn.execute(
        "select * from protection_shadow_parents where parent_id=?",
        (parent_id,),
    ).fetchone()
    if parent_row is None:
        raise KeyError(f"shadow parent not found: {parent_id}")
    parent = dict(parent_row)

    branch_rows = [
        dict(r) for r in conn.execute(
            "select * from protection_shadow_branches where parent_id=?",
            (parent_id,),
        ).fetchall()
    ]
    needed_seqs = _settlement_event_seqs(branch_rows, upto_event_seq)
    marks = ",".join("?" for _ in needed_seqs)
    event_rows = conn.execute(
        f"""select * from protection_shadow_events
            where parent_id=?
              and event_seq<=?
              and (
                  event_seq in ({marks})
                  or event_type in (?,?)
              )
            order by event_seq""",
        (
            parent_id,
            upto_event_seq,
            *needed_seqs,
            SOURCE_REDUCE_EVENT,
            SOURCE_CLOSE_EVENT,
        ),
    ).fetchall()
    events = {int(r["event_seq"]): dict(r) for r in event_rows}
    if upto_event_seq not in events:
        raise KeyError(f"canonical shadow event not found: {parent_id}/{upto_event_seq}")

    by_key = {r["branch_key"]: r for r in branch_rows}
    if set(by_key) != set(BRANCH_KEYS):
        raise RuntimeError("PS4 requires exact four-branch set")

    now_ms = int(time.time() * 1000)
    results = {}
    for key in BRANCH_KEYS:
        existing = [
            dict(r) for r in conn.execute(
                """select * from protection_shadow_settlements
                   where parent_id=? and branch_key=? order by event_seq,intent_source,action""",
                (parent_id, key),
            ).fetchall()
        ]
        new_rows, state, remaining, status, current_state = _settle_branch(
            parent=parent,
            branch=by_key[key],
            events=events,
            upto_event_seq=upto_event_seq,
            existing=existing,
        )
        _insert_sqlite(conn, new_rows)
        conn.execute(
            """update protection_shadow_branches
               set status=?,remaining_quantity=?,current_state=?,state_json=?,updated_at_ms=?
               where parent_id=? and branch_key=?""",
            (
                status, remaining, current_state, _canonical_json(state), now_ms,
                parent_id, key,
            ),
        )
        results[key] = {
            "status": status,
            "current_state": current_state,
            "remaining_quantity": remaining,
            "new_settlements": len(new_rows),
            "current_pnl_usdt": state["current_pnl_usdt"],
            "realized_pnl_usdt": state["realized_pnl_usdt"],
            "close_reason": state.get("close_reason"),
        }

    return {
        "status": "SETTLEMENT_OK",
        "parent_id": parent_id,
        "upto_event_seq": upto_event_seq,
        "execution_authority": EXECUTION_AUTHORITY,
        "settlement_version": SETTLEMENT_VERSION,
        "branches": results,
    }


def _settle_postgres(
    conn: Any,
    *,
    parent_id: str,
    upto_event_seq: int,
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
        branch_rows = [dict(r) for r in cur.fetchall()]
        needed_seqs = _settlement_event_seqs(branch_rows, upto_event_seq)
        marks = ",".join("%s" for _ in needed_seqs)
        cur.execute(
            f"""select * from protection_shadow_events
                where parent_id=%s
                  and event_seq<=%s
                  and (
                      event_seq in ({marks})
                      or event_type in (%s,%s)
                  )
                order by event_seq""",
            (
                parent_id,
                upto_event_seq,
                *needed_seqs,
                SOURCE_REDUCE_EVENT,
                SOURCE_CLOSE_EVENT,
            ),
        )
        events = {int(r["event_seq"]): dict(r) for r in cur.fetchall()}
        if upto_event_seq not in events:
            raise KeyError(f"canonical shadow event not found: {parent_id}/{upto_event_seq}")
        by_key = {r["branch_key"]: r for r in branch_rows}
        if set(by_key) != set(BRANCH_KEYS):
            raise RuntimeError("PS4 requires exact four-branch set")

        now_ms = int(time.time() * 1000)
        results = {}
        for key in BRANCH_KEYS:
            cur.execute(
                """select * from protection_shadow_settlements
                   where parent_id=%s and branch_key=%s
                   order by event_seq,intent_source,action""",
                (parent_id, key),
            )
            existing = [dict(r) for r in cur.fetchall()]
            new_rows, state, remaining, status, current_state = _settle_branch(
                parent=parent,
                branch=by_key[key],
                events=events,
                upto_event_seq=upto_event_seq,
                existing=existing,
            )
            _insert_postgres(cur, new_rows)
            cur.execute(
                """update protection_shadow_branches
                   set status=%s,remaining_quantity=%s,current_state=%s,state_json=%s,updated_at_ms=%s
                   where parent_id=%s and branch_key=%s""",
                (
                    status, remaining, current_state, _canonical_json(state), now_ms,
                    parent_id, key,
                ),
            )
            results[key] = {
                "status": status,
                "current_state": current_state,
                "remaining_quantity": remaining,
                "new_settlements": len(new_rows),
                "current_pnl_usdt": state["current_pnl_usdt"],
                "realized_pnl_usdt": state["realized_pnl_usdt"],
                "close_reason": state.get("close_reason"),
            }

        return {
            "status": "SETTLEMENT_OK",
            "parent_id": parent_id,
            "upto_event_seq": upto_event_seq,
            "execution_authority": EXECUTION_AUTHORITY,
            "settlement_version": SETTLEMENT_VERSION,
            "branches": results,
        }


def settle_shadow_parent(
    parent_id: str,
    *,
    upto_event_seq: int | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Settle all branch intents/source lifecycle events through one canonical seq."""
    initialize_shadow_settlement_store(path)
    parent_id = str(parent_id).strip()
    if not parent_id:
        raise ValueError("parent_id is required")

    parity = audit_shadow_parity(parent_id, path=path)
    if not parity["comparison_eligible"]:
        return {
            "status": "SETTLEMENT_BLOCKED",
            "reason": "PARITY_ERROR",
            "parent_id": parent_id,
            "execution_authority": EXECUTION_AUTHORITY,
            "issue_types": parity["issue_types"],
        }

    def latest_sqlite(conn: Any) -> int:
        row = conn.execute(
            "select max(event_seq) from protection_shadow_events where parent_id=?",
            (parent_id,),
        ).fetchone()
        return int((row[0] if row else 0) or 0)

    with _SETTLEMENT_LOCK:
        if path is not None:
            with _local_sqlite_connect(path) as conn:
                target = int(upto_event_seq or latest_sqlite(conn))
                if target <= 0:
                    return {"status": "NO_EVENTS", "parent_id": parent_id}
                with conn:
                    return _settle_sqlite(conn, parent_id=parent_id, upto_event_seq=target)

        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                target = int(upto_event_seq or latest_sqlite(conn))
                if target <= 0:
                    return {"status": "NO_EVENTS", "parent_id": parent_id}
                with conn:
                    return _settle_sqlite(conn, parent_id=parent_id, upto_event_seq=target)

        with runtime._postgres_connect() as conn:
            if upto_event_seq is None:
                with conn.cursor() as cur:
                    cur.execute(
                        "select max(event_seq) from protection_shadow_events where parent_id=%s",
                        (parent_id,),
                    )
                    target = int((cur.fetchone()[0] or 0))
            else:
                target = int(upto_event_seq)
            if target <= 0:
                return {"status": "NO_EVENTS", "parent_id": parent_id}
            return _settle_postgres(conn, parent_id=parent_id, upto_event_seq=target)


def list_shadow_settlements(
    parent_id: str,
    *,
    branch_key: str | None = None,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    initialize_shadow_settlement_store(path)
    if branch_key is not None and branch_key not in BRANCH_KEYS:
        raise ValueError(f"unknown branch_key: {branch_key}")

    if branch_key:
        sql = """select * from protection_shadow_settlements
                 where parent_id=? and branch_key=?
                 order by event_seq,branch_key,intent_source,action"""
        params = (parent_id, branch_key)
    else:
        sql = """select * from protection_shadow_settlements
                 where parent_id=?
                 order by event_seq,branch_key,intent_source,action"""
        params = (parent_id,)

    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
    with runtime._postgres_connect() as conn:
        with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql.replace("?", "%s"), params)
            return [dict(r) for r in cur.fetchall()]


def process_shadow_event_with_settlement(
    parent_id: str,
    event_seq: int,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Preferred PS-4 orchestration: decision first, then virtual settlement."""
    from .parallel_protection_shadow_adapters import process_shadow_event

    decision = process_shadow_event(
        parent_id=parent_id,
        event_seq=event_seq,
        path=path,
    )
    if decision["status"] == "ADAPTER_ERROR":
        return {
            "status": "ERROR",
            "decision": decision,
            "settlement": None,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    # Normal market events do not need a settlement scan. Settlement is only
    # required when a new protection intent was emitted at this event or when
    # the source lifecycle itself changed quantity/status.
    needs_settlement = decision["status"] == "ALREADY_PROCESSED"
    if decision["status"] == "ADAPTER_OK":
        event_type = str(decision.get("event_type") or "").upper()
        needs_settlement = event_type in {SOURCE_REDUCE_EVENT, SOURCE_CLOSE_EVENT}
        if not needs_settlement:
            needs_settlement = any(
                item.get("intent_event_seq") == int(event_seq)
                for item in (decision.get("branches") or {}).values()
            )

    if not needs_settlement:
        return {
            "status": "COMPLETE",
            "decision": decision,
            "settlement": {
                "status": "NO_ACTION_REQUIRED",
                "parent_id": parent_id,
                "upto_event_seq": int(event_seq),
                "execution_authority": EXECUTION_AUTHORITY,
            },
            "execution_authority": EXECUTION_AUTHORITY,
        }

    settlement = settle_shadow_parent(
        parent_id,
        upto_event_seq=event_seq,
        path=path,
    )
    return {
        "status": (
            "COMPLETE"
            if settlement["status"] in {"SETTLEMENT_OK", "NO_EVENTS"}
            else "ERROR"
        ),
        "decision": decision,
        "settlement": settlement,
        "execution_authority": EXECUTION_AUTHORITY,
    }


def process_pending_with_settlement(
    parent_id: str,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Catch adapters up once, then settle all persisted intent history once."""
    initialize_shadow_settlement_store(path)
    from .parallel_protection_shadow_adapters import process_pending_shadow_events

    decision = process_pending_shadow_events(parent_id, path=path)
    if decision["status"] == "ERROR":
        return {
            "status": "ERROR",
            "parent_id": parent_id,
            "decision": decision,
            "settlement": None,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    if path is not None:
        with _local_sqlite_connect(path) as conn:
            row = conn.execute(
                "select max(event_seq) from protection_shadow_events where parent_id=?",
                (parent_id,),
            ).fetchone()
            max_seq = int((row[0] if row else 0) or 0)
    else:
        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                row = conn.execute(
                    "select max(event_seq) from protection_shadow_events where parent_id=?",
                    (parent_id,),
                ).fetchone()
                max_seq = int((row[0] if row else 0) or 0)
        else:
            with runtime._postgres_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "select max(event_seq) from protection_shadow_events where parent_id=%s",
                        (parent_id,),
                    )
                    max_seq = int((cur.fetchone()[0] or 0))

    settlement = (
        settle_shadow_parent(parent_id, upto_event_seq=max_seq, path=path)
        if max_seq > 0
        else {"status": "NO_EVENTS", "parent_id": parent_id}
    )
    ok = settlement["status"] in {"SETTLEMENT_OK", "NO_EVENTS"}
    return {
        "status": "COMPLETE" if ok else "ERROR",
        "parent_id": parent_id,
        "canonical_event_count": max_seq,
        "adapter_processed_n": decision.get("processed_n", 0),
        "decision": decision,
        "settlement": settlement,
        "execution_authority": EXECUTION_AUTHORITY,
    }


def settlement_contract() -> dict[str, Any]:
    return {
        "settlement_version": SETTLEMENT_VERSION,
        "execution_authority": EXECUTION_AUTHORITY,
        "protection_intents": ["REDUCE", "CLOSE"],
        "source_lifecycle_events": [SOURCE_REDUCE_EVENT, SOURCE_CLOSE_EVENT],
        "source_reduce_rule": "mirror only before first protection divergence",
        "source_close_rule": "close any remaining virtual quantity",
        "fill_model": "side-aware slippage then exit fee",
        "entry_fee_allocation": "pro-rata by settled quantity",
        "branch_isolation": True,
        "source_position_mutation": False,
        "parent_auto_close": False,
    }
