from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .binance import BinancePublicClient
from .parallel_protection_shadow import (
    EXECUTION_AUTHORITY,
    archive_shadow_parent,
    create_shadow_parent,
    fanout_shadow_events_batch,
    get_shadow_event_by_source_id,
    get_shadow_parent,
    list_shadow_branches,
    record_shadow_integrity_issue,
    _canonical_json,
    _local_sqlite_connect,
    _runtime_persistence,
)
from .parallel_protection_shadow_adapters import process_shadow_events_through
from .parallel_protection_shadow_settlement import settle_shadow_parent

RUNTIME_VERSION = "ps5a-v1-prospective-runtime"
RUNTIME_ENV = "PROTECTION_SHADOW_RUNTIME_ENABLED"
START_ENV = "PROTECTION_SHADOW_START_MS"
MAX_RAW_SYMBOLS_ENV = "PROTECTION_SHADOW_MAX_RAW_SYMBOLS"
RAW_MAX_PAGES_ENV = "PROTECTION_SHADOW_RAW_MAX_PAGES"
PRODUCTION_COHORT = "STAGE3C7A_LONG"
RAW_PAGE_LIMIT = 1000
RAW_RETENTION_GUARD_MS = 47 * 60 * 60 * 1000

SQLITE_SCHEMA = """
create table if not exists protection_shadow_runtime_epochs (
    epoch_id text primary key,
    started_at_ms integer not null,
    status text not null check (status in ('ACTIVE','ARCHIVED')),
    runtime_version text not null,
    config_json text not null default '{}',
    created_at_ms integer not null
);
create index if not exists idx_shadow_runtime_epoch_status
on protection_shadow_runtime_epochs(status, started_at_ms desc);

create table if not exists protection_shadow_runtime_cursors (
    parent_id text primary key references protection_shadow_parents(parent_id) on delete cascade,
    epoch_id text not null,
    symbol text not null,
    raw_feed_state text not null,
    last_agg_trade_id integer,
    last_agg_trade_time_ms integer,
    last_raw_scan_ms integer,
    last_sample_time_ms integer,
    last_event_time_ms integer,
    source_closed_at_ms integer,
    error_count integer not null default 0,
    last_error text,
    updated_at_ms integer not null
);
create index if not exists idx_shadow_runtime_cursor_epoch
on protection_shadow_runtime_cursors(epoch_id, raw_feed_state, updated_at_ms);
"""

POSTGRES_SCHEMA = """
create table if not exists protection_shadow_runtime_epochs (
    epoch_id text primary key,
    started_at_ms bigint not null,
    status text not null check (status in ('ACTIVE','ARCHIVED')),
    runtime_version text not null,
    config_json text not null default '{}',
    created_at_ms bigint not null
);
create index if not exists idx_shadow_runtime_epoch_status
on protection_shadow_runtime_epochs(status, started_at_ms desc);

create table if not exists protection_shadow_runtime_cursors (
    parent_id text primary key references protection_shadow_parents(parent_id) on delete cascade,
    epoch_id text not null,
    symbol text not null,
    raw_feed_state text not null,
    last_agg_trade_id bigint,
    last_agg_trade_time_ms bigint,
    last_raw_scan_ms bigint,
    last_sample_time_ms bigint,
    last_event_time_ms bigint,
    source_closed_at_ms bigint,
    error_count integer not null default 0,
    last_error text,
    updated_at_ms bigint not null
);
create index if not exists idx_shadow_runtime_cursor_epoch
on protection_shadow_runtime_cursors(epoch_id, raw_feed_state, updated_at_ms);
"""

_INIT_LOCK = threading.Lock()
_RUNTIME_LOCK = threading.Lock()
_READY: set[tuple[str, str]] = set()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def runtime_enabled() -> bool:
    return _bool_env(RUNTIME_ENV, False)


def configured_start_ms() -> int:
    try:
        return int(os.environ.get(START_ENV, "0") or 0)
    except (TypeError, ValueError):
        return 0


