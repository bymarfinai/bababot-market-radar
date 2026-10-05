from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .parallel_protection_shadow import (
    BRANCH_KEYS,
    BRANCH_SPECS,
    EXECUTION_AUTHORITY,
    PARALLEL_SHADOW_EVENT_VERSION,
    _local_sqlite_connect,
    _runtime_persistence,
    audit_shadow_parity,
    initialize_parallel_shadow_store,
)

UI_CONTRACT_VERSION = "ps2.5-v1-shadow-ui-contract"
BASELINE_BRANCH_KEY = "V42_BASELINE"

BRANCH_UI = {
    "V42_BASELINE": {
        "label": "V4.2 Baseline",
        "short_label": "V4.2",
        "rank": 1,
        "category": "BASELINE",
    },
    "V43_LS": {
        "label": "V4.3-LS",
        "short_label": "V4.3",
        "rank": 2,
        "category": "CHALLENGER",
    },
    "BE025_CONSERVATIVE": {
        "label": "BE 0.25 Conservative",
        "short_label": "BE0.25",
        "rank": 3,
        "category": "CONSERVATIVE",
    },
    "BE018_AGGRESSIVE": {
        "label": "BE 0.18 Aggressive",
        "short_label": "BE0.18",
        "rank": 4,
        "category": "AGGRESSIVE",
    },
}


def _json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _gross_move_pct(side: str, entry: float, price: float | None) -> float | None:
    if price is None or entry <= 0:
        return None
    if side == "LONG":
        return 100.0 * (price - entry) / entry
    return 100.0 * (entry - price) / entry


def _gross_pnl_usdt(
    side: str,
    entry: float,
    price: float | None,
    quantity: float,
) -> float | None:
    if price is None:
        return None
    if side == "LONG":
        return (price - entry) * quantity
    return (entry - price) * quantity


def contract_definition() -> dict[str, Any]:
    return {
        "contract_version": UI_CONTRACT_VERSION,
        "execution_authority": EXECUTION_AUTHORITY,
        "baseline_branch_key": BASELINE_BRANCH_KEY,
        "branch_order": list(BRANCH_KEYS),
        "branches": [
            {
                "branch_key": spec.branch_key,
                **BRANCH_UI[spec.branch_key],
                "protection_family": spec.protection_family,
                "protector_config": {
                    "no_action_be_arm_pct": spec.no_action_be_arm_pct,
                    "reduce25_logic": spec.reduce25_logic,
                    "runner_logic": spec.runner_logic,
                },
            }
            for spec in BRANCH_SPECS
        ],
        "position_shape": {
            "parent": "immutable source trade identity",
            "market": "shared canonical event observation; not protector PnL",
            "parity": "event-stream integrity and comparison eligibility",
            "comparison": "baseline/best-branch fields; nullable until branch PnL exists",
            "branches": "four ordered independent protection snapshots",
        },
        "nullable_until_ps3_ps4": [
            "branch.performance.current_pnl_usdt",
            "branch.performance.current_pnl_pct",
            "branch.performance.realized_pnl_usdt",
            "branch.performance.realized_pnl_pct",
            "branch.performance.delta_vs_v42_usdt",
            "branch.settlement.closed_at_ms",
            "branch.settlement.close_price",
            "branch.settlement.close_reason",
            "comparison.current_best_branch_key",
            "comparison.current_best_delta_vs_v42_usdt",
        ],
    }


def _query_rows(
    *,
    limit: int,
    status: str | None,
    symbol: str | None,
    side: str | None,
    path: str | Path | None,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, dict[str, Any] | None]]:
    clauses = []
    values: list[Any] = []
    if status:
        clauses.append("status=?")
        values.append(status)
    if symbol:
        clauses.append("symbol=?")
        values.append(symbol)
    if side:
        clauses.append("side=?")
        values.append(side)
    where = (" where " + " and ".join(clauses)) if clauses else ""
    sql = (
        "select * from protection_shadow_parents"
        + where
        + " order by opened_at_ms desc, parent_id desc limit ?"
    )
    values.append(limit)

    def fetch(conn: Any):
        parents = [dict(r) for r in conn.execute(sql, values).fetchall()]
        parent_ids = [r["parent_id"] for r in parents]
        branches: dict[str, list[dict[str, Any]]] = {pid: [] for pid in parent_ids}
        latest: dict[str, dict[str, Any] | None] = {pid: None for pid in parent_ids}
        if not parent_ids:
            return parents, branches, latest
        marks = ",".join("?" for _ in parent_ids)
        branch_rows = conn.execute(
            f"""select * from protection_shadow_branches
                where parent_id in ({marks})""",
            parent_ids,
        ).fetchall()
        for row in branch_rows:
            d = dict(row)
            branches[d["parent_id"]].append(d)
        event_rows = conn.execute(
            f"""select e.* from protection_shadow_events e
                join (
                    select parent_id,max(event_seq) as max_seq
                    from protection_shadow_events
                    where parent_id in ({marks})
                    group by parent_id
                ) x on x.parent_id=e.parent_id and x.max_seq=e.event_seq""",
            parent_ids,
        ).fetchall()
        for row in event_rows:
            d = dict(row)
            latest[d["parent_id"]] = d
        return parents, branches, latest

    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return fetch(conn)

    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            return fetch(conn)

    # PostgreSQL uses the same conceptual queries with parameter substitution.
    with runtime._postgres_connect() as conn:
        with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
            pg_where = where.replace("?", "%s")
            cur.execute(
                "select * from protection_shadow_parents"
                + pg_where
                + " order by opened_at_ms desc, parent_id desc limit %s",
                values,
            )
            parents = [dict(r) for r in cur.fetchall()]
            parent_ids = [r["parent_id"] for r in parents]
            branches = {pid: [] for pid in parent_ids}
            latest = {pid: None for pid in parent_ids}
            if not parent_ids:
                return parents, branches, latest
            cur.execute(
                """select * from protection_shadow_branches
                   where parent_id = any(%s)""",
                (parent_ids,),
            )
            for row in cur.fetchall():
                d = dict(row)
                branches[d["parent_id"]].append(d)
            cur.execute(
                """select distinct on (parent_id) *
                   from protection_shadow_events
                   where parent_id = any(%s)
                   order by parent_id,event_seq desc""",
                (parent_ids,),
            )
            for row in cur.fetchall():
                d = dict(row)
                latest[d["parent_id"]] = d
            return parents, branches, latest


