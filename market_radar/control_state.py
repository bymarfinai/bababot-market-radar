from __future__ import annotations

import os
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


CONTROL_VERSION = "stage14-control-v1"
_VALID_MODES = {"RUN", "PAUSE_ENTRIES", "EXIT_ONLY"}

SQLITE_SCHEMA = """
create table if not exists control_state (
    control_id integer primary key check(control_id=1),
    mode text not null,
    updated_at_ms integer not null,
    note text,
    control_version text not null
);
insert or ignore into control_state (
    control_id, mode, updated_at_ms, note, control_version
) values (1, 'RUN', 0, 'default', 'stage14-control-v1');
"""

POSTGRES_SCHEMA = """
create table if not exists control_state (
    control_id integer primary key check(control_id=1),
    mode text not null,
    updated_at_ms bigint not null,
    note text,
    control_version text not null
);
insert into control_state (
    control_id, mode, updated_at_ms, note, control_version
) values (1, 'RUN', 0, 'default', 'stage14-control-v1')
on conflict(control_id) do nothing;
"""


def initialize_control_state() -> None:
    initialize_database()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.executescript(SQLITE_SCHEMA)
        return
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(POSTGRES_SCHEMA)


def get_control_state() -> dict[str, Any]:
    initialize_control_state()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                """
                select control_id, mode, updated_at_ms, note, control_version
                from control_state where control_id=1
                """
            ).fetchone()
            data = dict(row)
    else:
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    select control_id, mode, updated_at_ms, note, control_version
                    from control_state where control_id=1
                    """
                )
                data = dict(cur.fetchone())

    mode = str(data.get("mode") or "RUN").upper()
    data["mode"] = mode
    data["entries_enabled"] = mode == "RUN"
    data["lifecycle_exits_enabled"] = True
    data["live_order_submission_enabled"] = False
    data["paper_trading_env_enabled"] = (
        os.environ.get("PAPER_TRADING_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    return data


def set_control_mode(mode: str, *, note: str | None = None) -> dict[str, Any]:
    initialize_control_state()
    wanted = str(mode or "").strip().upper()
    if wanted not in _VALID_MODES:
        raise ValueError(
            "mode must be RUN, PAUSE_ENTRIES, or EXIT_ONLY"
        )

    now_ms = int(time.time() * 1000)
    clean_note = (note or "").strip()[:240] or None

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update control_state
                set mode=?, updated_at_ms=?, note=?, control_version=?
                where control_id=1
                """,
                (wanted, now_ms, clean_note, CONTROL_VERSION),
            )
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update control_state
                    set mode=%s, updated_at_ms=%s, note=%s, control_version=%s
                    where control_id=1
                    """,
                    (wanted, now_ms, clean_note, CONTROL_VERSION),
                )

    # Safety copy only; failure must not block primary control write.
    if persistence_backend() == "postgres":
        try:
            initialize_database(database_path())
            with _sqlite_connect(database_path()) as conn:
                conn.executescript(SQLITE_SCHEMA)
                conn.execute(
                    """
                    update control_state
                    set mode=?, updated_at_ms=?, note=?, control_version=?
                    where control_id=1
                    """,
                    (wanted, now_ms, clean_note, CONTROL_VERSION),
                )
        except Exception:
            pass

    return get_control_state()


def control_token_configured() -> bool:
    return bool(os.environ.get("CONTROL_API_TOKEN", "").strip())


def valid_control_token(value: str | None) -> bool:
    expected = os.environ.get("CONTROL_API_TOKEN", "").strip()
    supplied = (value or "").strip()
    if not expected or not supplied:
        return False

    # Constant-time equality without adding another dependency.
    if len(expected) != len(supplied):
        return False
    result = 0
    for left, right in zip(expected.encode(), supplied.encode()):
        result |= left ^ right
    return result == 0
