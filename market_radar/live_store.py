from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

import psycopg2.extras

from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    initialize_database,
    persistence_backend,
)


LIVE_STORE_VERSION = "stage15-store-v1"

SQLITE_SCHEMA = """
create table if not exists live_orders (
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
    submitted_at_ms integer,
    filled_at_ms integer,
    requested_quantity real,
    executed_quantity real,
    reference_price real,
    avg_price real,
    commission real,
    realized_pnl real,
    binance_order_id text,
    client_order_id text not null,
    reason text,
    payload_json text,
    error_text text,
    unique(source_type, source_id),
    unique(client_order_id)
);
create index if not exists idx_live_orders_status_time
on live_orders(status, created_at_ms);
create index if not exists idx_live_orders_position
on live_orders(position_id, created_at_ms);
"""

POSTGRES_SCHEMA = """
create table if not exists live_orders (
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
    submitted_at_ms bigint,
    filled_at_ms bigint,
    requested_quantity double precision,
    executed_quantity double precision,
    reference_price double precision,
    avg_price double precision,
    commission double precision,
    realized_pnl double precision,
    binance_order_id text,
    client_order_id text not null,
    reason text,
    payload_json text,
    error_text text,
    unique(source_type, source_id),
    unique(client_order_id)
);
create index if not exists idx_live_orders_status_time
on live_orders(status, created_at_ms);
create index if not exists idx_live_orders_position
on live_orders(position_id, created_at_ms);
"""


def initialize_live_store() -> None:
    initialize_database()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.executescript(SQLITE_SCHEMA)
        return
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(POSTGRES_SCHEMA)


def _client_order_id(source_type: str, source_id: str, action: str) -> str:
    raw = f"{source_type}:{source_id}:{action}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:22]
    return f"BB{action[:1].upper()}{digest}"[:32]


def list_live_entry_candidates(
    *,
    max_age_ms: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    initialize_live_store()
    cutoff = int(time.time() * 1000) - max(1, int(max_age_ms))
    safe_limit = max(1, min(int(limit), 100))

    sqlite_query = """
        select
            a.signal_id, a.reviewed_at_ms,
            s.symbol, s.side, s.signal_time_ms, s.signal_price,
            s.stage, s.long_score, s.short_score, s.score_edge
        from entry_approvals a
        join signals s on s.signal_id = a.signal_id
        left join positions p
          on p.signal_id = a.signal_id and p.mode='LIVE'
        left join live_orders o
          on o.source_type='ENTRY' and o.source_id=a.signal_id
        where a.final_verdict='APPROVE'
          and a.reviewed_at_ms >= ?
          and p.position_id is null
          and o.order_id is null
        order by a.reviewed_at_ms asc
        limit ?
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                sqlite_query,
                (cutoff, safe_limit),
            ).fetchall()
            return [dict(row) for row in rows]

    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                sqlite_query.replace("?", "%s"),
                (cutoff, safe_limit),
            )
            return [dict(row) for row in cur.fetchall()]


def count_open_live_positions() -> int:
    initialize_live_store()
    query = """
        select count(*) from positions
        where mode='LIVE' and status in ('OPEN','REDUCED')
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            return int(conn.execute(query).fetchone()[0])
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return int(cur.fetchone()[0])


def list_open_live_positions() -> list[dict[str, Any]]:
    initialize_live_store()
    query = """
        select * from positions
        where mode='LIVE' and status in ('OPEN','REDUCED')
        order by opened_at_ms asc
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            return [dict(row) for row in conn.execute(query).fetchall()]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]


def has_open_live_symbol(symbol: str) -> bool:
    initialize_live_store()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                """
                select 1 from positions
                where mode='LIVE' and status in ('OPEN','REDUCED')
                  and symbol=? limit 1
                """,
                (symbol.upper(),),
            ).fetchone()
            return row is not None
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select 1 from positions
                where mode='LIVE' and status in ('OPEN','REDUCED')
                  and symbol=%s limit 1
                """,
                (symbol.upper(),),
            )
            return cur.fetchone() is not None


