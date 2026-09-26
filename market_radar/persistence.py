from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from .models import MarketScan


PERSISTENCE_VERSION = "stage10-v2-postgres"
DEFAULT_DB_PATH = "data/market_radar.sqlite3"


SQLITE_SCHEMA_SQL = """
create table if not exists signals (
    signal_id text primary key,
    symbol text not null,
    side text not null check (side in ('LONG','SHORT')),
    signal_time_ms integer not null,
    signal_price real,
    stage text,
    long_score real,
    short_score real,
    score_edge real,
    volume_ratio real,
    structure_status text,
    taker_bias text,
    raw_oi_change_pct real,
    funding_rate real,
    market_regime text,
    decision_context_balance integer,
    decision_reasons_json text not null default '[]',
    snapshot_json text not null,
    first_seen_at_ms integer not null,
    last_seen_at_ms integer not null,
    persistence_version text not null
);

create index if not exists idx_signals_time
on signals(signal_time_ms desc);

create index if not exists idx_signals_symbol_time
on signals(symbol, signal_time_ms desc);

create index if not exists idx_signals_side_time
on signals(side, signal_time_ms desc);

create table if not exists signal_outcomes (
    signal_id text primary key references signals(signal_id) on delete cascade,
    status text not null default 'PENDING',
    updated_at_ms integer not null,
    future_5m_return_pct real,
    future_15m_return_pct real,
    future_30m_return_pct real,
    future_1h_return_pct real,
    future_2h_return_pct real,
    mfe_15m_pct real,
    mae_15m_pct real,
    mfe_1h_pct real,
    mae_1h_pct real,
    mfe_2h_pct real,
    mae_2h_pct real,
    hit_0_5pct integer,
    hit_1pct integer,
    hit_2pct integer,
    time_to_0_5pct_minutes integer,
    time_to_1pct_minutes integer,
    time_to_2pct_minutes integer
);

create table if not exists ai_reviews (
    review_id integer primary key autoincrement,
    signal_id text not null references signals(signal_id) on delete cascade,
    reviewed_at_ms integer not null,
    verdict text,
    confidence text,
    model text,
    reasons_json text not null default '[]',
    raw_json text
);

create index if not exists idx_ai_reviews_signal_time
on ai_reviews(signal_id, reviewed_at_ms desc);

create table if not exists entry_approvals (
    signal_id text primary key references signals(signal_id) on delete cascade,
    reviewed_at_ms integer not null,
    risk_verdict text not null,
    ai_verdict text not null,
    final_verdict text not null,
    confidence real,
    model text,
    approval_version text not null,
    prompt_version text,
    risk_reasons_json text not null default '[]',
    ai_reasons_json text not null default '[]',
    raw_json text
);

create index if not exists idx_entry_approvals_verdict_time
on entry_approvals(final_verdict, reviewed_at_ms desc);

create table if not exists positions (
    position_id text primary key,
    signal_id text references signals(signal_id),
    symbol text not null,
    side text not null check (side in ('LONG','SHORT')),
    status text not null,
    opened_at_ms integer,
    closed_at_ms integer,
    entry_price real,
    exit_price real,
    quantity real,
    stop_loss real,
    take_profit real,
    realized_pnl real,
    realized_pnl_pct real,
    close_reason text,
    mode text not null,
    raw_json text
);

create index if not exists idx_positions_status_time
on positions(status, opened_at_ms desc);

create table if not exists trade_events (
    event_id integer primary key autoincrement,
    signal_id text references signals(signal_id),
    position_id text references positions(position_id),
    event_type text not null,
    event_time_ms integer not null,
    payload_json text not null default '{}'
);

create index if not exists idx_trade_events_time
on trade_events(event_time_ms desc);
"""