def _int_env(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        return int(default)


def runtime_preflight() -> dict[str, Any]:
    """Fail-closed activation contract for the PT-L2 prospective cohort.

    Explicit start_ms calls used by offline/unit parity tests bypass this
    production preflight. The daemon path never does.
    """
    shadow_start = configured_start_ms()
    observer_enabled = _bool_env("PP_V4_STAGE1_ENABLED", False)
    observer_start = _int_env("PP_V4_STAGE1_START_MS", 0)
    paper_enabled = _bool_env("PAPER_TRADING_ENABLED", False)
    health_isolation_enabled = _bool_env(
        "PTL3_HEALTH_OBSERVER_ONLY_ENABLED", False
    )
    live_enabled = _bool_env("LIVE_TRADING_ENABLED", False)
    detector_policy = os.environ.get(
        "PAPER_LONG_DETECTOR_POLICY", "generic"
    ).strip().lower()

    reasons: list[str] = []
    if shadow_start <= 0:
        reasons.append("shadow_start_missing")
    if not observer_enabled:
        reasons.append("pp_v4_5s_observer_disabled")
    if observer_start <= 0:
        reasons.append("pp_v4_observer_start_missing")
    if shadow_start > 0 and observer_start > 0 and shadow_start != observer_start:
        reasons.append("observer_shadow_boundary_mismatch")
    if not paper_enabled:
        reasons.append("paper_trading_disabled")
    if detector_policy != "stage3c7a":
        reasons.append("paper_long_detector_not_stage3c7a")
    if not health_isolation_enabled:
        reasons.append("ptl3_health_isolation_disabled")
    if live_enabled:
        reasons.append("live_trading_must_remain_disabled")

    return {
        "ready": not reasons,
        "reasons": reasons,
        "production_cohort": PRODUCTION_COHORT,
        "shadow_runtime_enabled": runtime_enabled(),
        "shadow_start_ms": shadow_start,
        "pp_v4_observer_enabled": observer_enabled,
        "pp_v4_observer_start_ms": observer_start,
        "paper_trading_enabled": paper_enabled,
        "paper_long_detector_policy": detector_policy,
        "ptl3_health_observer_only_enabled": health_isolation_enabled,
        "live_trading_enabled": live_enabled,
        "execution_authority": EXECUTION_AUTHORITY,
    }


def _production_cohort_eligibility(
    position: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    metadata = _metadata(position)
    side = str(position.get("side") or "").upper()
    policy = str(metadata.get("paper_entry_policy") or "").lower()
    eligible = side == "LONG" and policy == "stage3c7a"
    return eligible, {
        "production_cohort": PRODUCTION_COHORT,
        "side": side,
        "paper_entry_policy": policy or None,
        "eligible": eligible,
    }


def max_raw_symbols() -> int:
    try:
        value = int(os.environ.get(MAX_RAW_SYMBOLS_ENV, "6") or 6)
    except (TypeError, ValueError):
        value = 6
    return max(1, min(value, 10))


def raw_max_pages() -> int:
    try:
        value = int(os.environ.get(RAW_MAX_PAGES_ENV, "5") or 5)
    except (TypeError, ValueError):
        value = 5
    return max(1, min(value, 20))


def initialize_shadow_runtime_store(path: str | Path | None = None) -> None:
    from .parallel_protection_shadow import initialize_parallel_shadow_store

    initialize_parallel_shadow_store(path)
    if path is not None:
        key = ("sqlite", str(Path(path).resolve()))
        with _INIT_LOCK:
            if key in _READY:
                return
            with _local_sqlite_connect(path) as conn:
                conn.executescript(SQLITE_SCHEMA)
            _READY.add(key)
        return

    p = _runtime_persistence()
    if p.persistence_backend() == "sqlite":
        key = ("sqlite", str(p.database_path().resolve()))
        with _INIT_LOCK:
            if key in _READY:
                return
            with p._sqlite_connect(p.database_path()) as conn:
                conn.executescript(SQLITE_SCHEMA)
            _READY.add(key)
        return

    key = ("postgres", "primary")
    with _INIT_LOCK:
        if key in _READY:
            return
        with p._postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(POSTGRES_SCHEMA)
        _READY.add(key)


def _metadata(position: dict[str, Any]) -> dict[str, Any]:
    raw = position.get("raw_json")
    if isinstance(raw, dict):
        return dict(raw)
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _epoch_id(started_at_ms: int) -> str:
    return f"PS5A:{int(started_at_ms)}"


def _active_epoch(path: str | Path | None = None) -> dict[str, Any] | None:
    initialize_shadow_runtime_store(path)
    query = """select * from protection_shadow_runtime_epochs
               where status='ACTIVE'
               order by started_at_ms desc"""
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            rows = [dict(r) for r in conn.execute(query).fetchall()]
    else:
        p = _runtime_persistence()
        if p.persistence_backend() == "sqlite":
            with p._sqlite_connect(p.database_path()) as conn:
                rows = [dict(r) for r in conn.execute(query).fetchall()]
        else:
            with p._postgres_connect() as conn:
                with conn.cursor(cursor_factory=p.psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query)
                    rows = [dict(r) for r in cur.fetchall()]
    if len(rows) > 1:
        raise RuntimeError("multiple ACTIVE protection shadow runtime epochs")
    return rows[0] if rows else None


def ensure_runtime_epoch(
    *,
    start_ms: int | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    if start_ms is None:
        if not runtime_enabled():
            return {
                "status": "DISABLED",
                "runtime_version": RUNTIME_VERSION,
                "execution_authority": EXECUTION_AUTHORITY,
            }
        preflight = runtime_preflight()
        if not preflight["ready"]:
            return {
                "status": "CONFIG_BLOCKED",
                "preflight": preflight,
                "runtime_version": RUNTIME_VERSION,
                "execution_authority": EXECUTION_AUTHORITY,
            }
    initialize_shadow_runtime_store(path)
    boundary = int(configured_start_ms() if start_ms is None else start_ms)
    if boundary <= 0:
        return {
            "status": "WAITING_FOR_START_BOUNDARY",
            "runtime_version": RUNTIME_VERSION,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    existing = _active_epoch(path)
    if existing is not None:
        if int(existing["started_at_ms"]) != boundary:
            return {
                "status": "BOUNDARY_CONFLICT",
                "epoch_id": existing["epoch_id"],
                "active_started_at_ms": int(existing["started_at_ms"]),
                "configured_started_at_ms": boundary,
                "runtime_version": RUNTIME_VERSION,
                "execution_authority": EXECUTION_AUTHORITY,
            }
        return {
            "status": "ACTIVE",
            **existing,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    epoch_id = _epoch_id(boundary)
    now_ms = int(time.time() * 1000)
    config = {
        "max_raw_symbols": max_raw_symbols(),
        "raw_max_pages": raw_max_pages(),
        "raw_page_limit": RAW_PAGE_LIMIT,
        "source_mode": "PAPER",
        "runtime_version": RUNTIME_VERSION,
    }
    values = (
        epoch_id,
        boundary,
        "ACTIVE",
        RUNTIME_VERSION,
        _canonical_json(config),
        now_ms,
    )
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            conn.execute(
                """insert or ignore into protection_shadow_runtime_epochs (
                    epoch_id,started_at_ms,status,runtime_version,config_json,created_at_ms
                ) values (?,?,?,?,?,?)""",
                values,
            )
    else:
        p = _runtime_persistence()
        if p.persistence_backend() == "sqlite":
            with p._sqlite_connect(p.database_path()) as conn:
                conn.execute(
                    """insert or ignore into protection_shadow_runtime_epochs (
                        epoch_id,started_at_ms,status,runtime_version,config_json,created_at_ms
                    ) values (?,?,?,?,?,?)""",
                    values,
                )
        else:
            with p._postgres_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """insert into protection_shadow_runtime_epochs (
                            epoch_id,started_at_ms,status,runtime_version,config_json,created_at_ms
                        ) values (%s,%s,%s,%s,%s,%s)
                        on conflict(epoch_id) do nothing""",
                        values,
                    )
    row = _active_epoch(path)
    if row is None:
        raise RuntimeError("failed to create protection shadow runtime epoch")
    return {
        "status": "ACTIVE",
        **row,
        "execution_authority": EXECUTION_AUTHORITY,
    }


def _cursor(parent_id: str, path: str | Path | None = None) -> dict[str, Any] | None:
    initialize_shadow_runtime_store(path)
    query = "select * from protection_shadow_runtime_cursors where parent_id=?"
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            row = conn.execute(query, (parent_id,)).fetchone()
            return dict(row) if row else None
    p = _runtime_persistence()
    if p.persistence_backend() == "sqlite":
        with p._sqlite_connect(p.database_path()) as conn:
            row = conn.execute(query, (parent_id,)).fetchone()
            return dict(row) if row else None
    with p._postgres_connect() as conn:
        with conn.cursor(cursor_factory=p.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), (parent_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def _active_raw_count(epoch_id: str, path: str | Path | None = None) -> int:
    query = """select count(*) from protection_shadow_runtime_cursors
               where epoch_id=? and raw_feed_state='ACTIVE'
                 and source_closed_at_ms is null"""
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return int(conn.execute(query, (epoch_id,)).fetchone()[0])
    p = _runtime_persistence()
    if p.persistence_backend() == "sqlite":
        with p._sqlite_connect(p.database_path()) as conn:
            return int(conn.execute(query, (epoch_id,)).fetchone()[0])
    with p._postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query.replace("?", "%s"), (epoch_id,))
            return int(cur.fetchone()[0])


def _insert_cursor(
    *,
    parent_id: str,
    epoch_id: str,
    symbol: str,
    opened_at_ms: int,
    raw_feed_state: str,
    path: str | Path | None = None,
) -> None:
    now_ms = int(time.time() * 1000)
    values = (
        parent_id,
        epoch_id,
        symbol.upper(),
        raw_feed_state,
        None,
        None,
        max(0, int(opened_at_ms) - 1),
        None,
        int(opened_at_ms),
        None,
        0,
        None,
        now_ms,
    )
    sql_sqlite = """insert or ignore into protection_shadow_runtime_cursors (
        parent_id,epoch_id,symbol,raw_feed_state,last_agg_trade_id,
        last_agg_trade_time_ms,last_raw_scan_ms,last_sample_time_ms,
        last_event_time_ms,source_closed_at_ms,error_count,last_error,updated_at_ms
    ) values (?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            conn.execute(sql_sqlite, values)
        return
    p = _runtime_persistence()
    if p.persistence_backend() == "sqlite":
        with p._sqlite_connect(p.database_path()) as conn:
            conn.execute(sql_sqlite, values)
        return
    with p._postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """insert into protection_shadow_runtime_cursors (
                    parent_id,epoch_id,symbol,raw_feed_state,last_agg_trade_id,
                    last_agg_trade_time_ms,last_raw_scan_ms,last_sample_time_ms,
                    last_event_time_ms,source_closed_at_ms,error_count,last_error,updated_at_ms
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(parent_id) do nothing""",
                values,
            )


def _update_cursor(
    parent_id: str,
    *,
    path: str | Path | None = None,
    **fields: Any,
) -> None:
    allowed = {
        "raw_feed_state",
        "last_agg_trade_id",
        "last_agg_trade_time_ms",
        "last_raw_scan_ms",
        "last_sample_time_ms",
        "last_event_time_ms",
        "source_closed_at_ms",
        "error_count",
        "last_error",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at_ms"] = int(time.time() * 1000)
    columns = list(updates)
    if path is not None:
        sql = "update protection_shadow_runtime_cursors set " + ",".join(
            f"{c}=?" for c in columns
        ) + " where parent_id=?"
        with _local_sqlite_connect(path) as conn:
            conn.execute(sql, tuple(updates[c] for c in columns) + (parent_id,))
        return
    p = _runtime_persistence()
    if p.persistence_backend() == "sqlite":
        sql = "update protection_shadow_runtime_cursors set " + ",".join(
            f"{c}=?" for c in columns
        ) + " where parent_id=?"
        with p._sqlite_connect(p.database_path()) as conn:
            conn.execute(sql, tuple(updates[c] for c in columns) + (parent_id,))
        return
    sql = "update protection_shadow_runtime_cursors set " + ",".join(
        f"{c}=%s" for c in columns
    ) + " where parent_id=%s"
    with p._postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(updates[c] for c in columns) + (parent_id,))


def _mark_feed_error(
    parent_id: str,
    issue_type: str,
    details: dict[str, Any],
    *,
    path: str | Path | None = None,
) -> None:
    cursor = _cursor(parent_id, path)
    error_count = int((cursor or {}).get("error_count") or 0) + 1
    message = f"{issue_type}: {json.dumps(details, sort_keys=True)[:500]}"
    record_shadow_integrity_issue(
        parent_id=parent_id,
        issue_type=issue_type,
        details=details,
        path=path,
    )
    _update_cursor(
        parent_id,
        path=path,
        raw_feed_state="FEED_ERROR",
        error_count=error_count,
        last_error=message,
    )


def register_paper_position(
    position: dict[str, Any],
    *,
    start_ms: int | None = None,
    raw_capacity: int | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    production = start_ms is None
    if production:
        if not runtime_enabled():
            return {"status": "DISABLED", "execution_authority": EXECUTION_AUTHORITY}
        preflight = runtime_preflight()
        if not preflight["ready"]:
            return {
                "status": "CONFIG_BLOCKED",
                "preflight": preflight,
                "execution_authority": EXECUTION_AUTHORITY,
            }
        eligible, cohort = _production_cohort_eligibility(position)
        if not eligible:
            return {
                "status": "COHORT_SKIPPED",
                "cohort": cohort,
                "execution_authority": EXECUTION_AUTHORITY,
            }
    epoch = ensure_runtime_epoch(start_ms=start_ms, path=path)
    if epoch["status"] != "ACTIVE":
        return epoch

    mode = str(position.get("mode") or "PAPER").upper()
    if mode != "PAPER":
        return {
            "status": "SOURCE_MODE_SKIPPED",
            "mode": mode,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    opened_at_ms = int(position.get("opened_at_ms") or 0)
    boundary = int(epoch["started_at_ms"])
    if opened_at_ms < boundary:
        return {
            "status": "PRE_BOUNDARY",
            "opened_at_ms": opened_at_ms,
            "boundary_ms": boundary,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    source_position_id = str(position["position_id"])
    existing = get_shadow_parent(source_position_id, path=path)
    metadata = _metadata(position)
    metadata.update(
        {
            "runtime_version": RUNTIME_VERSION,
            "runtime_epoch_id": epoch["epoch_id"],
            "runtime_boundary_ms": boundary,
            "prospective": True,
            "source_mode": "PAPER",
        }
    )
    parent = create_shadow_parent(
        source_position_id=source_position_id,
        signal_id=position.get("signal_id"),
        symbol=str(position["symbol"]),
        side=str(position["side"]),
        opened_at_ms=opened_at_ms,
        entry_price=float(position["entry_price"]),
        quantity=float(
            metadata.get("initial_quantity")
            or position.get("quantity")
            or 0.0
        ),
        metadata=metadata,
        path=path,
    )
    cursor = _cursor(parent["parent_id"], path)
    if cursor is None:
        cap = max_raw_symbols() if raw_capacity is None else max(1, int(raw_capacity))
        state = (
            "ACTIVE"
            if _active_raw_count(str(epoch["epoch_id"]), path) < cap
            else "CAPACITY_EXCEEDED"
        )
        _insert_cursor(
            parent_id=parent["parent_id"],
            epoch_id=str(epoch["epoch_id"]),
            symbol=str(position["symbol"]),
            opened_at_ms=opened_at_ms,
            raw_feed_state=state,
            path=path,
        )
        cursor = _cursor(parent["parent_id"], path)
        if state == "CAPACITY_EXCEEDED":
            record_shadow_integrity_issue(
                parent_id=parent["parent_id"],
                issue_type="RAW_FEED_CAPACITY_EXCEEDED",
                details={
                    "max_raw_symbols": cap,
                    "epoch_id": epoch["epoch_id"],
                },
                path=path,
            )

    return {
        "status": "EXISTING" if existing else "REGISTERED",
        "parent_id": parent["parent_id"],
        "source_position_id": source_position_id,
        "epoch_id": epoch["epoch_id"],
        "boundary_ms": boundary,
        "raw_feed_state": cursor["raw_feed_state"] if cursor else None,
        "execution_authority": EXECUTION_AUTHORITY,
    }


def _raw_needed(parent_id: str, path: str | Path | None = None) -> bool:
    branches = {r["branch_key"]: r for r in list_shadow_branches(parent_id, path=path)}
    for key in ("BE025_CONSERVATIVE", "BE018_AGGRESSIVE"):
        branch = branches.get(key)
        if branch is None:
            return True
        if str(branch.get("status") or "").upper() == "CLOSED":
            continue
        state = _metadata({"raw_json": branch.get("state_json")})
        if not bool(state.get("decision_terminal")) and not bool(state.get("be_superseded")):
            return True
    return False


def _normalize_agg_trade(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "agg_trade_id": int(item["a"]),
        "price": float(item["p"]),
        "quantity": float(item.get("q") or 0.0),
        "first_trade_id": int(item.get("f") or 0),
        "last_trade_id": int(item.get("l") or 0),
        "exchange_time_ms": int(item["T"]),
        "buyer_is_maker": bool(item.get("m")),
        "normal_quantity": (
            None if item.get("nq") is None else float(item.get("nq") or 0.0)
        ),
    }


def _collect_raw_events(
    *,
    parent: dict[str, Any],
    cursor: dict[str, Any],
    upto_ms: int,
    client: BinancePublicClient,
    pages_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parent_id = str(parent["parent_id"])
    symbol = str(parent["symbol"]).upper()
    opened_at_ms = int(parent["opened_at_ms"])
    last_event_time = int(cursor.get("last_event_time_ms") or opened_at_ms)
    last_scan = int(cursor.get("last_raw_scan_ms") or max(0, opened_at_ms - 1))
    last_agg_id = cursor.get("last_agg_trade_id")
    last_agg_id = None if last_agg_id is None else int(last_agg_id)
    last_agg_time = cursor.get("last_agg_trade_time_ms")
    last_agg_time = None if last_agg_time is None else int(last_agg_time)
    cutoff = int(upto_ms)
    if cutoff <= last_scan:
        return [], {
            "last_agg_trade_id": last_agg_id,
            "last_agg_trade_time_ms": last_agg_time,
            "last_raw_scan_ms": last_scan,
            "last_event_time_ms": last_event_time,
        }

    now_ms = int(time.time() * 1000)
    if last_agg_id is None and max(opened_at_ms, last_scan + 1) < now_ms - RAW_RETENTION_GUARD_MS:
        raise RuntimeError("RAW_HISTORY_OUTSIDE_SAFE_RETENTION_WINDOW")

    events: list[dict[str, Any]] = []
    expected_id = None if last_agg_id is None else last_agg_id + 1
    next_from_id = expected_id
    start_time = max(opened_at_ms, last_scan + 1)
    caught_up = False

    for page in range(1, int(pages_limit) + 1):
        if next_from_id is not None:
            rows = client.agg_trades(
                symbol,
                from_id=next_from_id,
                limit=RAW_PAGE_LIMIT,
            )
        else:
            kwargs: dict[str, Any] = {
                "start_time": start_time,
                "limit": RAW_PAGE_LIMIT,
            }
            if cutoff - start_time < 3_599_000:
                kwargs["end_time"] = cutoff
            rows = client.agg_trades(symbol, **kwargs)

        if not rows:
            caught_up = True
            break

        saw_future = False
        page_last_id = None
        for raw in rows:
            trade = _normalize_agg_trade(raw)
            agg_id = int(trade["agg_trade_id"])
            ts = int(trade["exchange_time_ms"])
            page_last_id = agg_id

            if expected_id is not None and agg_id < expected_id:
                continue
            if expected_id is not None and agg_id != expected_id:
                raise RuntimeError(
                    f"RAW_AGG_ID_GAP expected={expected_id} got={agg_id}"
                )
            expected_id = agg_id + 1

            if ts < opened_at_ms:
                continue
            if ts > cutoff:
                saw_future = True
                break
            if ts < last_event_time:
                raise RuntimeError(
                    f"RAW_EVENT_LATE_AFTER_CANONICAL raw={ts} canonical={last_event_time}"
                )
            if float(trade["price"]) <= 0:
                raise RuntimeError("RAW_AGG_INVALID_PRICE")

            events.append(
                {
                    "source_event_id": f"agg:{symbol}:{agg_id}",
                    "event_time_ms": ts,
                    "event_type": "AGG_TRADE",
                    "market_price": float(trade["price"]),
                    "payload": {
                        **trade,
                        "runtime_version": RUNTIME_VERSION,
                        "feed": "BINANCE_FUTURES_AGGTRADES_REST",
                    },
                }
            )
            last_agg_id = agg_id
            last_agg_time = ts
            last_event_time = ts

        if saw_future:
            caught_up = True
            break
        if len(rows) < RAW_PAGE_LIMIT:
            caught_up = True
            break
        if page_last_id is None:
            caught_up = True
            break
        next_from_id = int(page_last_id) + 1

    if not caught_up:
        raise RuntimeError(
            f"RAW_BACKFILL_PAGE_LIMIT pages={pages_limit} cutoff={cutoff}"
        )

    return events, {
        "last_agg_trade_id": last_agg_id,
        "last_agg_trade_time_ms": last_agg_time,
        "last_raw_scan_ms": cutoff,
        "last_event_time_ms": last_event_time,
    }


def _run_batch(
    *,
    parent_id: str,
    events: list[dict[str, Any]],
    cursor_updates: dict[str, Any],
    path: str | Path | None = None,
) -> dict[str, Any]:
    if not events:
        _update_cursor(parent_id, path=path, **cursor_updates)
        return {
            "status": "NO_EVENTS",
            "parent_id": parent_id,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    fanout = fanout_shadow_events_batch(
        parent_id=parent_id,
        events=events,
        path=path,
    )
    if fanout["status"] != "BATCH_OK" or fanout.get("last_event_seq") is None:
        return {
            "status": "FANOUT_ERROR",
            "parent_id": parent_id,
            "fanout": fanout,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    through_seq = int(fanout["last_event_seq"])
    decision = process_shadow_events_through(
        parent_id=parent_id,
        through_event_seq=through_seq,
        path=path,
    )
    if decision["status"] not in {"ADAPTER_BATCH_OK", "ALREADY_PROCESSED"}:
        return {
            "status": "ADAPTER_ERROR",
            "parent_id": parent_id,
            "fanout": fanout,
            "decision": decision,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    settlement = settle_shadow_parent(
        parent_id,
        upto_event_seq=through_seq,
        path=path,
    )

    last_event_time = max(int(e["event_time_ms"]) for e in events)
    merged_cursor_updates = dict(cursor_updates)
    merged_cursor_updates["last_event_time_ms"] = last_event_time
    _update_cursor(
        parent_id,
        path=path,
        **merged_cursor_updates,
    )

    if (
        settlement["status"] == "SETTLEMENT_BLOCKED"
        and settlement.get("reason") == "PARITY_ERROR"
    ):
        return {
            "status": "COMPARISON_INVALID",
            "parent_id": parent_id,
            "through_event_seq": through_seq,
            "event_count": len(events),
            "fanout": fanout,
            "decision": decision,
            "settlement": settlement,
            "execution_authority": EXECUTION_AUTHORITY,
        }
    if settlement["status"] != "SETTLEMENT_OK":
        return {
            "status": "SETTLEMENT_ERROR",
            "parent_id": parent_id,
            "fanout": fanout,
            "decision": decision,
            "settlement": settlement,
            "execution_authority": EXECUTION_AUTHORITY,
        }
    return {
        "status": "COMPLETE",
        "parent_id": parent_id,
        "through_event_seq": through_seq,
        "event_count": len(events),
        "fanout": fanout,
        "decision": decision,
        "settlement": settlement,
        "execution_authority": EXECUTION_AUTHORITY,
    }


def process_protection_sample(
    position: dict[str, Any],
    *,
    current_price: float,
    observed_at_ms: int,
    cycle_id: str,
    client: BinancePublicClient,
    start_ms: int | None = None,
    raw_capacity: int | None = None,
    pages_limit: int | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    if start_ms is None and not runtime_enabled():
        return {"status": "DISABLED", "execution_authority": EXECUTION_AUTHORITY}
    with _RUNTIME_LOCK:
        reg = register_paper_position(
            position,
            start_ms=start_ms,
            raw_capacity=raw_capacity,
            path=path,
        )
        if reg["status"] in {
            "DISABLED",
            "WAITING_FOR_START_BOUNDARY",
            "BOUNDARY_CONFLICT",
            "PRE_BOUNDARY",
            "SOURCE_MODE_SKIPPED",
            "CONFIG_BLOCKED",
            "COHORT_SKIPPED",
        }:
            return reg

        parent = get_shadow_parent(str(position["position_id"]), path=path)
        if parent is None:
            raise RuntimeError("registered shadow parent not found")
        parent_id = str(parent["parent_id"])
        cursor = _cursor(parent_id, path)
        if cursor is None:
            raise RuntimeError("shadow runtime cursor not found")

        raw_events: list[dict[str, Any]] = []
        raw_updates: dict[str, Any] = {}
        raw_status = str(cursor.get("raw_feed_state") or "ACTIVE")

        if raw_status == "ACTIVE":
            if _raw_needed(parent_id, path):
                try:
                    raw_events, raw_updates = _collect_raw_events(
                        parent=parent,
                        cursor=cursor,
                        upto_ms=int(observed_at_ms),
                        client=client,
                        pages_limit=(
                            raw_max_pages()
                            if pages_limit is None
                            else max(1, int(pages_limit))
                        ),
                    )
                except Exception as exc:
                    _mark_feed_error(
                        parent_id,
                        "RAW_FEED_ERROR",
                        {
                            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                            "observed_at_ms": int(observed_at_ms),
                            "cycle_id": str(cycle_id),
                        },
                        path=path,
                    )
                    raw_status = "FEED_ERROR"
            else:
                _update_cursor(
                    parent_id,
                    path=path,
                    raw_feed_state="NOT_NEEDED",
                    last_raw_scan_ms=int(observed_at_ms),
                )
                raw_status = "NOT_NEEDED"

        cursor = _cursor(parent_id, path) or cursor
        last_event_time = int(cursor.get("last_event_time_ms") or parent["opened_at_ms"])
        if raw_updates.get("last_event_time_ms") is not None:
            last_event_time = int(raw_updates["last_event_time_ms"])

        sample_time = int(observed_at_ms)
        if sample_time < last_event_time:
            record_shadow_integrity_issue(
                parent_id=parent_id,
                issue_type="LATE_PROTECTION_SAMPLE",
                details={
                    "sample_time_ms": sample_time,
                    "last_event_time_ms": last_event_time,
                    "cycle_id": str(cycle_id),
                },
                path=path,
            )
            return {
                "status": "SAMPLE_REJECTED_LATE",
                "parent_id": parent_id,
                "sample_time_ms": sample_time,
                "last_event_time_ms": last_event_time,
                "execution_authority": EXECUTION_AUTHORITY,
            }

        sample = {
            "source_event_id": f"sample:{cycle_id}:{position['position_id']}",
            "event_time_ms": sample_time,
            "event_type": "PROTECTION_SAMPLE_5S",
            "market_price": float(current_price),
            "payload": {
                "cycle_id": str(cycle_id),
                "observed_at_ms": sample_time,
                "runtime_version": RUNTIME_VERSION,
                "raw_feed_state": raw_status,
            },
        }
        updates = dict(raw_updates)
        updates["last_sample_time_ms"] = sample_time
        if not raw_updates:
            updates.setdefault("last_raw_scan_ms", cursor.get("last_raw_scan_ms"))

        result = _run_batch(
            parent_id=parent_id,
            events=raw_events + [sample],
            cursor_updates=updates,
            path=path,
        )
        return {
            **result,
            "raw_event_count": len(raw_events),
            "raw_feed_state": (_cursor(parent_id, path) or {}).get("raw_feed_state"),
            "epoch_id": reg.get("epoch_id"),
        }


def process_source_lifecycle(
    position: dict[str, Any],
    *,
    action: str,
    executed_at_ms: int,
    market_price: float,
    fill_price: float,
    executed_quantity: float,
    fee: float,
    reason: str,
    source_event_id: str,
    client: BinancePublicClient,
    start_ms: int | None = None,
    raw_capacity: int | None = None,
    pages_limit: int | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    action = str(action).upper()
    if action not in {"REDUCE", "CLOSE"}:
        raise ValueError("action must be REDUCE or CLOSE")
    if start_ms is None and not runtime_enabled():
        return {"status": "DISABLED", "execution_authority": EXECUTION_AUTHORITY}

    with _RUNTIME_LOCK:
        reg = register_paper_position(
            position,
            start_ms=start_ms,
            raw_capacity=raw_capacity,
            path=path,
        )
        if reg["status"] in {
            "DISABLED",
            "WAITING_FOR_START_BOUNDARY",
            "BOUNDARY_CONFLICT",
            "PRE_BOUNDARY",
            "SOURCE_MODE_SKIPPED",
            "CONFIG_BLOCKED",
            "COHORT_SKIPPED",
        }:
            return reg

        parent = get_shadow_parent(str(position["position_id"]), path=path)
        if parent is None:
            raise RuntimeError("shadow parent not found for source lifecycle")
        parent_id = str(parent["parent_id"])
        cursor = _cursor(parent_id, path)
        if cursor is None:
            raise RuntimeError("shadow runtime cursor not found")

        raw_events: list[dict[str, Any]] = []
        raw_updates: dict[str, Any] = {}
        raw_status = str(cursor.get("raw_feed_state") or "ACTIVE")
        if raw_status == "ACTIVE" and _raw_needed(parent_id, path):
            try:
                raw_events, raw_updates = _collect_raw_events(
                    parent=parent,
                    cursor=cursor,
                    upto_ms=int(executed_at_ms),
                    client=client,
                    pages_limit=(
                        raw_max_pages()
                        if pages_limit is None
                        else max(1, int(pages_limit))
                    ),
                )
            except Exception as exc:
                _mark_feed_error(
                    parent_id,
                    "RAW_FEED_ERROR_BEFORE_SOURCE_LIFECYCLE",
                    {
                        "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                        "action": action,
                        "executed_at_ms": int(executed_at_ms),
                    },
                    path=path,
                )
                raw_status = "FEED_ERROR"

        cursor = _cursor(parent_id, path) or cursor
        last_event_time = int(cursor.get("last_event_time_ms") or parent["opened_at_ms"])
        if raw_updates.get("last_event_time_ms") is not None:
            last_event_time = int(raw_updates["last_event_time_ms"])
        if int(executed_at_ms) < last_event_time:
            record_shadow_integrity_issue(
                parent_id=parent_id,
                issue_type="LATE_SOURCE_LIFECYCLE_RECOVERY",
                source_event_id=str(source_event_id),
                details={
                    "source_executed_at_ms": int(executed_at_ms),
                    "last_event_time_ms": last_event_time,
                    "action": action,
                },
                path=path,
            )
        lifecycle_time = max(int(executed_at_ms), last_event_time)
        lifecycle = {
            "source_event_id": str(source_event_id),
            "event_time_ms": lifecycle_time,
            "event_type": (
                "SOURCE_POSITION_REDUCE"
                if action == "REDUCE"
                else "SOURCE_POSITION_CLOSE"
            ),
            "market_price": float(market_price),
            "payload": {
                "reason": str(reason),
                "executed_quantity": float(executed_quantity),
                "fill_price": float(fill_price),
                "fee": float(fee),
                "source_executed_at_ms": int(executed_at_ms),
                "runtime_version": RUNTIME_VERSION,
                "raw_feed_state": raw_status,
            },
        }
        result = _run_batch(
            parent_id=parent_id,
            events=raw_events + [lifecycle],
            cursor_updates=raw_updates,
            path=path,
        )
        if action == "CLOSE" and result.get("status") in {"COMPLETE", "COMPARISON_INVALID"}:
            archive_shadow_parent(parent_id, path=path)
            _update_cursor(
                parent_id,
                path=path,
                raw_feed_state="SOURCE_CLOSED",
                source_closed_at_ms=int(executed_at_ms),
            )
        return {
            **result,
            "raw_event_count": len(raw_events),
            "raw_feed_state": (_cursor(parent_id, path) or {}).get("raw_feed_state"),
            "epoch_id": reg.get("epoch_id"),
        }


def _runtime_source_positions(
    epoch_id: str,
    *,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    query = """select p.*,sp.parent_id as shadow_parent_id
               from protection_shadow_runtime_cursors c
               join protection_shadow_parents sp on sp.parent_id=c.parent_id
               join positions p on p.position_id=sp.source_position_id
               where c.epoch_id=?
                 and c.source_closed_at_ms is null
               order by p.opened_at_ms,p.position_id"""
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return [dict(r) for r in conn.execute(query, (epoch_id,)).fetchall()]
    p = _runtime_persistence()
    if p.persistence_backend() == "sqlite":
        with p._sqlite_connect(p.database_path()) as conn:
            return [dict(r) for r in conn.execute(query, (epoch_id,)).fetchall()]
    with p._postgres_connect() as conn:
        with conn.cursor(cursor_factory=p.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), (epoch_id,))
            return [dict(r) for r in cur.fetchall()]


def _filled_source_lifecycle_orders(
    position_id: str,
    *,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    query = """select * from paper_orders
               where position_id=?
                 and status='FILLED'
                 and action in ('REDUCE','CLOSE')
                 and executed_at_ms is not null
               order by executed_at_ms,created_at_ms,order_id"""
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return [dict(r) for r in conn.execute(query, (position_id,)).fetchall()]
    p = _runtime_persistence()
    if p.persistence_backend() == "sqlite":
        with p._sqlite_connect(p.database_path()) as conn:
            return [dict(r) for r in conn.execute(query, (position_id,)).fetchall()]
    with p._postgres_connect() as conn:
        with conn.cursor(cursor_factory=p.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), (position_id,))
            return [dict(r) for r in cur.fetchall()]


def reconcile_source_lifecycle(
    *,
    client: BinancePublicClient | None = None,
    start_ms: int | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Recover missed source REDUCE/CLOSE shadow handoffs after restarts/errors."""
    if start_ms is None and not runtime_enabled():
        return {
            "status": "DISABLED",
            "checked_positions": 0,
            "recovered_events": 0,
            "execution_authority": EXECUTION_AUTHORITY,
        }
    epoch = ensure_runtime_epoch(start_ms=start_ms, path=path)
    if epoch["status"] != "ACTIVE":
        return {
            **epoch,
            "checked_positions": 0,
            "recovered_events": 0,
        }

    source_rows = _runtime_source_positions(str(epoch["epoch_id"]), path=path)
    if not source_rows:
        return {
            "status": "COMPLETE",
            "checked_positions": 0,
            "recovered_events": 0,
            "invalid_recoveries": 0,
            "errors": [],
            "execution_authority": EXECUTION_AUTHORITY,
        }

    client = client or BinancePublicClient(timeout=3.0, retries=1)
    recovered = 0
    invalid = 0
    errors: list[str] = []

    for position in source_rows:
        parent_id = str(position["shadow_parent_id"])
        orders = _filled_source_lifecycle_orders(
            str(position["position_id"]),
            path=path,
        )
        close_seen = False
        for order in orders:
            action = str(order.get("action") or "").upper()
            event_id = f"paper:{order['order_id']}:{action}"
            if get_shadow_event_by_source_id(parent_id, event_id, path=path) is not None:
                if action == "CLOSE":
                    close_seen = True
                continue
            try:
                result = process_source_lifecycle(
                    position,
                    action=action,
                    executed_at_ms=int(order["executed_at_ms"]),
                    market_price=float(order.get("market_price") or order["fill_price"]),
                    fill_price=float(order["fill_price"]),
                    executed_quantity=float(order.get("executed_quantity") or 0.0),
                    fee=float(order.get("fee") or 0.0),
                    reason=str(order.get("reason") or action.lower()),
                    source_event_id=event_id,
                    client=client,
                    start_ms=int(epoch["started_at_ms"]),
                    path=path,
                )
                if result.get("status") in {"COMPLETE", "COMPARISON_INVALID"}:
                    recovered += 1
                if result.get("status") == "COMPARISON_INVALID":
                    invalid += 1
                if action == "CLOSE":
                    close_seen = True
                    break
            except Exception as exc:
                errors.append(
                    f"{position['position_id']}:{order['order_id']}:"
                    f"{type(exc).__name__}:{str(exc)[:240]}"
                )
                break

        if (
            str(position.get("status") or "").upper() == "CLOSED"
            and not close_seen
        ):
            record_shadow_integrity_issue(
                parent_id=parent_id,
                issue_type="SOURCE_CLOSED_WITHOUT_FILLED_CLOSE_ORDER",
                details={
                    "source_position_id": position["position_id"],
                    "closed_at_ms": position.get("closed_at_ms"),
                },
                path=path,
            )
            archive_shadow_parent(parent_id, path=path)
            _update_cursor(
                parent_id,
                path=path,
                raw_feed_state="SOURCE_CLOSED_INVALID",
                source_closed_at_ms=int(
                    position.get("closed_at_ms") or time.time() * 1000
                ),
            )
            invalid += 1

    return {
        "status": "COMPLETE" if not errors else "PARTIAL",
        "checked_positions": len(source_rows),
        "recovered_events": recovered,
        "invalid_recoveries": invalid,
        "errors": errors,
        "execution_authority": EXECUTION_AUTHORITY,
    }


def runtime_summary(
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    initialize_shadow_runtime_store(path)
    epoch = _active_epoch(path)

    def sqlite_summary(conn: Any) -> tuple[int, dict[str, int], int, int]:
        rows = conn.execute(
            """select raw_feed_state,count(*) as n
               from protection_shadow_runtime_cursors
               group by raw_feed_state"""
        ).fetchall()
        states = {str(r[0]): int(r[1]) for r in rows}
        parents = int(conn.execute(
            "select count(*) from protection_shadow_runtime_cursors"
        ).fetchone()[0])
        active = int(conn.execute(
            """select count(*) from protection_shadow_runtime_cursors
               where source_closed_at_ms is null"""
        ).fetchone()[0])
        errors = int(conn.execute(
            """select coalesce(sum(error_count),0)
               from protection_shadow_runtime_cursors"""
        ).fetchone()[0])
        return parents, states, active, errors

    if path is not None:
        with _local_sqlite_connect(path) as conn:
            parents, states, active, errors = sqlite_summary(conn)
    else:
        p = _runtime_persistence()
        if p.persistence_backend() == "sqlite":
            with p._sqlite_connect(p.database_path()) as conn:
                parents, states, active, errors = sqlite_summary(conn)
        else:
            with p._postgres_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """select raw_feed_state,count(*)
                           from protection_shadow_runtime_cursors
                           group by raw_feed_state"""
                    )
                    states = {str(r[0]): int(r[1]) for r in cur.fetchall()}
                    cur.execute("select count(*) from protection_shadow_runtime_cursors")
                    parents = int(cur.fetchone()[0])
                    cur.execute(
                        """select count(*) from protection_shadow_runtime_cursors
                           where source_closed_at_ms is null"""
                    )
                    active = int(cur.fetchone()[0])
                    cur.execute(
                        """select coalesce(sum(error_count),0)
                           from protection_shadow_runtime_cursors"""
                    )
                    errors = int(cur.fetchone()[0])

    return {
        "runtime_version": RUNTIME_VERSION,
        "configured_enabled": runtime_enabled(),
        "configured_start_ms": configured_start_ms(),
        "production_cohort": PRODUCTION_COHORT,
        "preflight": runtime_preflight(),
        "epoch": epoch,
        "parents": parents,
        "active_source_parents": active,
        "raw_feed_states": states,
        "feed_error_count": errors,
        "max_raw_symbols": max_raw_symbols(),
        "raw_max_pages": raw_max_pages(),
        "raw_page_limit": RAW_PAGE_LIMIT,
        "execution_authority": EXECUTION_AUTHORITY,
        "source_mode": "PAPER_ONLY",
        "raw_feed": "BINANCE_FUTURES_AGGTRADES_REST",
        "sample_feed": "PP_V4_5S_OBSERVER",
    }
