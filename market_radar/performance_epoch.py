from __future__ import annotations

import time
import threading
from typing import Any

import psycopg2.extras

from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    initialize_database,
    persistence_backend,
)

PERFORMANCE_EPOCH_VERSION = "performance-epoch-v2-history"
_LOCK = threading.Lock()
_READY: set[tuple[str, str]] = set()

SQLITE_SCHEMA = """
create table if not exists performance_epochs (
    epoch_id text primary key,
    label text not null,
    note text not null default '',
    started_at_ms integer not null,
    ended_at_ms integer,
    active integer not null default 1,
    version text not null,
    created_at_ms integer not null
);
create index if not exists idx_performance_epochs_active_started
on performance_epochs(active, started_at_ms desc);
"""

POSTGRES_SCHEMA = """
create table if not exists performance_epochs (
    epoch_id text primary key,
    label text not null,
    note text not null default '',
    started_at_ms bigint not null,
    ended_at_ms bigint,
    active boolean not null default true,
    version text not null,
    created_at_ms bigint not null
);
create index if not exists idx_performance_epochs_active_started
on performance_epochs(active, started_at_ms desc);
"""


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


def _normalize(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    out = dict(row)
    out["started_at_ms"] = int(out["started_at_ms"])
    out["created_at_ms"] = int(out["created_at_ms"])
    out["ended_at_ms"] = (
        int(out["ended_at_ms"]) if out.get("ended_at_ms") is not None else None
    )
    out["active"] = bool(out.get("active"))
    return out


def get_performance_epoch() -> dict[str, Any] | None:
    _initialize()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                """
                select * from performance_epochs
                where active=1
                order by started_at_ms desc
                limit 1
                """
            ).fetchone()
            return _normalize(dict(row) if row else None)
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select * from performance_epochs
                where active=true
                order by started_at_ms desc
                limit 1
                """
            )
            return _normalize(cur.fetchone())


def list_performance_epochs(limit: int = 50) -> list[dict[str, Any]]:
    _initialize()
    safe_limit = max(1, min(int(limit), 500))
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(
                """
                select * from performance_epochs
                order by started_at_ms desc
                limit ?
                """,
                (safe_limit,),
            ).fetchall()
            return [_normalize(dict(row)) for row in rows]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select * from performance_epochs
                order by started_at_ms desc
                limit %s
                """,
                (safe_limit,),
            )
            return [_normalize(row) for row in cur.fetchall()]


def start_performance_epoch(
    *,
    label: str,
    note: str | None = None,
    started_at_ms: int | None = None,
) -> dict[str, Any]:
    _initialize()
    started = int(started_at_ms if started_at_ms is not None else time.time() * 1000)
    created = int(time.time() * 1000)
    epoch_id = f"RUN-{started}"
    clean_label = str(label).strip() or epoch_id
    clean_note = str(note or "").strip()

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update performance_epochs
                set active=0, ended_at_ms=coalesce(ended_at_ms, ?)
                where active=1
                """,
                (started,),
            )
            conn.execute(
                """
                insert into performance_epochs (
                    epoch_id,label,note,started_at_ms,ended_at_ms,
                    active,version,created_at_ms
                ) values (?,?,?,?,?,?,?,?)
                """,
                (
                    epoch_id, clean_label, clean_note, started, None,
                    1, PERFORMANCE_EPOCH_VERSION, created,
                ),
            )
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update performance_epochs
                    set active=false, ended_at_ms=coalesce(ended_at_ms, %s)
                    where active=true
                    """,
                    (started,),
                )
                cur.execute(
                    """
                    insert into performance_epochs (
                        epoch_id,label,note,started_at_ms,ended_at_ms,
                        active,version,created_at_ms
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        epoch_id, clean_label, clean_note, started, None,
                        True, PERFORMANCE_EPOCH_VERSION, created,
                    ),
                )

    return {
        "epoch_id": epoch_id,
        "label": clean_label,
        "note": clean_note,
        "started_at_ms": started,
        "ended_at_ms": None,
        "active": True,
        "version": PERFORMANCE_EPOCH_VERSION,
        "created_at_ms": created,
    }