def _branch_snapshot(
    parent: dict[str, Any],
    branch: dict[str, Any],
    latest_event: dict[str, Any] | None,
) -> dict[str, Any]:
    branch_key = branch["branch_key"]
    spec = next(x for x in BRANCH_SPECS if x.branch_key == branch_key)
    state = _json_object(branch.get("state_json"))
    current_price = (
        float(latest_event["market_price"])
        if latest_event and latest_event.get("market_price") is not None
        else None
    )

    # Reserved performance keys may be written by PS-3/PS-4 later.
    current_pnl_usdt = state.get("current_pnl_usdt")
    current_pnl_pct = state.get("current_pnl_pct")
    realized_pnl_usdt = state.get("realized_pnl_usdt")
    realized_pnl_pct = state.get("realized_pnl_pct")
    delta_vs_v42_usdt = state.get("delta_vs_v42_usdt")

    return {
        "branch_key": branch_key,
        **BRANCH_UI[branch_key],
        "role": branch["role"],
        "protection_family": branch["protection_family"],
        "status": branch["status"],
        "current_state": branch["current_state"],
        "execution_authority": branch["execution_authority"],
        "protector_config": {
            "no_action_be_arm_pct": spec.no_action_be_arm_pct,
            "reduce25_logic": spec.reduce25_logic,
            "runner_logic": spec.runner_logic,
        },
        "telemetry": {
            "last_event_id": branch.get("last_event_id"),
            "last_event_time_ms": branch.get("last_event_time_ms"),
            "last_event_seq": int(latest_event["event_seq"]) if latest_event else None,
            "mfe_pct": branch.get("mfe_pct"),
            "mae_pct": branch.get("mae_pct"),
            "remaining_quantity": branch.get("remaining_quantity"),
        },
        "decision": {
            "lane": state.get("lane"),
            "action": state.get("action"),
            "reason": state.get("reason"),
            "be_armed": state.get("be_armed"),
            "runner_qualified": state.get("runner_qualified"),
            "reduce_triggered": state.get("reduce_triggered"),
        },
        "performance": {
            "available": any(
                x is not None
                for x in (
                    current_pnl_usdt,
                    current_pnl_pct,
                    realized_pnl_usdt,
                    realized_pnl_pct,
                )
            ),
            "current_pnl_usdt": current_pnl_usdt,
            "current_pnl_pct": current_pnl_pct,
            "realized_pnl_usdt": realized_pnl_usdt,
            "realized_pnl_pct": realized_pnl_pct,
            "delta_vs_v42_usdt": delta_vs_v42_usdt,
        },
        "settlement": {
            "closed_at_ms": state.get("closed_at_ms"),
            "close_price": state.get("close_price"),
            "close_reason": state.get("close_reason"),
        },
    }