def create_live_order(
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
    initialize_live_store()
    action = action.upper()
    order_id = f"LIVE:{source_type}:{source_id}:{action}"
    client_order_id = _client_order_id(source_type, source_id, action)
    created = int(time.time() * 1000)
    raw = json.dumps(payload or {}, separators=(",", ":"), allow_nan=False)
    values = (
        order_id, source_type, source_id, position_id, signal_id,
        symbol.upper(), side.upper(), action, "PENDING", created,
        requested_quantity, client_order_id, reason, raw,
    )

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                insert or ignore into live_orders (
                    order_id, source_type, source_id, position_id, signal_id,
                    symbol, side, action, status, created_at_ms,
                    requested_quantity, client_order_id, reason, payload_json
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
        return order_id

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into live_orders (
                    order_id, source_type, source_id, position_id, signal_id,
                    symbol, side, action, status, created_at_ms,
                    requested_quantity, client_order_id, reason, payload_json
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(source_type, source_id) do nothing
                """,
                values,
            )
    return order_id


def list_pending_live_orders(limit: int = 50) -> list[dict[str, Any]]:
    initialize_live_store()
    safe_limit = max(1, min(int(limit), 200))
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                """
                select * from live_orders
                where status in ('PENDING','SUBMITTING')
                order by created_at_ms asc limit ?
                """,
                (safe_limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select * from live_orders
                where status in ('PENDING','SUBMITTING')
                order by created_at_ms asc limit %s
                """,
                (safe_limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def mark_live_order(
    order_id: str,
    *,
    status: str,
    submitted_at_ms: int | None = None,
    filled_at_ms: int | None = None,
    executed_quantity: float | None = None,
    reference_price: float | None = None,
    avg_price: float | None = None,
    commission: float | None = None,
    realized_pnl: float | None = None,
    binance_order_id: str | None = None,
    error_text: str | None = None,
    reason: str | None = None,
) -> None:
    initialize_live_store()
    params = (
        status, submitted_at_ms, filled_at_ms, executed_quantity,
        reference_price, avg_price, commission, realized_pnl,
        binance_order_id, error_text, reason, order_id,
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update live_orders set
                    status=?,
                    submitted_at_ms=coalesce(?,submitted_at_ms),
                    filled_at_ms=coalesce(?,filled_at_ms),
                    executed_quantity=coalesce(?,executed_quantity),
                    reference_price=coalesce(?,reference_price),
                    avg_price=coalesce(?,avg_price),
                    commission=coalesce(?,commission),
                    realized_pnl=coalesce(?,realized_pnl),
                    binance_order_id=coalesce(?,binance_order_id),
                    error_text=?,
                    reason=coalesce(?,reason)
                where order_id=?
                """,
                params,
            )
        return
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update live_orders set
                    status=%s,
                    submitted_at_ms=coalesce(%s,submitted_at_ms),
                    filled_at_ms=coalesce(%s,filled_at_ms),
                    executed_quantity=coalesce(%s,executed_quantity),
                    reference_price=coalesce(%s,reference_price),
                    avg_price=coalesce(%s,avg_price),
                    commission=coalesce(%s,commission),
                    realized_pnl=coalesce(%s,realized_pnl),
                    binance_order_id=coalesce(%s,binance_order_id),
                    error_text=%s,
                    reason=coalesce(%s,reason)
                where order_id=%s
                """,
                params,
            )


def get_live_position(position_id: str) -> dict[str, Any] | None:
    initialize_live_store()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                "select * from positions where position_id=? and mode='LIVE'",
                (position_id,),
            ).fetchone()
            return dict(row) if row else None
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "select * from positions where position_id=%s and mode='LIVE'",
                (position_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_live_position(
    *,
    position_id: str,
    signal_id: str,
    symbol: str,
    side: str,
    opened_at_ms: int,
    entry_price: float,
    quantity: float,
    metadata: dict[str, Any],
) -> None:
    initialize_live_store()
    raw = json.dumps(metadata, separators=(",", ":"), allow_nan=False)
    values = (
        position_id, signal_id, symbol.upper(), side.upper(), "OPEN",
        opened_at_ms, entry_price, quantity, None, "LIVE", raw,
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
                    ) values (?,?,'LIVE_POSITION_OPENED',?,?)
                    """,
                    (signal_id, position_id, opened_at_ms, raw),
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
            if cur.fetchone() is not None:
                cur.execute(
                    """
                    insert into trade_events (
                        signal_id, position_id, event_type,
                        event_time_ms, payload_json
                    ) values (%s,%s,'LIVE_POSITION_OPENED',%s,%s)
                    """,
                    (signal_id, position_id, opened_at_ms, raw),
                )


def update_live_reduce(
    *,
    position_id: str,
    event_time_ms: int,
    new_quantity: float,
    realized_pnl: float,
    realized_pnl_pct: float,
    metadata: dict[str, Any],
) -> None:
    initialize_live_store()
    raw = json.dumps(metadata, separators=(",", ":"), allow_nan=False)
    sql = """
        update positions
        set status='REDUCED', quantity={q}, realized_pnl={p},
            realized_pnl_pct={pp}, raw_json={r}
        where position_id={id} and mode='LIVE'
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                sql.format(q="?", p="?", pp="?", r="?", id="?"),
                (new_quantity, realized_pnl, realized_pnl_pct, raw, position_id),
            )
        return
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.format(q="%s", p="%s", pp="%s", r="%s", id="%s"),
                (new_quantity, realized_pnl, realized_pnl_pct, raw, position_id),
            )


def close_live_position(
    *,
    position_id: str,
    event_time_ms: int,
    exit_price: float,
    realized_pnl: float,
    realized_pnl_pct: float,
    close_reason: str,
    metadata: dict[str, Any],
) -> None:
    initialize_live_store()
    raw = json.dumps(metadata, separators=(",", ":"), allow_nan=False)
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update positions
                set status='CLOSED', closed_at_ms=?, exit_price=?,
                    quantity=0, realized_pnl=?, realized_pnl_pct=?,
                    close_reason=?, raw_json=?
                where position_id=? and mode='LIVE'
                """,
                (
                    event_time_ms, exit_price, realized_pnl,
                    realized_pnl_pct, close_reason, raw, position_id,
                ),
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
                where position_id=%s and mode='LIVE'
                """,
                (
                    event_time_ms, exit_price, realized_pnl,
                    realized_pnl_pct, close_reason, raw, position_id,
                ),
            )


def list_unacted_live_lifecycle_actions(limit: int = 100) -> list[dict[str, Any]]:
    initialize_live_store()
    safe_limit = max(1, min(int(limit), 500))
    sqlite_query = """
        select e.*, p.symbol, p.side, p.signal_id, p.quantity,
               p.status as position_status
        from position_evaluations e
        join positions p on p.position_id=e.position_id
        left join live_orders o
          on o.source_type='LIFECYCLE' and o.source_id=e.evaluation_id
        where e.evaluation_id = (
              select e2.evaluation_id
              from position_evaluations e2
              where e2.position_id=e.position_id
              order by e2.candle_close_time_ms desc
              limit 1
          )
          and e.final_action in ('REDUCE','CLOSE')
          and p.mode='LIVE'
          and p.status in ('OPEN','REDUCED')
          and o.order_id is null
        order by e.candle_close_time_ms asc
        limit ?
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(sqlite_query, (safe_limit,)).fetchall()
            return [dict(row) for row in rows]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sqlite_query.replace("?", "%s"), (safe_limit,))
            return [dict(row) for row in cur.fetchall()]


def live_daily_pnl() -> float:
    initialize_live_store()
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start_ms = int(start.timestamp() * 1000)
    query_sqlite = """
        select coalesce(sum(realized_pnl),0)
        from positions
        where mode='LIVE' and status='CLOSED'
          and closed_at_ms >= ?
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            return float(conn.execute(query_sqlite, (start_ms,)).fetchone()[0] or 0.0)
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query_sqlite.replace("?", "%s"), (start_ms,))
            return float(cur.fetchone()[0] or 0.0)