POSTGRES_SCHEMA_SQL = """
create table if not exists signals (
    signal_id text primary key,
    symbol text not null,
    side text not null check (side in ('LONG','SHORT')),
    signal_time_ms bigint not null,
    signal_price double precision,
    stage text,
    long_score double precision,
    short_score double precision,
    score_edge double precision,
    volume_ratio double precision,
    structure_status text,
    taker_bias text,
    raw_oi_change_pct double precision,
    funding_rate double precision,
    market_regime text,
    decision_context_balance integer,
    decision_reasons_json text not null default '[]',
    snapshot_json text not null,
    first_seen_at_ms bigint not null,
    last_seen_at_ms bigint not null,
    persistence_version text not null
);

create index if not exists idx_signals_time
on signals(signal_time_ms desc);

create index if not exists idx_signals_symbol_time
on signals(symbol, signal_time_ms desc);

create index if not exists idx_signals_side_time
on signals(side, signal_time_ms desc);

create table if not exists signal_outcomes (
    signal_id text primary key references signals(signal_id) on delete cascade,
    status text not null default 'PENDING',
    updated_at_ms bigint not null,
    future_5m_return_pct double precision,
    future_15m_return_pct double precision,
    future_30m_return_pct double precision,
    future_1h_return_pct double precision,
    future_2h_return_pct double precision,
    mfe_15m_pct double precision,
    mae_15m_pct double precision,
    mfe_1h_pct double precision,
    mae_1h_pct double precision,
    mfe_2h_pct double precision,
    mae_2h_pct double precision,
    hit_0_5pct integer,
    hit_1pct integer,
    hit_2pct integer,
    time_to_0_5pct_minutes integer,
    time_to_1pct_minutes integer,
    time_to_2pct_minutes integer
);

create table if not exists ai_reviews (
    review_id bigserial primary key,
    signal_id text not null references signals(signal_id) on delete cascade,
    reviewed_at_ms bigint not null,
    verdict text,
    confidence text,
    model text,
    reasons_json text not null default '[]',
    raw_json text
);

create index if not exists idx_ai_reviews_signal_time
on ai_reviews(signal_id, reviewed_at_ms desc);

create table if not exists entry_approvals (
    signal_id text primary key references signals(signal_id) on delete cascade,
    reviewed_at_ms bigint not null,
    risk_verdict text not null,
    ai_verdict text not null,
    final_verdict text not null,
    confidence double precision,
    model text,
    approval_version text not null,
    prompt_version text,
    risk_reasons_json text not null default '[]',
    ai_reasons_json text not null default '[]',
    raw_json text
);

create index if not exists idx_entry_approvals_verdict_time
on entry_approvals(final_verdict, reviewed_at_ms desc);

create table if not exists positions (
    position_id text primary key,
    signal_id text references signals(signal_id),
    symbol text not null,
    side text not null check (side in ('LONG','SHORT')),
    status text not null,
    opened_at_ms bigint,
    closed_at_ms bigint,
    entry_price double precision,
    exit_price double precision,
    quantity double precision,
    stop_loss double precision,
    take_profit double precision,
    realized_pnl double precision,
    realized_pnl_pct double precision,
    close_reason text,
    mode text not null,
    raw_json text
);

create index if not exists idx_positions_status_time
on positions(status, opened_at_ms desc);

create table if not exists trade_events (
    event_id bigserial primary key,
    signal_id text references signals(signal_id),
    position_id text references positions(position_id),
    event_type text not null,
    event_time_ms bigint not null,
    payload_json text not null default '{}'
);

create index if not exists idx_trade_events_time
on trade_events(event_time_ms desc);

create table if not exists persistence_meta (
    key text primary key,
    value text,
    updated_at_ms bigint not null
);
"""


def database_path() -> Path:
    return Path(os.environ.get("BABABOT_DB_PATH", DEFAULT_DB_PATH))


def database_url() -> str | None:
    value = os.environ.get("DATABASE_URL")
    return value.strip() if value and value.strip() else None


def persistence_backend() -> str:
    return "postgres" if database_url() else "sqlite"


