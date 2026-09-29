from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import psycopg2.extras

from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    initialize_database,
    persistence_backend,
)


COHORT_VERSION = "entry-rebuild-cohort-v1"
PRE_COHORT = "PRE_ENTRY_REBUILD"
POST_COHORT = "POST_ENTRY_REBUILD"

# Official production boundary: Stage 13 V2 deployment resumed RUN.
DEFAULT_BOUNDARY_MS = 1790655250219

POST_STACK = {
    "decision_version": "stage6-v2-directional-context",
    "persistence_version": "stage10-v3-entry-latency",
    "approval_version": "stage11-v3-fast-pool",
    "failover_version": "stage11b-v3-failover-only",
    "fresh_gate_version": "stage11c-v1-fresh-direction",
    "paper_trading_version": "stage13-v2-event-driven",
}

_LOCK = threading.Lock()
_READY: set[tuple[str, str]] = set()

SQLITE_SCHEMA = """
create table if not exists pipeline_cohorts (
    signal_id text primary key references signals(signal_id) on delete cascade,
    cohort text not null check(cohort in ('PRE_ENTRY_REBUILD','POST_ENTRY_REBUILD')),
    boundary_ms integer not null,
    position_opened_at_ms integer,
    decision_version text,
    persistence_version text,
    approval_version text,
    failover_version text,
    fresh_gate_version text,
    paper_trading_version text,
    cohort_version text not null,
    labeled_at_ms integer not null,
    metadata_json text not null default '{}'
);
create index if not exists idx_pipeline_cohorts_cohort_opened
on pipeline_cohorts(cohort, position_opened_at_ms desc);
"""

POSTGRES_SCHEMA = """
create table if not exists pipeline_cohorts (
    signal_id text primary key references signals(signal_id) on delete cascade,
    cohort text not null check(cohort in ('PRE_ENTRY_REBUILD','POST_ENTRY_REBUILD')),
    boundary_ms bigint not null,
    position_opened_at_ms bigint,
    decision_version text,
    persistence_version text,
    approval_version text,
    failover_version text,
    fresh_gate_version text,
    paper_trading_version text,
    cohort_version text not null,
    labeled_at_ms bigint not null,
    metadata_json text not null default '{}'
);
create index if not exists idx_pipeline_cohorts_cohort_opened
on pipeline_cohorts(cohort, position_opened_at_ms desc);
"""


def boundary_ms() -> int:
    return int(os.environ.get("ENTRY_REBUILD_COHORT_BOUNDARY_MS", str(DEFAULT_BOUNDARY_MS)))


def _initialize() -> None:
    initialize_database()
    backend = persistence_backend()
    key = (
        ("sqlite", str(database_path().resolve()))
        if backend == "sqlite"
        else ("postgres", "primary")
    )
    with _LOCK:
        if key in _READY:
            return
        if backend == "sqlite":
            with _sqlite_connect(database_path()) as conn:
                conn.executescript(SQLITE_SCHEMA)
        else:
            with _postgres_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(POSTGRES_SCHEMA)
        _READY.add(key)


def cohort_for_opened_at(opened_at_ms: int | None) -> str:
    if opened_at_ms is None:
        raise ValueError("opened_at_ms is required for entry cohort classification")
    return POST_COHORT if int(opened_at_ms) >= boundary_ms() else PRE_COHORT