def live_recent_loss_streak(limit: int = 20) -> int:
    initialize_live_store()
    safe_limit = max(1, min(int(limit), 100))
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                """
                select realized_pnl from positions
                where mode='LIVE' and status='CLOSED'
                order by closed_at_ms desc limit ?
                """,
                (safe_limit,),
            ).fetchall()
            pnls = [float(row[0] or 0.0) for row in rows]
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select realized_pnl from positions
                    where mode='LIVE' and status='CLOSED'
                    order by closed_at_ms desc limit %s
                    """,
                    (safe_limit,),
                )
                pnls = [float(row[0] or 0.0) for row in cur.fetchall()]
    streak = 0
    for pnl in pnls:
        if pnl < 0:
            streak += 1
        else:
            break
    return streak


def paper_gate_stats() -> dict[str, Any]:
    initialize_live_store()
    query = """
        select
          count(*) as closed,
          coalesce(sum(case when realized_pnl > 0 then 1 else 0 end),0) as wins,
          coalesce(sum(realized_pnl),0) as net_pnl
        from positions
        where mode='PAPER' and status='CLOSED'
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(query).fetchone()
            closed, wins, net_pnl = row[0], row[1], row[2]
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                closed, wins, net_pnl = cur.fetchone()
    closed = int(closed or 0)
    wins = int(wins or 0)
    return {
        "closed": closed,
        "wins": wins,
        "net_pnl": float(net_pnl or 0.0),
        "win_rate_pct": (100.0 * wins / closed) if closed else None,
    }


def list_live_orders(limit: int = 100) -> list[dict[str, Any]]:
    initialize_live_store()
    safe_limit = max(1, min(int(limit), 500))
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                "select * from live_orders order by created_at_ms desc limit ?",
                (safe_limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "select * from live_orders order by created_at_ms desc limit %s",
                (safe_limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def live_summary() -> dict[str, Any]:
    initialize_live_store()
    queries = {
        "open_positions": """
            select count(*) from positions
            where mode='LIVE' and status in ('OPEN','REDUCED')
        """,
        "closed_positions": """
            select count(*) from positions
            where mode='LIVE' and status='CLOSED'
        """,
        "wins": """
            select count(*) from positions
            where mode='LIVE' and status='CLOSED' and realized_pnl > 0
        """,
        "net_pnl": """
            select coalesce(sum(realized_pnl),0) from positions
            where mode='LIVE' and status='CLOSED'
        """,
        "commission": """
            select coalesce(sum(commission),0) from live_orders
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
    closed = int(values["closed_positions"] or 0)
    wins = int(values["wins"] or 0)
    values["win_rate_pct"] = 100.0 * wins / closed if closed else None
    values["daily_pnl"] = live_daily_pnl()
    values["loss_streak"] = live_recent_loss_streak()
    values["live_store_version"] = LIVE_STORE_VERSION
    return values