def _sqlite_connect(path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path is not None else database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma busy_timeout = 15000")
    try:
        conn.execute("pragma journal_mode = wal")
    except sqlite3.DatabaseError:
        pass
    return conn


def _postgres_connect():
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(url, connect_timeout=10)


def initialize_sqlite(
    path: str | os.PathLike[str] | None = None,
) -> Path:
    db_path = Path(path) if path is not None else database_path()
    with _sqlite_connect(db_path) as conn:
        conn.executescript(SQLITE_SCHEMA_SQL)
    return db_path


def initialize_postgres() -> None:
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(POSTGRES_SCHEMA_SQL)


def initialize_database(
    path: str | os.PathLike[str] | None = None,
) -> str | Path:
    if path is not None or persistence_backend() == "sqlite":
        return initialize_sqlite(path)
    initialize_postgres()
    migrate_sqlite_history_once()
    return "postgres"


def _price_map(scan: MarketScan) -> dict[str, float]:
    return {snapshot.symbol.upper(): snapshot.close for snapshot in scan.symbols}


def _signal_id(symbol: str, candle_close_time_ms: int, side: str) -> str:
    return f"{symbol.upper()}:{int(candle_close_time_ms)}:{side}"


def _candidate_payload(scan: MarketScan, candidate: Any, price: float | None) -> tuple[Any, ...]:
    ctx = candidate.market_context
    snapshot = asdict(candidate)
    reasons = list(candidate.decision_reasons or ())
    return (
        _signal_id(candidate.symbol, candidate.candle_close_time_ms, candidate.decision),
        candidate.symbol.upper(),
        candidate.decision,
        candidate.candle_close_time_ms,
        price,
        candidate.stage,
        candidate.long_score,
        candidate.short_score,
        candidate.score_edge,
        candidate.volume_ratio,
        ctx.structure_status if ctx else None,
        ctx.taker_bias if ctx else None,
        ctx.raw_oi_change_pct if ctx else None,
        ctx.funding_rate if ctx else None,
        ctx.market_regime if ctx else None,
        candidate.decision_context_balance,
        json.dumps(reasons, separators=(",", ":")),
        json.dumps(snapshot, separators=(",", ":"), allow_nan=False),
        scan.scan_finished_at_ms,
        scan.scan_finished_at_ms,
        PERSISTENCE_VERSION,
    )


def _record_sqlite(
    scan: MarketScan,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, int]:
    db_path = initialize_sqlite(path)
    prices = _price_map(scan)
    inserted = 0
    updated = 0

    with _sqlite_connect(db_path) as conn:
        for candidate in scan.moving_candidates:
            if candidate.decision not in {"LONG", "SHORT"}:
                continue
            values = _candidate_payload(scan, candidate, prices.get(candidate.symbol.upper()))
            signal_id = values[0]
            existed = conn.execute(
                "select 1 from signals where signal_id = ?",
                (signal_id,),
            ).fetchone() is not None
            conn.execute(
                """
                insert into signals (
                    signal_id, symbol, side, signal_time_ms, signal_price,
                    stage, long_score, short_score, score_edge, volume_ratio,
                    structure_status, taker_bias, raw_oi_change_pct,
                    funding_rate, market_regime, decision_context_balance,
                    decision_reasons_json, snapshot_json,
                    first_seen_at_ms, last_seen_at_ms, persistence_version
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(signal_id) do update set
                    last_seen_at_ms = excluded.last_seen_at_ms,
                    snapshot_json = excluded.snapshot_json,
                    persistence_version = excluded.persistence_version
                """,
                values,
            )
            if existed:
                updated += 1
            else:
                inserted += 1
                conn.execute(
                    """
                    insert or ignore into signal_outcomes (
                        signal_id, status, updated_at_ms
                    ) values (?, 'PENDING', ?)
                    """,
                    (signal_id, scan.scan_finished_at_ms),
                )
                conn.execute(
                    """
                    insert into trade_events (
                        signal_id, position_id, event_type,
                        event_time_ms, payload_json
                    ) values (?, null, 'SIGNAL_CREATED', ?, ?)
                    """,
                    (
                        signal_id,
                        scan.scan_finished_at_ms,
                        json.dumps(
                            {
                                "symbol": candidate.symbol.upper(),
                                "side": candidate.decision,
                                "stage": candidate.stage,
                                "signal_price": prices.get(candidate.symbol.upper()),
                                "long_score": candidate.long_score,
                                "short_score": candidate.short_score,
                            },
                            separators=(",", ":"),
                        ),
                    ),
                )
    return {"inserted": inserted, "updated": updated}


def _record_postgres(scan: MarketScan) -> dict[str, int]:
    initialize_postgres()
    migrate_sqlite_history_once()
    prices = _price_map(scan)
    inserted = 0
    updated = 0

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            for candidate in scan.moving_candidates:
                if candidate.decision not in {"LONG", "SHORT"}:
                    continue
                values = _candidate_payload(scan, candidate, prices.get(candidate.symbol.upper()))
                signal_id = values[0]
                cur.execute("select 1 from signals where signal_id = %s", (signal_id,))
                existed = cur.fetchone() is not None
                cur.execute(
                    """
                    insert into signals (
                        signal_id, symbol, side, signal_time_ms, signal_price,
                        stage, long_score, short_score, score_edge, volume_ratio,
                        structure_status, taker_bias, raw_oi_change_pct,
                        funding_rate, market_regime, decision_context_balance,
                        decision_reasons_json, snapshot_json,
                        first_seen_at_ms, last_seen_at_ms, persistence_version
                    ) values (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                    )
                    on conflict(signal_id) do update set
                        last_seen_at_ms = excluded.last_seen_at_ms,
                        snapshot_json = excluded.snapshot_json,
                        persistence_version = excluded.persistence_version
                    """,
                    values,
                )
                if existed:
                    updated += 1
                else:
                    inserted += 1
                    cur.execute(
                        """
                        insert into signal_outcomes (
                            signal_id, status, updated_at_ms
                        ) values (%s, 'PENDING', %s)
                        on conflict(signal_id) do nothing
                        """,
                        (signal_id, scan.scan_finished_at_ms),
                    )
                    cur.execute(
                        """
                        insert into trade_events (
                            signal_id, position_id, event_type,
                            event_time_ms, payload_json
                        ) values (%s, null, 'SIGNAL_CREATED', %s, %s)
                        """,
                        (
                            signal_id,
                            scan.scan_finished_at_ms,
                            json.dumps(
                                {
                                    "symbol": candidate.symbol.upper(),
                                    "side": candidate.decision,
                                    "stage": candidate.stage,
                                    "signal_price": prices.get(candidate.symbol.upper()),
                                    "long_score": candidate.long_score,
                                    "short_score": candidate.short_score,
                                },
                                separators=(",", ":"),
                            ),
                        ),
                    )
    return {"inserted": inserted, "updated": updated}


def record_actionable_signals(
    scan: MarketScan,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, int]:
    """Persist Stage 6 LONG/SHORT decisions exactly once.

    PostgreSQL is primary when DATABASE_URL is configured. SQLite remains a
    safe fallback when PostgreSQL is unavailable/not configured.
    """
    if path is not None or persistence_backend() == "sqlite":
        return _record_sqlite(scan, path)

    # PostgreSQL is the primary Stage 10 store. Keep SQLite on the persistent
    # Railway volume as a local safety copy so a temporary DB outage never
    # causes signal-history loss.
    try:
        primary = _record_postgres(scan)
    except Exception:
        return _record_sqlite(scan, database_path())

    try:
        _record_sqlite(scan, database_path())
    except Exception:
        pass
    return primary


def _sqlite_history_rows(
    path: str | os.PathLike[str],
) -> dict[str, list[dict[str, Any]]]:
    initialize_sqlite(path)
    tables = ["signals", "signal_outcomes", "ai_reviews", "positions", "trade_events"]
    result: dict[str, list[dict[str, Any]]] = {}
    with _sqlite_connect(path) as conn:
        for table in tables:
            result[table] = [dict(row) for row in conn.execute(f"select * from {table}")]
    return result


def migrate_sqlite_history_once() -> dict[str, int]:
    """Copy historical Stage 10 SQLite rows into PostgreSQL exactly once."""
    if persistence_backend() != "postgres":
        return {"migrated": 0}
    sqlite_path = database_path()
    if not sqlite_path.exists():
        return {"migrated": 0}

    initialize_postgres()
    marker = "sqlite_stage10_migration_complete"
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("select value from persistence_meta where key = %s", (marker,))
            if cur.fetchone() is not None:
                return {"migrated": 0}

    rows = _sqlite_history_rows(sqlite_path)
    migrated = 0
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            for row in rows["signals"]:
                cols = list(row)
                values = [row[c] for c in cols]
                placeholders = ",".join(["%s"] * len(cols))
                updates = ",".join(
                    f"{c}=excluded.{c}"
                    for c in cols
                    if c != "signal_id"
                )
                cur.execute(
                    f"""
                    insert into signals ({",".join(cols)})
                    values ({placeholders})
                    on conflict(signal_id) do update set {updates}
                    """,
                    values,
                )
                migrated += 1

            for row in rows["signal_outcomes"]:
                cols = list(row)
                vals = [row[c] for c in cols]
                placeholders = ",".join(["%s"] * len(cols))
                updates = ",".join(
                    f"{c}=excluded.{c}"
                    for c in cols
                    if c != "signal_id"
                )
                cur.execute(
                    f"""
                    insert into signal_outcomes ({",".join(cols)})
                    values ({placeholders})
                    on conflict(signal_id) do update set {updates}
                    """,
                    vals,
                )

            for row in rows["positions"]:
                cols = list(row)
                vals = [row[c] for c in cols]
                placeholders = ",".join(["%s"] * len(cols))
                updates = ",".join(
                    f"{c}=excluded.{c}"
                    for c in cols
                    if c != "position_id"
                )
                cur.execute(
                    f"""
                    insert into positions ({",".join(cols)})
                    values ({placeholders})
                    on conflict(position_id) do update set {updates}
                    """,
                    vals,
                )

            for row in rows["ai_reviews"]:
                cur.execute(
                    """
                    insert into ai_reviews (
                        signal_id, reviewed_at_ms, verdict, confidence,
                        model, reasons_json, raw_json
                    ) values (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        row["signal_id"], row["reviewed_at_ms"], row["verdict"],
                        row["confidence"], row["model"], row["reasons_json"],
                        row["raw_json"],
                    ),
                )

            for row in rows["trade_events"]:
                cur.execute(
                    """
                    insert into trade_events (
                        signal_id, position_id, event_type,
                        event_time_ms, payload_json
                    ) values (%s,%s,%s,%s,%s)
                    """,
                    (
                        row["signal_id"], row["position_id"], row["event_type"],
                        row["event_time_ms"], row["payload_json"],
                    ),
                )

            cur.execute(
                """
                insert into persistence_meta (key, value, updated_at_ms)
                values (%s,%s,%s)
                on conflict(key) do update set
                    value = excluded.value,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (marker, str(migrated), int(time.time() * 1000)),
            )
    return {"migrated": migrated}


def list_signals(
    *,
    path: str | os.PathLike[str] | None = None,
    limit: int = 100,
    symbol: str | None = None,
    side: str | None = None,
) -> list[dict[str, Any]]:
    if side:
        normalized = side.upper().replace("_", " ")
        if normalized not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        side = normalized

    safe_limit = max(1, min(int(limit), 500))

    if path is not None or persistence_backend() == "sqlite":
        db_path = initialize_sqlite(path)
        clauses: list[str] = []
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.upper())
        if side:
            clauses.append("side = ?")
            params.append(side)
        where = " where " + " and ".join(clauses) if clauses else ""
        params.append(safe_limit)
        with _sqlite_connect(db_path) as conn:
            rows = conn.execute(
                f"""
                select signal_id, symbol, side, signal_time_ms, signal_price,
                    stage, long_score, short_score, score_edge, volume_ratio,
                    structure_status, taker_bias, raw_oi_change_pct,
                    funding_rate, market_regime, decision_context_balance,
                    decision_reasons_json, first_seen_at_ms, last_seen_at_ms,
                    persistence_version
                from signals {where}
                order by signal_time_ms desc, signal_id
                limit ?
                """,
                tuple(params),
            ).fetchall()
            result = [dict(row) for row in rows]
    else:
        initialize_postgres()
        migrate_sqlite_history_once()
        clauses = []
        params = []
        if symbol:
            clauses.append("symbol = %s")
            params.append(symbol.upper())
        if side:
            clauses.append("side = %s")
            params.append(side)
        where = " where " + " and ".join(clauses) if clauses else ""
        params.append(safe_limit)
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""
                    select signal_id, symbol, side, signal_time_ms, signal_price,
                        stage, long_score, short_score, score_edge, volume_ratio,
                        structure_status, taker_bias, raw_oi_change_pct,
                        funding_rate, market_regime, decision_context_balance,
                        decision_reasons_json, first_seen_at_ms, last_seen_at_ms,
                        persistence_version
                    from signals {where}
                    order by signal_time_ms desc, signal_id
                    limit %s
                    """,
                    tuple(params),
                )
                result = [dict(row) for row in cur.fetchall()]

    for item in result:
        item["decision_reasons"] = json.loads(
            item.pop("decision_reasons_json") or "[]"
        )
    return result


def persistence_summary(
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    if path is not None or persistence_backend() == "sqlite":
        db_path = initialize_sqlite(path)
        with _sqlite_connect(db_path) as conn:
            values = {
                "signal_count": conn.execute("select count(*) from signals").fetchone()[0],
                "long_count": conn.execute("select count(*) from signals where side='LONG'").fetchone()[0],
                "short_count": conn.execute("select count(*) from signals where side='SHORT'").fetchone()[0],
                "pending_outcomes": conn.execute("select count(*) from signal_outcomes where status='PENDING'").fetchone()[0],
                "position_count": conn.execute("select count(*) from positions").fetchone()[0],
                "trade_event_count": conn.execute("select count(*) from trade_events").fetchone()[0],
                "first_signal_time_ms": conn.execute("select min(signal_time_ms) from signals").fetchone()[0],
                "last_signal_time_ms": conn.execute("select max(signal_time_ms) from signals").fetchone()[0],
            }
        return {
            "persistence_version": PERSISTENCE_VERSION,
            "backend": "sqlite",
            "database_path": str(db_path),
            **values,
        }

    initialize_postgres()
    migration = migrate_sqlite_history_once()
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            queries = {
                "signal_count": "select count(*) from signals",
                "long_count": "select count(*) from signals where side='LONG'",
                "short_count": "select count(*) from signals where side='SHORT'",
                "pending_outcomes": "select count(*) from signal_outcomes where status='PENDING'",
                "position_count": "select count(*) from positions",
                "trade_event_count": "select count(*) from trade_events",
                "first_signal_time_ms": "select min(signal_time_ms) from signals",
                "last_signal_time_ms": "select max(signal_time_ms) from signals",
            }
            values: dict[str, Any] = {}
            for key, query in queries.items():
                cur.execute(query)
                values[key] = cur.fetchone()[0]
    return {
        "persistence_version": PERSISTENCE_VERSION,
        "backend": "postgres",
        "sqlite_migrated_this_call": migration["migrated"],
        **values,
    }



def get_pending_entry_signals(
    *,
    max_age_ms: int,
    limit: int = 12,
    now_ms: int | None = None,
    path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    """Return fresh actionable signals that do not yet have a Stage 11 review."""
    current_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    cutoff = current_ms - max(1, int(max_age_ms))
    retry_before = current_ms - 60_000
    safe_limit = max(1, min(int(limit), 100))

    if path is not None or persistence_backend() == "sqlite":
        db_path = initialize_sqlite(path)
        with _sqlite_connect(db_path) as conn:
            rows = conn.execute(
                """
                select s.*
                from signals s
                left join entry_approvals a on a.signal_id = s.signal_id
                where (
                        a.signal_id is null
                        or (a.ai_verdict = 'ERROR' and a.reviewed_at_ms <= ?)
                      )
                  and s.signal_time_ms >= ?
                order by s.signal_time_ms asc, s.signal_id
                limit ?
                """,
                (retry_before, cutoff, safe_limit),
            ).fetchall()
            return [dict(row) for row in rows]

    initialize_postgres()
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select s.*
                from signals s
                left join entry_approvals a on a.signal_id = s.signal_id
                where (
                        a.signal_id is null
                        or (a.ai_verdict = 'ERROR' and a.reviewed_at_ms <= %s)
                      )
                  and s.signal_time_ms >= %s
                order by s.signal_time_ms asc, s.signal_id
                limit %s
                """,
                (retry_before, cutoff, safe_limit),
            )
            return [dict(row) for row in cur.fetchall()]


