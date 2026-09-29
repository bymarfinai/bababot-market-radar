from __future__ import annotations

import json
import threading
import time
from typing import Any

import psycopg2.extras

from .pipeline_cohort import cohort_summary, label_signal_cohort
from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    initialize_database,
    persistence_backend,
    update_entry_latency,
)


PAPER_STORE_VERSION = "stage13-store-v1"

_PAPER_INIT_LOCK = threading.Lock()
_PAPER_INITIALIZED: set[tuple[str, str]] = set()

SQLITE_SCHEMA = """
create table if not exists paper_orders (
    order_id text primary key,
    source_type text not null,
    source_id text not null,
    position_id text,
    signal_id text,
    symbol text not null,
    side text not null,
    action text not null,
    status text not null,
    created_at_ms integer not null,
    executed_at_ms integer,
    requested_quantity real,
    executed_quantity real,
    market_price real,
    fill_price real,
    fee real,
    reason text,
    payload_json text,
    unique(source_type, source_id)
);
create index if not exists idx_paper_orders_status_time
on paper_orders(status, created_at_ms);
create index if not exists idx_paper_orders_position
on paper_orders(position_id, created_at_ms);
"""

POSTGRES_SCHEMA = """
create table if not exists paper_orders (
    order_id text primary key,
    source_type text not null,
    source_id text not null,
    position_id text,
    signal_id text,
    symbol text not null,
    side text not null,
    action text not null,
    status text not null,
    created_at_ms bigint not null,
    executed_at_ms bigint,
    requested_quantity double precision,
    executed_quantity double precision,
    market_price double precision,
    fill_price double precision,
    fee double precision,
    reason text,
    payload_json text,
    unique(source_type, source_id)
);
create index if not exists idx_paper_orders_status_time
on paper_orders(status, created_at_ms);
create index if not exists idx_paper_orders_position
on paper_orders(position_id, created_at_ms);
"""


def initialize_paper_store() -> None:
    initialize_database()
    backend = persistence_backend()
    key = (
        ("sqlite", str(database_path().resolve()))
        if backend == "sqlite"
        else ("postgres", "primary")
    )
    with _PAPER_INIT_LOCK:
        if key in _PAPER_INITIALIZED:
            return
        if backend == "sqlite":
            with _sqlite_connect(database_path()) as conn:
                conn.executescript(SQLITE_SCHEMA)
        else:
            with _postgres_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(POSTGRES_SCHEMA)
        _PAPER_INITIALIZED.add(key)


def list_entry_candidates(
    *,
    max_age_ms: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    initialize_paper_store()
    cutoff = int(time.time() * 1000) - max(1, int(max_age_ms))
    safe_limit = max(1, min(int(limit), 100))

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                """
                select
                    a.signal_id, a.reviewed_at_ms,
                    s.symbol, s.side, s.signal_time_ms, s.signal_price,
                    s.stage, s.long_score, s.short_score, s.score_edge,
                    s.structure_status, s.taker_bias, s.raw_oi_change_pct,
                    s.market_regime, s.decision_reasons_json
                from entry_approvals a
                join signals s on s.signal_id = a.signal_id
                left join positions p on p.signal_id = a.signal_id
                left join paper_orders o
                  on o.source_type='ENTRY' and o.source_id=a.signal_id
                where a.final_verdict='APPROVE'
                  and a.reviewed_at_ms >= ?
                  and p.position_id is null
                  and o.order_id is null
                order by a.reviewed_at_ms desc
                limit ?
                """,
                (cutoff, safe_limit),
            ).fetchall()
            return [dict(row) for row in rows]

    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select
                    a.signal_id, a.reviewed_at_ms,
                    s.symbol, s.side, s.signal_time_ms, s.signal_price,
                    s.stage, s.long_score, s.short_score, s.score_edge,
                    s.structure_status, s.taker_bias, s.raw_oi_change_pct,
                    s.market_regime, s.decision_reasons_json
                from entry_approvals a
                join signals s on s.signal_id = a.signal_id
                left join positions p on p.signal_id = a.signal_id
                left join paper_orders o
                  on o.source_type='ENTRY' and o.source_id=a.signal_id
                where a.final_verdict='APPROVE'
                  and a.reviewed_at_ms >= %s
                  and p.position_id is null
                  and o.order_id is null
                order by a.reviewed_at_ms desc
                limit %s
                """,
                (cutoff, safe_limit),
            )
            return [dict(row) for row in cur.fetchall()]


def get_entry_candidate(signal_id: str) -> dict[str, Any] | None:
    """Return one approved paper-entry candidate if it is still unacted."""
    initialize_paper_store()
    params = (signal_id,)
    query = """
        select
            a.signal_id, a.reviewed_at_ms,
            s.symbol, s.side, s.signal_time_ms, s.signal_price,
            s.stage, s.long_score, s.short_score, s.score_edge,
                    s.structure_status, s.taker_bias, s.raw_oi_change_pct,
                    s.market_regime, s.decision_reasons_json
        from entry_approvals a
        join signals s on s.signal_id = a.signal_id
        left join positions p on p.signal_id = a.signal_id
        left join paper_orders o
          on o.source_type='ENTRY' and o.source_id=a.signal_id
        where a.signal_id=?
          and a.final_verdict='APPROVE'
          and p.position_id is null
          and o.order_id is null
        limit 1
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), params)
            row = cur.fetchone()
            return dict(row) if row else None


