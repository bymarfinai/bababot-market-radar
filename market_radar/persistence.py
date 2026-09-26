from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import MarketScan


PERSISTENCE_VERSION = "stage10-v1"
DEFAULT_DB_PATH = "data/market_radar.sqlite3"


SCHEMA_SQL = """
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


def database_path() -> Path:
    return Path(os.environ.get("BABABOT_DB_PATH", DEFAULT_DB_PATH))


def _connect(path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
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


def initialize_database(
    path: str | os.PathLike[str] | None = None,
) -> Path:
    db_path = Path(path) if path is not None else database_path()
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    return db_path


def _price_map(scan: MarketScan) -> dict[str, float]:
    return {snapshot.symbol.upper(): snapshot.close for snapshot in scan.symbols}


def _signal_id(symbol: str, candle_close_time_ms: int, side: str) -> str:
    return f"{symbol.upper()}:{int(candle_close_time_ms)}:{side}"


def record_actionable_signals(
    scan: MarketScan,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, int]:
    """Persist Stage 6 LONG/SHORT decisions exactly once.

    NO TRADE never enters the signal ledger. Re-processing the same closed
    candle updates last_seen_at_ms but cannot duplicate the signal.
    """
    db_path = initialize_database(path)
    prices = _price_map(scan)
    inserted = 0
    updated = 0

    with _connect(db_path) as conn:
        for candidate in scan.moving_candidates:
            side = candidate.decision
            if side not in {"LONG", "SHORT"}:
                continue

            symbol = candidate.symbol.upper()
            signal_id = _signal_id(
                symbol,
                candidate.candle_close_time_ms,
                side,
            )
            ctx = candidate.market_context
            snapshot = asdict(candidate)
            reasons = list(candidate.decision_reasons or ())
            price = prices.get(symbol)

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
                    snapshot_json = excluded.snapshot_json
                """,
                (
                    signal_id,
                    symbol,
                    side,
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
                ),
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
                                "symbol": symbol,
                                "side": side,
                                "stage": candidate.stage,
                                "signal_price": price,
                                "long_score": candidate.long_score,
                                "short_score": candidate.short_score,
                            },
                            separators=(",", ":"),
                        ),
                    ),
                )

    return {"inserted": inserted, "updated": updated}


def list_signals(
    *,
    path: str | os.PathLike[str] | None = None,
    limit: int = 100,
    symbol: str | None = None,
    side: str | None = None,
) -> list[dict[str, Any]]:
    db_path = initialize_database(path)
    clauses: list[str] = []
    params: list[Any] = []

    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol.upper())
    if side:
        normalized = side.upper().replace("_", " ")
        if normalized not in {"LONG", "SHORT"}:
            raise ValueError("side must be LONG or SHORT")
        clauses.append("side = ?")
        params.append(normalized)

    where = " where " + " and ".join(clauses) if clauses else ""
    safe_limit = max(1, min(int(limit), 500))
    params.append(safe_limit)

    with _connect(db_path) as conn:
        rows = conn.execute(
            f"""
            select
                signal_id, symbol, side, signal_time_ms, signal_price,
                stage, long_score, short_score, score_edge, volume_ratio,
                structure_status, taker_bias, raw_oi_change_pct,
                funding_rate, market_regime, decision_context_balance,
                decision_reasons_json, first_seen_at_ms, last_seen_at_ms,
                persistence_version
            from signals
            {where}
            order by signal_time_ms desc, signal_id
            limit ?
            """,
            tuple(params),
        ).fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["decision_reasons"] = json.loads(
            item.pop("decision_reasons_json") or "[]"
        )
        result.append(item)
    return result


def persistence_summary(
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    db_path = initialize_database(path)
    with _connect(db_path) as conn:
        signal_count = conn.execute(
            "select count(*) from signals"
        ).fetchone()[0]
        long_count = conn.execute(
            "select count(*) from signals where side = 'LONG'"
        ).fetchone()[0]
        short_count = conn.execute(
            "select count(*) from signals where side = 'SHORT'"
        ).fetchone()[0]
        pending_outcomes = conn.execute(
            "select count(*) from signal_outcomes where status = 'PENDING'"
        ).fetchone()[0]
        position_count = conn.execute(
            "select count(*) from positions"
        ).fetchone()[0]
        event_count = conn.execute(
            "select count(*) from trade_events"
        ).fetchone()[0]
        first_signal = conn.execute(
            "select min(signal_time_ms) from signals"
        ).fetchone()[0]
        last_signal = conn.execute(
            "select max(signal_time_ms) from signals"
        ).fetchone()[0]

    return {
        "persistence_version": PERSISTENCE_VERSION,
        "database_path": str(db_path),
        "signal_count": signal_count,
        "long_count": long_count,
        "short_count": short_count,
        "pending_outcomes": pending_outcomes,
        "position_count": position_count,
        "trade_event_count": event_count,
        "first_signal_time_ms": first_signal,
        "last_signal_time_ms": last_signal,
    }