def save_entry_approval(
    *,
    signal_id: str,
    reviewed_at_ms: int,
    risk_verdict: str,
    ai_verdict: str,
    final_verdict: str,
    confidence: float | None,
    model: str | None,
    approval_version: str,
    prompt_version: str | None,
    risk_reasons: list[str],
    ai_reasons: list[str],
    raw: dict[str, Any],
    path: str | os.PathLike[str] | None = None,
) -> None:
    """Persist one idempotent Stage 11 entry approval."""
    risk_json = json.dumps(risk_reasons, separators=(",", ":"))
    ai_json = json.dumps(ai_reasons, separators=(",", ":"))
    raw_json = json.dumps(raw, separators=(",", ":"), allow_nan=False)

    if path is not None or persistence_backend() == "sqlite":
        db_path = initialize_sqlite(path)
        with _sqlite_connect(db_path) as conn:
            conn.execute(
                """
                insert into entry_approvals (
                    signal_id, reviewed_at_ms, risk_verdict, ai_verdict,
                    final_verdict, confidence, model, approval_version,
                    prompt_version, risk_reasons_json, ai_reasons_json, raw_json
                ) values (?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(signal_id) do update set
                    reviewed_at_ms=excluded.reviewed_at_ms,
                    risk_verdict=excluded.risk_verdict,
                    ai_verdict=excluded.ai_verdict,
                    final_verdict=excluded.final_verdict,
                    confidence=excluded.confidence,
                    model=excluded.model,
                    approval_version=excluded.approval_version,
                    prompt_version=excluded.prompt_version,
                    risk_reasons_json=excluded.risk_reasons_json,
                    ai_reasons_json=excluded.ai_reasons_json,
                    raw_json=excluded.raw_json
                """,
                (
                    signal_id, reviewed_at_ms, risk_verdict, ai_verdict,
                    final_verdict, confidence, model, approval_version,
                    prompt_version, risk_json, ai_json, raw_json,
                ),
            )
            if ai_verdict not in {"NOT_CALLED", "ERROR"}:
                conn.execute(
                    """
                    insert into ai_reviews (
                        signal_id, reviewed_at_ms, verdict, confidence,
                        model, reasons_json, raw_json
                    ) values (?,?,?,?,?,?,?)
                    """,
                    (
                        signal_id, reviewed_at_ms, ai_verdict,
                        None if confidence is None else str(confidence),
                        model, ai_json, raw_json,
                    ),
                )
            conn.execute(
                """
                insert into trade_events (
                    signal_id, position_id, event_type,
                    event_time_ms, payload_json
                ) values (?, null, 'ENTRY_APPROVAL_COMPLETED', ?, ?)
                """,
                (
                    signal_id,
                    reviewed_at_ms,
                    json.dumps(
                        {
                            "risk_verdict": risk_verdict,
                            "ai_verdict": ai_verdict,
                            "final_verdict": final_verdict,
                            "confidence": confidence,
                            "approval_version": approval_version,
                        },
                        separators=(",", ":"),
                    ),
                ),
            )
        return

    initialize_postgres()
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into entry_approvals (
                    signal_id, reviewed_at_ms, risk_verdict, ai_verdict,
                    final_verdict, confidence, model, approval_version,
                    prompt_version, risk_reasons_json, ai_reasons_json, raw_json
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(signal_id) do update set
                    reviewed_at_ms=excluded.reviewed_at_ms,
                    risk_verdict=excluded.risk_verdict,
                    ai_verdict=excluded.ai_verdict,
                    final_verdict=excluded.final_verdict,
                    confidence=excluded.confidence,
                    model=excluded.model,
                    approval_version=excluded.approval_version,
                    prompt_version=excluded.prompt_version,
                    risk_reasons_json=excluded.risk_reasons_json,
                    ai_reasons_json=excluded.ai_reasons_json,
                    raw_json=excluded.raw_json
                """,
                (
                    signal_id, reviewed_at_ms, risk_verdict, ai_verdict,
                    final_verdict, confidence, model, approval_version,
                    prompt_version, risk_json, ai_json, raw_json,
                ),
            )
            if ai_verdict not in {"NOT_CALLED", "ERROR"}:
                cur.execute(
                    """
                    insert into ai_reviews (
                        signal_id, reviewed_at_ms, verdict, confidence,
                        model, reasons_json, raw_json
                    ) values (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        signal_id, reviewed_at_ms, ai_verdict,
                        None if confidence is None else str(confidence),
                        model, ai_json, raw_json,
                    ),
                )
            cur.execute(
                """
                insert into trade_events (
                    signal_id, position_id, event_type,
                    event_time_ms, payload_json
                ) values (%s, null, 'ENTRY_APPROVAL_COMPLETED', %s, %s)
                """,
                (
                    signal_id,
                    reviewed_at_ms,
                    json.dumps(
                        {
                            "risk_verdict": risk_verdict,
                            "ai_verdict": ai_verdict,
                            "final_verdict": final_verdict,
                            "confidence": confidence,
                            "approval_version": approval_version,
                        },
                        separators=(",", ":"),
                    ),
                ),
            )

    # Maintain the SQLite volume as the Stage 10/11 safety ledger too.
    try:
        save_entry_approval(
            signal_id=signal_id,
            reviewed_at_ms=reviewed_at_ms,
            risk_verdict=risk_verdict,
            ai_verdict=ai_verdict,
            final_verdict=final_verdict,
            confidence=confidence,
            model=model,
            approval_version=approval_version,
            prompt_version=prompt_version,
            risk_reasons=risk_reasons,
            ai_reasons=ai_reasons,
            raw=raw,
            path=database_path(),
        )
    except Exception:
        pass


