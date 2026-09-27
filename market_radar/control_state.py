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


CONTROL_VERSION = "stage15-control-v2"
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
) values (1, 'RUN', 0, 'default', 'stage15-control-v2');

create table if not exists live_activation_state (
    control_id integer primary key check(control_id=1),
    armed integer not null default 0,
    updated_at_ms integer not null default 0,
    note text,
    control_version text not null
);
insert or ignore into live_activation_state (
    control_id, armed, updated_at_ms, note, control_version
) values (1, 0, 0, 'default_disarmed', 'stage15-control-v2');
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
) values (1, 'RUN', 0, 'default', 'stage15-control-v2')
on conflict(control_id) do nothing;

create table if not exists live_activation_state (
    control_id integer primary key check(control_id=1),
    armed boolean not null default false,
    updated_at_ms bigint not null default 0,
    note text,
    control_version text not null
);
insert into live_activation_state (
    control_id, armed, updated_at_ms, note, control_version
) values (1, false, 0, 'default_disarmed', 'stage15-control-v2')
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
    data["paper_trading_env_enabled"] = (
        os.environ.get("PAPER_TRADING_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    live_env = (
        os.environ.get("LIVE_TRADING_ENABLED", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    credentials = bool(
        os.environ.get("BINANCE_API_KEY", "").strip()
        and os.environ.get("BINANCE_API_SECRET", "").strip()
    )

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                """
                select armed, updated_at_ms, note, control_version
                from live_activation_state where control_id=1
                """
            ).fetchone()
            live_row = dict(row)
    else:
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    select armed, updated_at_ms, note, control_version
                    from live_activation_state where control_id=1
                    """
                )
                live_row = dict(cur.fetchone())

    live_armed = bool(live_row.get("armed"))
    data["live_env_enabled"] = live_env
    data["live_credentials_configured"] = credentials
    data["live_armed"] = live_armed
    data["live_arm_updated_at_ms"] = live_row.get("updated_at_ms")
    data["live_arm_note"] = live_row.get("note")
    data["live_entry_submission_enabled"] = (
        live_env and credentials and live_armed and mode == "RUN"
    )
    data["live_exit_submission_enabled"] = live_env and credentials
    data["live_order_submission_enabled"] = data[
        "live_entry_submission_enabled"
    ]
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



def set_live_armed(
    armed: bool,
    *,
    note: str | None = None,
) -> dict[str, Any]:
    initialize_control_state()
    now_ms = int(time.time() * 1000)
    clean_note = (note or "").strip()[:240] or None

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update live_activation_state
                set armed=?, updated_at_ms=?, note=?, control_version=?
                where control_id=1
                """,
                (1 if armed else 0, now_ms, clean_note, CONTROL_VERSION),
            )
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update live_activation_state
                    set armed=%s, updated_at_ms=%s, note=%s, control_version=%s
                    where control_id=1
                    """,
                    (bool(armed), now_ms, clean_note, CONTROL_VERSION),
                )

    if persistence_backend() == "postgres":
        try:
            initialize_database(database_path())
            with _sqlite_connect(database_path()) as conn:
                conn.executescript(SQLITE_SCHEMA)
                conn.execute(
                    """
                    update live_activation_state
                    set armed=?, updated_at_ms=?, note=?, control_version=?
                    where control_id=1
                    """,
                    (1 if armed else 0, now_ms, clean_note, CONTROL_VERSION),
                )
        except Exception:
            pass

    return get_control_state()