def label_signal_cohort(
    signal_id: str,
    *,
    opened_at_ms: int,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _initialize()
    cohort = cohort_for_opened_at(opened_at_ms)
    now_ms = int(time.time() * 1000)
    stack = POST_STACK if cohort == POST_COHORT else {
        "decision_version": "legacy_or_mixed",
        "persistence_version": "legacy_or_mixed",
        "approval_version": "legacy_or_mixed",
        "failover_version": "legacy_or_mixed",
        "fresh_gate_version": "legacy_or_mixed",
        "paper_trading_version": "legacy_or_mixed",
    }
    raw = json.dumps(metadata or {}, separators=(",", ":"), allow_nan=False)
    values = (
        signal_id,
        cohort,
        boundary_ms(),
        int(opened_at_ms),
        stack["decision_version"],
        stack["persistence_version"],
        stack["approval_version"],
        stack["failover_version"],
        stack["fresh_gate_version"],
        stack["paper_trading_version"],
        COHORT_VERSION,
        now_ms,
        raw,
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                insert into pipeline_cohorts (
                    signal_id, cohort, boundary_ms, position_opened_at_ms,
                    decision_version, persistence_version, approval_version,
                    failover_version, fresh_gate_version, paper_trading_version,
                    cohort_version, labeled_at_ms, metadata_json
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(signal_id) do update set
                    cohort=excluded.cohort,
                    boundary_ms=excluded.boundary_ms,
                    position_opened_at_ms=excluded.position_opened_at_ms,
                    decision_version=excluded.decision_version,
                    persistence_version=excluded.persistence_version,
                    approval_version=excluded.approval_version,
                    failover_version=excluded.failover_version,
                    fresh_gate_version=excluded.fresh_gate_version,
                    paper_trading_version=excluded.paper_trading_version,
                    cohort_version=excluded.cohort_version,
                    labeled_at_ms=excluded.labeled_at_ms,
                    metadata_json=excluded.metadata_json
                """,
                values,
            )
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into pipeline_cohorts (
                        signal_id, cohort, boundary_ms, position_opened_at_ms,
                        decision_version, persistence_version, approval_version,
                        failover_version, fresh_gate_version, paper_trading_version,
                        cohort_version, labeled_at_ms, metadata_json
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict(signal_id) do update set
                        cohort=excluded.cohort,
                        boundary_ms=excluded.boundary_ms,
                        position_opened_at_ms=excluded.position_opened_at_ms,
                        decision_version=excluded.decision_version,
                        persistence_version=excluded.persistence_version,
                        approval_version=excluded.approval_version,
                        failover_version=excluded.failover_version,
                        fresh_gate_version=excluded.fresh_gate_version,
                        paper_trading_version=excluded.paper_trading_version,
                        cohort_version=excluded.cohort_version,
                        labeled_at_ms=excluded.labeled_at_ms,
                        metadata_json=excluded.metadata_json
                    """,
                    values,
                )
    return {
        "signal_id": signal_id,
        "cohort": cohort,
        "boundary_ms": boundary_ms(),
        "position_opened_at_ms": int(opened_at_ms),
        **stack,
        "cohort_version": COHORT_VERSION,
    }


def backfill_position_cohorts() -> dict[str, int]:
    """Classify every persisted position using its actual opened_at_ms."""
    _initialize()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                """
                select signal_id, min(opened_at_ms) as opened_at_ms
                from positions
                where signal_id is not null and opened_at_ms is not null
                group by signal_id
                """
            ).fetchall()
            data = [dict(row) for row in rows]
    else:
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    select signal_id, min(opened_at_ms) as opened_at_ms
                    from positions
                    where signal_id is not null and opened_at_ms is not null
                    group by signal_id
                    """
                )
                data = [dict(row) for row in cur.fetchall()]

    counts = {PRE_COHORT: 0, POST_COHORT: 0}
    for row in data:
        result = label_signal_cohort(
            str(row["signal_id"]),
            opened_at_ms=int(row["opened_at_ms"]),
            metadata={"source": "position_backfill"},
        )
        counts[result["cohort"]] += 1
    return counts


def list_cohorts(
    *,
    cohort: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    _initialize()
    safe_limit = max(1, min(int(limit), 5000))
    cohort_clean = str(cohort or "").upper() or None
    if cohort_clean and cohort_clean not in {PRE_COHORT, POST_COHORT}:
        raise ValueError(f"invalid cohort: {cohort}")

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            if cohort_clean:
                rows = conn.execute(
                    """
                    select c.*, s.symbol, s.side,
                           p.position_id, p.mode, p.status,
                           p.closed_at_ms, p.realized_pnl, p.realized_pnl_pct
                    from pipeline_cohorts c
                    join signals s on s.signal_id=c.signal_id
                    left join positions p on p.signal_id=c.signal_id
                    where c.cohort=?
                    order by c.position_opened_at_ms desc
                    limit ?
                    """,
                    (cohort_clean, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    select c.*, s.symbol, s.side,
                           p.position_id, p.mode, p.status,
                           p.closed_at_ms, p.realized_pnl, p.realized_pnl_pct
                    from pipeline_cohorts c
                    join signals s on s.signal_id=c.signal_id
                    left join positions p on p.signal_id=c.signal_id
                    order by c.position_opened_at_ms desc
                    limit ?
                    """,
                    (safe_limit,),
                ).fetchall()
            out = [dict(row) for row in rows]
    else:
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if cohort_clean:
                    cur.execute(
                        """
                        select c.*, s.symbol, s.side,
                               p.position_id, p.mode, p.status,
                               p.closed_at_ms, p.realized_pnl, p.realized_pnl_pct
                        from pipeline_cohorts c
                        join signals s on s.signal_id=c.signal_id
                        left join positions p on p.signal_id=c.signal_id
                        where c.cohort=%s
                        order by c.position_opened_at_ms desc
                        limit %s
                        """,
                        (cohort_clean, safe_limit),
                    )
                else:
                    cur.execute(
                        """
                        select c.*, s.symbol, s.side,
                               p.position_id, p.mode, p.status,
                               p.closed_at_ms, p.realized_pnl, p.realized_pnl_pct
                        from pipeline_cohorts c
                        join signals s on s.signal_id=c.signal_id
                        left join positions p on p.signal_id=c.signal_id
                        order by c.position_opened_at_ms desc
                        limit %s
                        """,
                        (safe_limit,),
                    )
                out = [dict(row) for row in cur.fetchall()]
    for row in out:
        try:
            row["metadata"] = json.loads(row.pop("metadata_json") or "{}")
        except Exception:
            row["metadata"] = {}
    return out


def cohort_summary() -> dict[str, Any]:
    _initialize()
    query = """
        select
            c.cohort,
            count(distinct c.signal_id) as trades,
            count(distinct case when p.status='CLOSED' then p.position_id end) as closed,
            count(distinct case when p.status in ('OPEN','REDUCED') then p.position_id end) as active,
            coalesce(sum(case when p.status='CLOSED' and p.realized_pnl > 0 then 1 else 0 end),0) as wins,
            coalesce(sum(case when p.status='CLOSED' and p.realized_pnl <= 0 then 1 else 0 end),0) as losses,
            coalesce(sum(case when p.status='CLOSED' then p.realized_pnl else 0 end),0) as net_pnl
        from pipeline_cohorts c
        left join positions p on p.signal_id=c.signal_id and p.mode='PAPER'
        group by c.cohort
        order by c.cohort
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = [dict(row) for row in conn.execute(query).fetchall()]
    else:
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query)
                rows = [dict(row) for row in cur.fetchall()]

    for row in rows:
        closed = int(row["closed"] or 0)
        wins = int(row["wins"] or 0)
        row["win_rate_pct"] = round(100.0 * wins / closed, 4) if closed else None

    return {
        "cohort_version": COHORT_VERSION,
        "boundary_ms": boundary_ms(),
        "pre_cohort": PRE_COHORT,
        "post_cohort": POST_COHORT,
        "post_stack": POST_STACK,
        "cohorts": rows,
    }