def protection_shadow_snapshot(
    *,
    limit: int = 100,
    status: str | None = None,
    symbol: str | None = None,
    side: str | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    initialize_parallel_shadow_store(path)
    safe_limit = max(1, min(int(limit), 500))
    normalized_status = status.upper().strip() if status else None
    normalized_symbol = symbol.upper().strip() if symbol else None
    normalized_side = side.upper().strip() if side else None
    if normalized_status and normalized_status not in {"OPEN", "ARCHIVED"}:
        raise ValueError("status must be OPEN or ARCHIVED")
    if normalized_side and normalized_side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")

    parents, branches_by_parent, latest_by_parent = _query_rows(
        limit=safe_limit,
        status=normalized_status,
        symbol=normalized_symbol,
        side=normalized_side,
        path=path,
    )

    positions = []
    for parent in parents:
        pid = parent["parent_id"]
        parity = audit_shadow_parity(pid, path=path)
        latest_event = latest_by_parent[pid]
        branch_rows = {
            row["branch_key"]: row
            for row in branches_by_parent[pid]
            if row["branch_key"] in BRANCH_UI
        }
        ordered = [
            _branch_snapshot(parent, branch_rows[key], latest_event)
            for key in BRANCH_KEYS
            if key in branch_rows
        ]
        branch_complete = len(ordered) == len(BRANCH_KEYS)
        if not branch_complete:
            parity = {
                **parity,
                "status": "PARITY_ERROR",
                "comparison_eligible": False,
                "issue_types": sorted(set(parity["issue_types"] + ["BRANCH_SET_INCOMPLETE_UI"])),
            }

        current_price = (
            float(latest_event["market_price"])
            if latest_event and latest_event.get("market_price") is not None
            else None
        )
        entry = float(parent["entry_price"])
        quantity = float(parent["initial_quantity"])
        gross_move = _gross_move_pct(parent["side"], entry, current_price)

        baseline = next((b for b in ordered if b["branch_key"] == BASELINE_BRANCH_KEY), None)
        performance_ready = bool(
            branch_complete
            and all(b["performance"]["available"] for b in ordered)
        )
        best_branch = None
        best_delta = None
        if performance_ready:
            def effective_pnl(branch: dict[str, Any]) -> float | None:
                if str(branch.get("status") or "").upper() == "CLOSED":
                    value = branch["performance"]["realized_pnl_usdt"]
                    if value is None:
                        value = branch["performance"]["current_pnl_usdt"]
                else:
                    value = branch["performance"]["current_pnl_usdt"]
                    if value is None:
                        value = branch["performance"]["realized_pnl_usdt"]
                return float(value) if value is not None else None

            baseline_value = effective_pnl(baseline) if baseline else None
            if baseline_value is not None:
                for branch in ordered:
                    value = effective_pnl(branch)
                    branch["performance"]["delta_vs_v42_usdt"] = (
                        value - baseline_value if value is not None else None
                    )

            scored = [
                (effective_pnl(b), b)
                for b in ordered
                if effective_pnl(b) is not None
            ]
            if scored:
                scored.sort(key=lambda x: (x[0], -x[1]["rank"]), reverse=True)
                best_value, best = scored[0]
                best_branch = best["branch_key"]
                if baseline_value is not None:
                    best_delta = float(best_value) - baseline_value

        positions.append(
            {
                "parent": {
                    "parent_id": pid,
                    "source_position_id": parent["source_position_id"],
                    "signal_id": parent.get("signal_id"),
                    "symbol": parent["symbol"],
                    "side": parent["side"],
                    "status": parent["status"],
                    "opened_at_ms": int(parent["opened_at_ms"]),
                    "entry_price": entry,
                    "initial_quantity": quantity,
                    "initial_notional_usdt": float(parent["initial_notional_usdt"]),
                },
                "market": {
                    "event_version": PARALLEL_SHADOW_EVENT_VERSION,
                    "last_event_seq": int(latest_event["event_seq"]) if latest_event else None,
                    "last_event_id": latest_event["source_event_id"] if latest_event else None,
                    "last_event_time_ms": int(latest_event["event_time_ms"]) if latest_event else None,
                    "current_price": current_price,
                    "gross_move_pct": gross_move,
                    "gross_mark_pnl_usdt": _gross_pnl_usdt(
                        parent["side"], entry, current_price, quantity
                    ),
                    "note": "shared market observation; not protector performance",
                },
                "parity": {
                    "status": parity["status"],
                    "comparison_eligible": bool(parity["comparison_eligible"]),
                    "canonical_event_count": int(parity["canonical_event_count"]),
                    "issue_count": int(parity["issue_count"]),
                    "issue_types": list(parity["issue_types"]),
                    "branch_complete": branch_complete,
                },
                "comparison": {
                    "baseline_branch_key": BASELINE_BRANCH_KEY,
                    "performance_ready": performance_ready,
                    "current_best_branch_key": best_branch,
                    "current_best_delta_vs_v42_usdt": best_delta,
                },
                "branches": ordered,
            }
        )

    eligible = sum(p["parity"]["comparison_eligible"] for p in positions)
    return {
        "contract_version": UI_CONTRACT_VERSION,
        "generated_at_ms": int(time.time() * 1000),
        "execution_authority": EXECUTION_AUTHORITY,
        "baseline_branch_key": BASELINE_BRANCH_KEY,
        "branch_order": list(BRANCH_KEYS),
        "count": len(positions),
        "comparison_eligible_count": int(eligible),
        "comparison_ineligible_count": len(positions) - int(eligible),
        "filters": {
            "limit": safe_limit,
            "status": normalized_status,
            "symbol": normalized_symbol,
            "side": normalized_side,
        },
        "positions": positions,
    }