def get_paper_order(order_id: str) -> dict[str, Any] | None:
    initialize_paper_store()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                "select * from paper_orders where order_id=?",
                (order_id,),
            ).fetchone()
            return dict(row) if row else None
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "select * from paper_orders where order_id=%s",
                (order_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def count_open_paper_positions() -> int:
    initialize_paper_store()
    query = """
        select count(*)
        from positions
        where mode='PAPER' and status in ('OPEN','REDUCED')
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            return int(conn.execute(query).fetchone()[0])
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return int(cur.fetchone()[0])


def has_open_paper_symbol(symbol: str) -> bool:
    initialize_paper_store()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                """
                select 1 from positions
                where mode='PAPER'
                  and status in ('OPEN','REDUCED')
                  and symbol=?
                limit 1
                """,
                (symbol.upper(),),
            ).fetchone()
            return row is not None
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select 1 from positions
                where mode='PAPER'
                  and status in ('OPEN','REDUCED')
                  and symbol=%s
                limit 1
                """,
                (symbol.upper(),),
            )
            return cur.fetchone() is not None


def create_order(
    *,
    source_type: str,
    source_id: str,
    position_id: str | None,
    signal_id: str | None,
    symbol: str,
    side: str,
    action: str,
    requested_quantity: float | None,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> str:
    initialize_paper_store()
    order_id = f"{source_type}:{source_id}:{action}"
    created = int(time.time() * 1000)
    payload_json = (
        json.dumps(payload, separators=(",", ":"), allow_nan=False)
        if payload is not None
        else None
    )
    values = (
        order_id, source_type, source_id, position_id, signal_id,
        symbol.upper(), side.upper(), action.upper(), "PENDING",
        created, requested_quantity, reason, payload_json,
    )

    inserted = False
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            cur = conn.execute(
                """
                insert or ignore into paper_orders (
                    order_id, source_type, source_id, position_id, signal_id,
                    symbol, side, action, status, created_at_ms,
                    requested_quantity, reason, payload_json
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
            inserted = bool(cur.rowcount)
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into paper_orders (
                        order_id, source_type, source_id, position_id, signal_id,
                        symbol, side, action, status, created_at_ms,
                        requested_quantity, reason, payload_json
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict(source_type, source_id) do nothing
                    returning order_id
                    """,
                    values,
                )
                inserted = cur.fetchone() is not None

    if inserted and source_type.upper() == "ENTRY" and signal_id:
        update_entry_latency(
            str(signal_id),
            order_created_at_ms=created,
        )
    return order_id


def list_pending_orders(limit: int = 100) -> list[dict[str, Any]]:
    initialize_paper_store()
    safe_limit = max(1, min(int(limit), 500))
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                """
                select * from paper_orders
                where status='PENDING'
                order by created_at_ms asc
                limit ?
                """,
                (safe_limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select * from paper_orders
                where status='PENDING'
                order by created_at_ms asc
                limit %s
                """,
                (safe_limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def mark_order(
    order_id: str,
    *,
    status: str,
    executed_at_ms: int | None = None,
    executed_quantity: float | None = None,
    market_price: float | None = None,
    fill_price: float | None = None,
    fee: float | None = None,
    reason: str | None = None,
) -> None:
    initialize_paper_store()
    params = (
        status, executed_at_ms, executed_quantity,
        market_price, fill_price, fee, reason, order_id,
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update paper_orders
                set status=?, executed_at_ms=?, executed_quantity=?,
                    market_price=?, fill_price=?, fee=?,
                    reason=coalesce(?, reason)
                where order_id=?
                """,
                params,
            )
        return
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update paper_orders
                set status=%s, executed_at_ms=%s, executed_quantity=%s,
                    market_price=%s, fill_price=%s, fee=%s,
                    reason=coalesce(%s, reason)
                where order_id=%s
                """,
                params,
            )


def get_position(position_id: str) -> dict[str, Any] | None:
    initialize_paper_store()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                "select * from positions where position_id=?",
                (position_id,),
            ).fetchone()
            return dict(row) if row else None
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "select * from positions where position_id=%s",
                (position_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_position(
    *,
    position_id: str,
    signal_id: str,
    symbol: str,
    side: str,
    opened_at_ms: int,
    entry_price: float,
    quantity: float,
    stop_loss: float | None,
    metadata: dict[str, Any],
) -> None:
    initialize_paper_store()
    raw = json.dumps(metadata, separators=(",", ":"), allow_nan=False)
    values = (
        position_id, signal_id, symbol.upper(), side.upper(), "OPEN",
        opened_at_ms, entry_price, quantity, stop_loss, "PAPER", raw,
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            cur = conn.execute(
                """
                insert or ignore into positions (
                    position_id, signal_id, symbol, side, status,
                    opened_at_ms, entry_price, quantity, stop_loss,
                    mode, raw_json
                ) values (?,?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
            if cur.rowcount:
                conn.execute(
                    """
                    insert into trade_events (
                        signal_id, position_id, event_type,
                        event_time_ms, payload_json
                    ) values (?,?,'PAPER_POSITION_OPENED',?,?)
                    """,
                    (signal_id, position_id, opened_at_ms, raw),
                )
        if cur.rowcount:
            update_entry_latency(
                signal_id,
                position_opened_at_ms=opened_at_ms,
            )
            label_signal_cohort(
                signal_id,
                opened_at_ms=opened_at_ms,
                metadata={
                    "mode": "PAPER",
                    "position_id": position_id,
                    "stage11c_version": metadata.get("stage11c_version"),
                    "stage13_version": metadata.get("paper_trading_version"),
                },
            )
        return

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into positions (
                    position_id, signal_id, symbol, side, status,
                    opened_at_ms, entry_price, quantity, stop_loss,
                    mode, raw_json
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(position_id) do nothing
                returning position_id
                """,
                values,
            )
            inserted = cur.fetchone() is not None
            if inserted:
                cur.execute(
                    """
                    insert into trade_events (
                        signal_id, position_id, event_type,
                        event_time_ms, payload_json
                    ) values (%s,%s,'PAPER_POSITION_OPENED',%s,%s)
                    """,
                    (signal_id, position_id, opened_at_ms, raw),
                )

    if inserted:
        update_entry_latency(
            signal_id,
            position_opened_at_ms=opened_at_ms,
        )
        label_signal_cohort(
            signal_id,
            opened_at_ms=opened_at_ms,
            metadata={
                    "mode": "PAPER",
                    "position_id": position_id,
                    "stage11c_version": metadata.get("stage11c_version"),
                    "stage13_version": metadata.get("paper_trading_version"),
                },
        )


def update_position_reduce(
    *,
    position_id: str,
    event_time_ms: int,
    new_quantity: float,
    realized_pnl: float,
    realized_pnl_pct: float,
    metadata: dict[str, Any],
) -> None:
    initialize_paper_store()
    raw = json.dumps(metadata, separators=(",", ":"), allow_nan=False)
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update positions
                set status='REDUCED', quantity=?, realized_pnl=?,
                    realized_pnl_pct=?, raw_json=?
                where position_id=?
                """,
                (new_quantity, realized_pnl, realized_pnl_pct, raw, position_id),
            )
            conn.execute(
                """
                insert into trade_events (
                    signal_id, position_id, event_type,
                    event_time_ms, payload_json
                )
                select signal_id, position_id, 'PAPER_POSITION_REDUCED', ?, ?
                from positions where position_id=?
                """,
                (event_time_ms, raw, position_id),
            )
        return
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update positions
                set status='REDUCED', quantity=%s, realized_pnl=%s,
                    realized_pnl_pct=%s, raw_json=%s
                where position_id=%s
                """,
                (new_quantity, realized_pnl, realized_pnl_pct, raw, position_id),
            )
            cur.execute(
                """
                insert into trade_events (
                    signal_id, position_id, event_type,
                    event_time_ms, payload_json
                )
                select signal_id, position_id, 'PAPER_POSITION_REDUCED', %s, %s
                from positions where position_id=%s
                """,
                (event_time_ms, raw, position_id),
            )


def close_position(
    *,
    position_id: str,
    event_time_ms: int,
    exit_price: float,
    realized_pnl: float,
    realized_pnl_pct: float,
    close_reason: str,
    metadata: dict[str, Any],
) -> None:
    initialize_paper_store()
    raw = json.dumps(metadata, separators=(",", ":"), allow_nan=False)
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update positions
                set status='CLOSED', closed_at_ms=?, exit_price=?,
                    quantity=0, realized_pnl=?, realized_pnl_pct=?,
                    close_reason=?, raw_json=?
                where position_id=?
                """,
                (
                    event_time_ms, exit_price, realized_pnl,
                    realized_pnl_pct, close_reason, raw, position_id,
                ),
            )
            conn.execute(
                """
                insert into trade_events (
                    signal_id, position_id, event_type,
                    event_time_ms, payload_json
                )
                select signal_id, position_id, 'PAPER_POSITION_CLOSED', ?, ?
                from positions where position_id=?
                """,
                (event_time_ms, raw, position_id),
            )
        return
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update positions
                set status='CLOSED', closed_at_ms=%s, exit_price=%s,
                    quantity=0, realized_pnl=%s, realized_pnl_pct=%s,
                    close_reason=%s, raw_json=%s
                where position_id=%s
                """,
                (
                    event_time_ms, exit_price, realized_pnl,
                    realized_pnl_pct, close_reason, raw, position_id,
                ),
            )
            cur.execute(
                """
                insert into trade_events (
                    signal_id, position_id, event_type,
                    event_time_ms, payload_json
                )
                select signal_id, position_id, 'PAPER_POSITION_CLOSED', %s, %s
                from positions where position_id=%s
                """,
                (event_time_ms, raw, position_id),
            )


def list_unacted_lifecycle_actions(limit: int = 100) -> list[dict[str, Any]]:
    initialize_paper_store()
    safe_limit = max(1, min(int(limit), 500))
    query_sqlite = """
        select e.*, p.symbol, p.side, p.signal_id, p.quantity, p.status as position_status
        from position_evaluations e
        join positions p on p.position_id=e.position_id
        left join paper_orders o
          on o.source_type='LIFECYCLE' and o.source_id=e.evaluation_id
        where e.evaluation_id = (
              select e2.evaluation_id
              from position_evaluations e2
              where e2.position_id = e.position_id
              order by e2.candle_close_time_ms desc
              limit 1
          )
          and e.final_action in ('REDUCE','CLOSE')
          and p.mode='PAPER'
          and p.status in ('OPEN','REDUCED')
          and o.order_id is null
        order by e.candle_close_time_ms asc
        limit ?
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(query_sqlite, (safe_limit,)).fetchall()
            return [dict(row) for row in rows]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                query_sqlite.replace("?", "%s"),
                (safe_limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def list_paper_orders(limit: int = 100) -> list[dict[str, Any]]:
    initialize_paper_store()
    safe_limit = max(1, min(int(limit), 500))
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                "select * from paper_orders order by created_at_ms desc limit ?",
                (safe_limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "select * from paper_orders order by created_at_ms desc limit %s",
                (safe_limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def paper_summary() -> dict[str, Any]:
    initialize_paper_store()
    queries = {
        "open_positions": """
            select count(*) from positions
            where mode='PAPER' and status in ('OPEN','REDUCED')
        """,
        "closed_positions": """
            select count(*) from positions
            where mode='PAPER' and status='CLOSED'
        """,
        "wins": """
            select count(*) from positions
            where mode='PAPER' and status='CLOSED' and realized_pnl > 0
        """,
        "losses": """
            select count(*) from positions
            where mode='PAPER' and status='CLOSED' and realized_pnl <= 0
        """,
        "net_pnl": """
            select coalesce(sum(realized_pnl),0) from positions
            where mode='PAPER' and status='CLOSED'
        """,
        "fees": """
            select coalesce(sum(fee),0) from paper_orders
            where status='FILLED'
        """,
    }
    values: dict[str, Any] = {}
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            for key, query in queries.items():
                values[key] = conn.execute(query).fetchone()[0]
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                for key, query in queries.items():
                    cur.execute(query)
                    values[key] = cur.fetchone()[0]

    closed = int(values["closed_positions"])
    wins = int(values["wins"])
    values["win_rate_pct"] = round(100.0 * wins / closed, 4) if closed else None
    values["paper_store_version"] = PAPER_STORE_VERSION
    # Always expose the hard PRE/POST boundary next to aggregate legacy totals.
    # Consumers should use pipeline_cohorts for post-rebuild evaluation.
    values["pipeline_cohorts"] = cohort_summary()
    return values