def list_entry_approvals(
    *,
    limit: int = 100,
    verdict: str | None = None,
    path: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 500))
    normalized = verdict.upper() if verdict else None
    if normalized and normalized not in {"APPROVE", "VETO", "WATCH"}:
        raise ValueError("verdict must be APPROVE, VETO, or WATCH")

    if path is not None or persistence_backend() == "sqlite":
        db_path = initialize_sqlite(path)
        query = """
            select a.*, s.symbol, s.side, s.signal_time_ms, s.signal_price,
                   s.stage, s.long_score, s.short_score, s.score_edge
            from entry_approvals a
            join signals s on s.signal_id = a.signal_id
        """
        params: list[Any] = []
        if normalized:
            query += " where a.final_verdict = ?"
            params.append(normalized)
        query += " order by a.reviewed_at_ms desc limit ?"
        params.append(safe_limit)
        with _sqlite_connect(db_path) as conn:
            rows = [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]
    else:
        initialize_postgres()
        query = """
            select a.*, s.symbol, s.side, s.signal_time_ms, s.signal_price,
                   s.stage, s.long_score, s.short_score, s.score_edge
            from entry_approvals a
            join signals s on s.signal_id = a.signal_id
        """
        params = []
        if normalized:
            query += " where a.final_verdict = %s"
            params.append(normalized)
        query += " order by a.reviewed_at_ms desc limit %s"
        params.append(safe_limit)
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, tuple(params))
                rows = [dict(row) for row in cur.fetchall()]

    for row in rows:
        row["risk_reasons"] = json.loads(row.pop("risk_reasons_json") or "[]")
        row["ai_reasons"] = json.loads(row.pop("ai_reasons_json") or "[]")
        if row.get("raw_json"):
            try:
                row["raw"] = json.loads(row.pop("raw_json"))
            except Exception:
                row["raw"] = row.pop("raw_json")
    return rows


def entry_approval_summary(
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    if path is not None or persistence_backend() == "sqlite":
        db_path = initialize_sqlite(path)
        with _sqlite_connect(db_path) as conn:
            total = conn.execute("select count(*) from entry_approvals").fetchone()[0]
            approve = conn.execute("select count(*) from entry_approvals where final_verdict='APPROVE'").fetchone()[0]
            veto = conn.execute("select count(*) from entry_approvals where final_verdict='VETO'").fetchone()[0]
            watch = conn.execute("select count(*) from entry_approvals where final_verdict='WATCH'").fetchone()[0]
        backend = "sqlite"
    else:
        initialize_postgres()
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from entry_approvals")
                total = cur.fetchone()[0]
                cur.execute("select count(*) from entry_approvals where final_verdict='APPROVE'")
                approve = cur.fetchone()[0]
                cur.execute("select count(*) from entry_approvals where final_verdict='VETO'")
                veto = cur.fetchone()[0]
                cur.execute("select count(*) from entry_approvals where final_verdict='WATCH'")
                watch = cur.fetchone()[0]
        backend = "postgres"
    return {
        "backend": backend,
        "total_reviews": total,
        "approve_count": approve,
        "veto_count": veto,
        "watch_count": watch,
    }
