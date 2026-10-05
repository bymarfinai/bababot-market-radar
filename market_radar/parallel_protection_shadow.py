from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PARALLEL_SHADOW_CORE_VERSION = "ps1-v1-parallel-shadow-core"
PARALLEL_SHADOW_EVENT_VERSION = "ps2-v1-event-fanout-parity"
EXECUTION_AUTHORITY = "NONE"

@dataclass(frozen=True)
class BranchSpec:
    branch_key: str
    role: str
    protection_family: str
    no_action_be_arm_pct: float | None
    reduce25_logic: str
    runner_logic: str
    execution_authority: str = EXECUTION_AUTHORITY

BRANCH_SPECS: tuple[BranchSpec, ...] = (
    BranchSpec(
        branch_key="V42_BASELINE",
        role="BASELINE",
        protection_family="V4.2_HYBRID",
        no_action_be_arm_pct=None,
        reduce25_logic="V4.2",
        runner_logic="V4.2",
    ),
    BranchSpec(
        branch_key="V43_LS",
        role="CHALLENGER",
        protection_family="V4.3_LS_WITH_V4.2_RUNNER",
        no_action_be_arm_pct=None,
        reduce25_logic="V4.3_LS",
        runner_logic="V4.2",
    ),
    BranchSpec(
        branch_key="BE025_CONSERVATIVE",
        role="CHALLENGER_CONSERVATIVE",
        protection_family="V4.3_LS_BE0.25_WITH_V4.2_RUNNER",
        no_action_be_arm_pct=0.25,
        reduce25_logic="V4.3_LS",
        runner_logic="V4.2",
    ),
    BranchSpec(
        branch_key="BE018_AGGRESSIVE",
        role="CHALLENGER_AGGRESSIVE",
        protection_family="V4.3_LS_BE0.18_WITH_V4.2_RUNNER",
        no_action_be_arm_pct=0.18,
        reduce25_logic="V4.3_LS",
        runner_logic="V4.2",
    ),
)

BRANCH_KEYS = tuple(spec.branch_key for spec in BRANCH_SPECS)
_SPEC_BY_KEY = {spec.branch_key: spec for spec in BRANCH_SPECS}

_SQLITE_SCHEMA = """
create table if not exists protection_shadow_parents (
    parent_id text primary key,
    source_position_id text not null unique,
    signal_id text,
    symbol text not null,
    side text not null check (side in ('LONG','SHORT')),
    status text not null check (status in ('OPEN','ARCHIVED')),
    opened_at_ms integer not null,
    entry_price real not null check (entry_price > 0),
    initial_quantity real not null check (initial_quantity > 0),
    initial_notional_usdt real not null check (initial_notional_usdt > 0),
    identity_fingerprint text not null,
    core_version text not null,
    execution_authority text not null check (execution_authority='NONE'),
    metadata_json text not null default '{}',
    created_at_ms integer not null
);
create index if not exists idx_shadow_parent_status_time
on protection_shadow_parents(status, opened_at_ms desc);

create table if not exists protection_shadow_branches (
    branch_instance_id text primary key,
    parent_id text not null references protection_shadow_parents(parent_id) on delete cascade,
    branch_key text not null,
    role text not null,
    protection_family text not null,
    status text not null check (status in ('OPEN','CLOSED','INVALID')),
    opened_at_ms integer not null,
    entry_price real not null check (entry_price > 0),
    initial_quantity real not null check (initial_quantity > 0),
    remaining_quantity real not null check (
        remaining_quantity >= 0 and remaining_quantity <= initial_quantity
    ),
    current_state text not null,
    mfe_pct real,
    mae_pct real,
    last_event_id text,
    last_event_time_ms integer,
    state_json text not null default '{}',
    spec_json text not null,
    execution_authority text not null check (execution_authority='NONE'),
    core_version text not null,
    updated_at_ms integer not null,
    unique(parent_id, branch_key)
);
create index if not exists idx_shadow_branch_parent
on protection_shadow_branches(parent_id, branch_key);
create index if not exists idx_shadow_branch_status
on protection_shadow_branches(status, updated_at_ms desc);

create table if not exists protection_shadow_events (
    parent_id text not null references protection_shadow_parents(parent_id) on delete cascade,
    event_seq integer not null check (event_seq > 0),
    source_event_id text not null,
    event_time_ms integer not null,
    event_type text not null,
    market_price real not null check (market_price > 0),
    event_hash text not null,
    payload_json text not null default '{}',
    event_version text not null,
    created_at_ms integer not null,
    primary key(parent_id, event_seq),
    unique(parent_id, source_event_id)
);
create index if not exists idx_shadow_events_parent_time
on protection_shadow_events(parent_id, event_time_ms, event_seq);

create table if not exists protection_shadow_branch_events (
    parent_id text not null references protection_shadow_parents(parent_id) on delete cascade,
    branch_key text not null,
    event_seq integer not null,
    source_event_id text not null,
    event_time_ms integer not null,
    event_hash text not null,
    receipt_status text not null check (receipt_status='DELIVERED'),
    delivered_at_ms integer not null,
    event_version text not null,
    primary key(parent_id, branch_key, event_seq),
    foreign key(parent_id, event_seq)
      references protection_shadow_events(parent_id, event_seq) on delete cascade
);
create index if not exists idx_shadow_branch_events_parent_branch
on protection_shadow_branch_events(parent_id, branch_key, event_seq);

create table if not exists protection_shadow_parity_issues (
    issue_id text primary key,
    parent_id text not null references protection_shadow_parents(parent_id) on delete cascade,
    source_event_id text,
    event_seq integer,
    issue_type text not null,
    detected_at_ms integer not null,
    details_json text not null default '{}',
    event_version text not null
);
create index if not exists idx_shadow_parity_issues_parent_time
on protection_shadow_parity_issues(parent_id, detected_at_ms desc);
"""

_POSTGRES_SCHEMA = _SQLITE_SCHEMA.replace(" integer not null", " bigint not null").replace(
    " integer,", " bigint,"
)

_INIT_LOCK = threading.Lock()
_FANOUT_LOCK = threading.Lock()
_READY: set[tuple[str, str]] = set()


def _local_sqlite_connect(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    conn.execute("pragma busy_timeout = 15000")
    return conn


def _runtime_persistence():
    # Lazy import keeps isolated SQLite unit tests independent from optional
    # production PostgreSQL drivers.
    from . import persistence
    return persistence


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _normalize_parent(
    *,
    source_position_id: str,
    signal_id: str | None,
    symbol: str,
    side: str,
    opened_at_ms: int,
    entry_price: float,
    quantity: float,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    source_position_id = str(source_position_id).strip()
    symbol = str(symbol).upper().strip()
    side = str(side).upper().strip()
    if not source_position_id:
        raise ValueError("source_position_id is required")
    if not symbol:
        raise ValueError("symbol is required")
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side must be LONG or SHORT")
    opened_at_ms = int(opened_at_ms)
    entry_price = float(entry_price)
    quantity = float(quantity)
    if opened_at_ms <= 0:
        raise ValueError("opened_at_ms must be positive")
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    return {
        "source_position_id": source_position_id,
        "signal_id": str(signal_id).strip() if signal_id else None,
        "symbol": symbol,
        "side": side,
        "opened_at_ms": opened_at_ms,
        "entry_price": entry_price,
        "quantity": quantity,
        "initial_notional_usdt": entry_price * quantity,
        "metadata": dict(metadata or {}),
    }


def _identity_fingerprint(parent: dict[str, Any]) -> str:
    identity = {
        "source_position_id": parent["source_position_id"],
        "signal_id": parent["signal_id"],
        "symbol": parent["symbol"],
        "side": parent["side"],
        "opened_at_ms": parent["opened_at_ms"],
        "entry_price": parent["entry_price"],
        "quantity": parent["quantity"],
    }
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def parent_id_for(source_position_id: str) -> str:
    digest = hashlib.sha256(str(source_position_id).encode("utf-8")).hexdigest()[:20]
    return f"PS:{digest}"


def branch_instance_id(parent_id: str, branch_key: str) -> str:
    if branch_key not in _SPEC_BY_KEY:
        raise ValueError(f"unknown branch_key: {branch_key}")
    return f"{parent_id}:{branch_key}"


def initialize_parallel_shadow_store(path: str | Path | None = None) -> None:
    if path is not None:
        key = ("sqlite", str(Path(path).resolve()))
        with _INIT_LOCK:
            if key in _READY:
                return
            with _local_sqlite_connect(path) as conn:
                conn.executescript(_SQLITE_SCHEMA)
            _READY.add(key)
        return

    p = _runtime_persistence()
    p.initialize_database()
    if p.persistence_backend() == "sqlite":
        key = ("sqlite", str(p.database_path().resolve()))
        with _INIT_LOCK:
            if key in _READY:
                return
            with p._sqlite_connect(p.database_path()) as conn:
                conn.executescript(_SQLITE_SCHEMA)
            _READY.add(key)
        return

    key = ("postgres", "primary")
    with _INIT_LOCK:
        if key in _READY:
            return
        with p._postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_POSTGRES_SCHEMA)
        _READY.add(key)


def _fetch_parent_by_source(source_position_id: str, path: str | Path | None) -> dict[str, Any] | None:
    query = "select * from protection_shadow_parents where source_position_id=?"
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            row = conn.execute(query, (source_position_id,)).fetchone()
            return dict(row) if row else None

    p = _runtime_persistence()
    if p.persistence_backend() == "sqlite":
        with p._sqlite_connect(p.database_path()) as conn:
            row = conn.execute(query, (source_position_id,)).fetchone()
            return dict(row) if row else None
    with p._postgres_connect() as conn:
        with conn.cursor(cursor_factory=p.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), (source_position_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def create_shadow_parent(
    *,
    source_position_id: str,
    signal_id: str | None,
    symbol: str,
    side: str,
    opened_at_ms: int,
    entry_price: float,
    quantity: float,
    metadata: dict[str, Any] | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Create one parent and exactly four isolated shadow branches.

    This function has no order/execution authority. Repeating an identical
    parent is idempotent; repeating the same source_position_id with different
    immutable entry identity is rejected.
    """
    initialize_parallel_shadow_store(path)
    p = _normalize_parent(
        source_position_id=source_position_id,
        signal_id=signal_id,
        symbol=symbol,
        side=side,
        opened_at_ms=opened_at_ms,
        entry_price=entry_price,
        quantity=quantity,
        metadata=metadata,
    )
    fingerprint = _identity_fingerprint(p)
    parent_id = parent_id_for(p["source_position_id"])
    now_ms = int(time.time() * 1000)
    existing = _fetch_parent_by_source(p["source_position_id"], path)
    if existing and existing["identity_fingerprint"] != fingerprint:
        raise ValueError("shadow parent identity conflict for source_position_id")

    parent_values = (
        parent_id, p["source_position_id"], p["signal_id"], p["symbol"], p["side"],
        "OPEN", p["opened_at_ms"], p["entry_price"], p["quantity"],
        p["initial_notional_usdt"], fingerprint, PARALLEL_SHADOW_CORE_VERSION,
        EXECUTION_AUTHORITY, _canonical_json(p["metadata"]), now_ms,
    )
    branch_rows = []
    for spec in BRANCH_SPECS:
        spec_json = _canonical_json(asdict(spec))
        branch_rows.append((
            branch_instance_id(parent_id, spec.branch_key), parent_id, spec.branch_key,
            spec.role, spec.protection_family, "OPEN", p["opened_at_ms"],
            p["entry_price"], p["quantity"], p["quantity"], "ENTRY_OPEN",
            None, None, None, None, "{}", spec_json, EXECUTION_AUTHORITY,
            PARALLEL_SHADOW_CORE_VERSION, now_ms,
        ))

    if path is not None:
        with _local_sqlite_connect(path) as conn:
            conn.execute(
                """insert or ignore into protection_shadow_parents (
                    parent_id, source_position_id, signal_id, symbol, side, status,
                    opened_at_ms, entry_price, initial_quantity, initial_notional_usdt,
                    identity_fingerprint, core_version, execution_authority,
                    metadata_json, created_at_ms
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                parent_values,
            )
            conn.executemany(
                """insert or ignore into protection_shadow_branches (
                    branch_instance_id, parent_id, branch_key, role, protection_family,
                    status, opened_at_ms, entry_price, initial_quantity,
                    remaining_quantity, current_state, mfe_pct, mae_pct, last_event_id,
                    last_event_time_ms, state_json, spec_json, execution_authority,
                    core_version, updated_at_ms
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                branch_rows,
            )
    else:
        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                conn.execute(
                    """insert or ignore into protection_shadow_parents (
                        parent_id, source_position_id, signal_id, symbol, side, status,
                        opened_at_ms, entry_price, initial_quantity, initial_notional_usdt,
                        identity_fingerprint, core_version, execution_authority,
                        metadata_json, created_at_ms
                    ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    parent_values,
                )
                conn.executemany(
                    """insert or ignore into protection_shadow_branches (
                        branch_instance_id, parent_id, branch_key, role, protection_family,
                        status, opened_at_ms, entry_price, initial_quantity,
                        remaining_quantity, current_state, mfe_pct, mae_pct, last_event_id,
                        last_event_time_ms, state_json, spec_json, execution_authority,
                        core_version, updated_at_ms
                    ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    branch_rows,
                )
        else:
            with runtime._postgres_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """insert into protection_shadow_parents (
                            parent_id, source_position_id, signal_id, symbol, side, status,
                            opened_at_ms, entry_price, initial_quantity, initial_notional_usdt,
                            identity_fingerprint, core_version, execution_authority,
                            metadata_json, created_at_ms
                        ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        on conflict(source_position_id) do nothing""",
                        parent_values,
                    )
                    cur.executemany(
                        """insert into protection_shadow_branches (
                            branch_instance_id, parent_id, branch_key, role, protection_family,
                            status, opened_at_ms, entry_price, initial_quantity,
                            remaining_quantity, current_state, mfe_pct, mae_pct, last_event_id,
                            last_event_time_ms, state_json, spec_json, execution_authority,
                            core_version, updated_at_ms
                        ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        on conflict(parent_id, branch_key) do nothing""",
                        branch_rows,
                    )

    branches = list_shadow_branches(parent_id, path=path)
    if tuple(row["branch_key"] for row in branches) != BRANCH_KEYS:
        raise RuntimeError("parallel shadow branch set is incomplete or out of order")
    return {
        "parent_id": parent_id,
        "source_position_id": p["source_position_id"],
        "branch_count": len(branches),
        "branch_keys": [row["branch_key"] for row in branches],
        "execution_authority": EXECUTION_AUTHORITY,
        "core_version": PARALLEL_SHADOW_CORE_VERSION,
        "created": existing is None,
    }


def list_shadow_branches(parent_id: str, *, path: str | Path | None = None) -> list[dict[str, Any]]:
    initialize_parallel_shadow_store(path)
    order_case = "case branch_key " + " ".join(
        f"when '{key}' then {i}" for i, key in enumerate(BRANCH_KEYS)
    ) + " else 999 end"
    query = f"select * from protection_shadow_branches where parent_id=? order by {order_case}"
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return [dict(r) for r in conn.execute(query, (parent_id,)).fetchall()]
    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            return [dict(r) for r in conn.execute(query, (parent_id,)).fetchall()]
    with runtime._postgres_connect() as conn:
        with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), (parent_id,))
            return [dict(r) for r in cur.fetchall()]


def get_shadow_branch(
    parent_id: str,
    branch_key: str,
    *,
    path: str | Path | None = None,
) -> dict[str, Any] | None:
    if branch_key not in _SPEC_BY_KEY:
        raise ValueError(f"unknown branch_key: {branch_key}")
    rows = list_shadow_branches(parent_id, path=path)
    return next((row for row in rows if row["branch_key"] == branch_key), None)


def update_shadow_branch_state(
    *,
    parent_id: str,
    branch_key: str,
    current_state: str,
    mfe_pct: float | None = None,
    mae_pct: float | None = None,
    remaining_quantity: float | None = None,
    state: dict[str, Any] | None = None,
    path: str | Path | None = None,
) -> None:
    """PS-1 state-isolation primitive. It cannot settle or execute an order."""
    if branch_key not in _SPEC_BY_KEY:
        raise ValueError(f"unknown branch_key: {branch_key}")
    current_state = str(current_state).strip().upper()
    if not current_state:
        raise ValueError("current_state is required")
    if remaining_quantity is not None and float(remaining_quantity) < 0:
        raise ValueError("remaining_quantity cannot be negative")
    initialize_parallel_shadow_store(path)
    existing_branch = get_shadow_branch(parent_id, branch_key, path=path)
    if existing_branch is None:
        raise KeyError(f"shadow branch not found: {parent_id}/{branch_key}")
    if (
        remaining_quantity is not None
        and float(remaining_quantity) > float(existing_branch["initial_quantity"]) + 1e-12
    ):
        raise ValueError("remaining_quantity cannot exceed initial_quantity")
    now_ms = int(time.time() * 1000)
    values = (
        current_state, mfe_pct, mae_pct, remaining_quantity,
        _canonical_json(state or {}), now_ms, parent_id, branch_key,
    )
    sql = """update protection_shadow_branches
             set current_state=?, mfe_pct=coalesce(?,mfe_pct),
                 mae_pct=coalesce(?,mae_pct),
                 remaining_quantity=coalesce(?,remaining_quantity),
                 state_json=?, updated_at_ms=?
             where parent_id=? and branch_key=? and status='OPEN'"""
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            cur = conn.execute(sql, values)
            if cur.rowcount != 1:
                raise KeyError(f"open shadow branch not found: {parent_id}/{branch_key}")
        return
    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            cur = conn.execute(sql, values)
            if cur.rowcount != 1:
                raise KeyError(f"open shadow branch not found: {parent_id}/{branch_key}")
        return
    with runtime._postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql.replace("?", "%s"), values)
            if cur.rowcount != 1:
                raise KeyError(f"open shadow branch not found: {parent_id}/{branch_key}")


def get_shadow_parent(source_position_id: str, *, path: str | Path | None = None) -> dict[str, Any] | None:
    initialize_parallel_shadow_store(path)
    return _fetch_parent_by_source(str(source_position_id), path)


def record_shadow_integrity_issue(
    *,
    parent_id: str,
    issue_type: str,
    details: dict[str, Any] | None = None,
    source_event_id: str | None = None,
    event_seq: int | None = None,
    path: str | Path | None = None,
) -> None:
    """Persist a fail-closed comparison-integrity issue for runtime feed faults."""
    initialize_parallel_shadow_store(path)
    issue_type = str(issue_type).strip().upper()
    if not issue_type:
        raise ValueError("issue_type is required")
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            _record_issue_sqlite(
                conn,
                parent_id=parent_id,
                issue_type=issue_type,
                source_event_id=source_event_id,
                event_seq=event_seq,
                details=details or {},
            )
        return
    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            _record_issue_sqlite(
                conn,
                parent_id=parent_id,
                issue_type=issue_type,
                source_event_id=source_event_id,
                event_seq=event_seq,
                details=details or {},
            )
        return
    with runtime._postgres_connect() as conn:
        with conn.cursor() as cur:
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type=issue_type,
                source_event_id=source_event_id,
                event_seq=event_seq,
                details=details or {},
            )


def archive_shadow_parent(
    parent_id: str,
    *,
    path: str | Path | None = None,
) -> bool:
    """Archive a parent after the source trade lifecycle has ended."""
    initialize_parallel_shadow_store(path)
    sql = """update protection_shadow_parents
             set status='ARCHIVED'
             where parent_id=? and status='OPEN'"""
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return conn.execute(sql, (parent_id,)).rowcount == 1
    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            return conn.execute(sql, (parent_id,)).rowcount == 1
    with runtime._postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql.replace("?", "%s"), (parent_id,))
            return cur.rowcount == 1


def shadow_core_summary(*, path: str | Path | None = None) -> dict[str, Any]:
    initialize_parallel_shadow_store(path)
    queries = {
        "parents": "select count(*) from protection_shadow_parents",
        "open_parents": "select count(*) from protection_shadow_parents where status='OPEN'",
        "branches": "select count(*) from protection_shadow_branches",
        "open_branches": "select count(*) from protection_shadow_branches where status='OPEN'",
        "non_none_authority": "select count(*) from protection_shadow_branches where execution_authority<>'NONE'",
    }
    values: dict[str, int] = {}
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            for key, sql in queries.items():
                values[key] = int(conn.execute(sql).fetchone()[0])
    else:
        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                for key, sql in queries.items():
                    values[key] = int(conn.execute(sql).fetchone()[0])
        else:
            with runtime._postgres_connect() as conn:
                with conn.cursor() as cur:
                    for key, sql in queries.items():
                        cur.execute(sql)
                        values[key] = int(cur.fetchone()[0])
    return {
        **values,
        "expected_branches_per_parent": len(BRANCH_SPECS),
        "branch_keys": list(BRANCH_KEYS),
        "execution_authority": EXECUTION_AUTHORITY,
        "core_version": PARALLEL_SHADOW_CORE_VERSION,
    }


def _event_hash(
    *,
    parent_id: str,
    source_event_id: str,
    event_time_ms: int,
    event_type: str,
    market_price: float,
    payload: dict[str, Any],
) -> str:
    body = {
        "parent_id": parent_id,
        "source_event_id": source_event_id,
        "event_time_ms": int(event_time_ms),
        "event_type": event_type,
        "market_price": float(market_price),
        "payload": payload,
    }
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def _issue_id(
    parent_id: str,
    issue_type: str,
    source_event_id: str | None,
    event_seq: int | None,
    details: dict[str, Any],
) -> str:
    body = {
        "parent_id": parent_id,
        "issue_type": issue_type,
        "source_event_id": source_event_id,
        "event_seq": event_seq,
        "details": details,
    }
    return "PSI:" + hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()[:32]


def _record_issue_sqlite(
    conn: sqlite3.Connection,
    *,
    parent_id: str,
    issue_type: str,
    source_event_id: str | None = None,
    event_seq: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    data = dict(details or {})
    issue_id = _issue_id(parent_id, issue_type, source_event_id, event_seq, data)
    conn.execute(
        """insert or ignore into protection_shadow_parity_issues (
            issue_id, parent_id, source_event_id, event_seq, issue_type,
            detected_at_ms, details_json, event_version
        ) values (?,?,?,?,?,?,?,?)""",
        (
            issue_id, parent_id, source_event_id, event_seq, issue_type,
            int(time.time() * 1000), _canonical_json(data),
            PARALLEL_SHADOW_EVENT_VERSION,
        ),
    )


def _record_issue_postgres(
    cur: Any,
    *,
    parent_id: str,
    issue_type: str,
    source_event_id: str | None = None,
    event_seq: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    data = dict(details or {})
    issue_id = _issue_id(parent_id, issue_type, source_event_id, event_seq, data)
    cur.execute(
        """insert into protection_shadow_parity_issues (
            issue_id, parent_id, source_event_id, event_seq, issue_type,
            detected_at_ms, details_json, event_version
        ) values (%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict(issue_id) do nothing""",
        (
            issue_id, parent_id, source_event_id, event_seq, issue_type,
            int(time.time() * 1000), _canonical_json(data),
            PARALLEL_SHADOW_EVENT_VERSION,
        ),
    )


def _fanout_sqlite(
    conn: sqlite3.Connection,
    *,
    parent_id: str,
    source_event_id: str,
    event_time_ms: int,
    event_type: str,
    market_price: float,
    payload: dict[str, Any],
    event_hash: str,
) -> dict[str, Any]:
    parent = conn.execute(
        "select * from protection_shadow_parents where parent_id=?",
        (parent_id,),
    ).fetchone()
    if parent is None:
        raise KeyError(f"shadow parent not found: {parent_id}")
    parent = dict(parent)
    if parent["status"] != "OPEN":
        return {"status": "PARENT_NOT_OPEN", "parent_id": parent_id}

    branch_rows = conn.execute(
        "select branch_key from protection_shadow_branches where parent_id=? order by branch_key",
        (parent_id,),
    ).fetchall()
    branch_set = {str(r[0]) for r in branch_rows}
    expected = set(BRANCH_KEYS)
    if branch_set != expected:
        details = {
            "expected": sorted(expected),
            "actual": sorted(branch_set),
            "missing": sorted(expected - branch_set),
            "extra": sorted(branch_set - expected),
        }
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="BRANCH_SET_MISMATCH",
            source_event_id=source_event_id,
            details=details,
        )
        return {"status": "PARITY_ERROR", "reason": "BRANCH_SET_MISMATCH", **details}

    existing = conn.execute(
        """select event_seq,event_hash from protection_shadow_events
           where parent_id=? and source_event_id=?""",
        (parent_id, source_event_id),
    ).fetchone()
    if existing is not None:
        existing = dict(existing)
        if existing["event_hash"] == event_hash:
            receipt_row = conn.execute(
                """select count(*) as total,
                          sum(case when event_hash=? then 1 else 0 end) as matching
                   from protection_shadow_branch_events
                   where parent_id=? and event_seq=?""",
                (event_hash, parent_id, existing["event_seq"]),
            ).fetchone()
            receipts = int(receipt_row["total"] or 0)
            matching = int(receipt_row["matching"] or 0)
            if receipts != len(BRANCH_KEYS) or matching != len(BRANCH_KEYS):
                _record_issue_sqlite(
                    conn,
                    parent_id=parent_id,
                    issue_type="DUPLICATE_RECEIPT_PARITY_FAILURE",
                    source_event_id=source_event_id,
                    event_seq=int(existing["event_seq"]),
                    details={
                        "receipt_count": receipts,
                        "matching_hash_count": matching,
                        "expected": len(BRANCH_KEYS),
                    },
                )
                return {
                    "status": "PARITY_ERROR",
                    "reason": "DUPLICATE_RECEIPT_PARITY_FAILURE",
                    "event_seq": int(existing["event_seq"]),
                    "receipt_count": receipts,
                    "expected_receipts": len(BRANCH_KEYS),
                }
            return {
                "status": "DUPLICATE",
                "parent_id": parent_id,
                "event_seq": int(existing["event_seq"]),
                "event_hash": event_hash,
                "receipt_count": receipts,
                "expected_receipts": len(BRANCH_KEYS),
            }
        details = {
            "existing_hash": existing["event_hash"],
            "incoming_hash": event_hash,
        }
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="SOURCE_EVENT_CONFLICT",
            source_event_id=source_event_id,
            event_seq=int(existing["event_seq"]),
            details=details,
        )
        return {
            "status": "PARITY_ERROR",
            "reason": "SOURCE_EVENT_CONFLICT",
            "event_seq": int(existing["event_seq"]),
        }

    if event_time_ms < int(parent["opened_at_ms"]):
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="EVENT_BEFORE_OPEN",
            source_event_id=source_event_id,
            details={"event_time_ms": event_time_ms, "opened_at_ms": int(parent["opened_at_ms"])},
        )
        return {"status": "PARITY_ERROR", "reason": "EVENT_BEFORE_OPEN"}

    last = conn.execute(
        """select event_seq,event_time_ms from protection_shadow_events
           where parent_id=? order by event_seq desc limit 1""",
        (parent_id,),
    ).fetchone()
    if last is not None and event_time_ms < int(last["event_time_ms"]):
        details = {
            "event_time_ms": event_time_ms,
            "last_event_time_ms": int(last["event_time_ms"]),
            "last_event_seq": int(last["event_seq"]),
        }
        _record_issue_sqlite(
            conn,
            parent_id=parent_id,
            issue_type="OUT_OF_ORDER_EVENT",
            source_event_id=source_event_id,
            details=details,
        )
        return {"status": "PARITY_ERROR", "reason": "OUT_OF_ORDER_EVENT", **details}

    event_seq = 1 if last is None else int(last["event_seq"]) + 1
    now_ms = int(time.time() * 1000)
    payload_json = _canonical_json(payload)
    conn.execute(
        """insert into protection_shadow_events (
            parent_id,event_seq,source_event_id,event_time_ms,event_type,
            market_price,event_hash,payload_json,event_version,created_at_ms
        ) values (?,?,?,?,?,?,?,?,?,?)""",
        (
            parent_id, event_seq, source_event_id, event_time_ms, event_type,
            market_price, event_hash, payload_json,
            PARALLEL_SHADOW_EVENT_VERSION, now_ms,
        ),
    )
    conn.executemany(
        """insert into protection_shadow_branch_events (
            parent_id,branch_key,event_seq,source_event_id,event_time_ms,
            event_hash,receipt_status,delivered_at_ms,event_version
        ) values (?,?,?,?,?,?,?,?,?)""",
        [
            (
                parent_id, branch_key, event_seq, source_event_id, event_time_ms,
                event_hash, "DELIVERED", now_ms, PARALLEL_SHADOW_EVENT_VERSION,
            )
            for branch_key in BRANCH_KEYS
        ],
    )
    cur = conn.execute(
        """update protection_shadow_branches
           set last_event_id=?, last_event_time_ms=?, updated_at_ms=?
           where parent_id=?""",
        (source_event_id, event_time_ms, now_ms, parent_id),
    )
    if cur.rowcount != len(BRANCH_KEYS):
        raise RuntimeError(
            f"fanout cursor update mismatch: {cur.rowcount} != {len(BRANCH_KEYS)}"
        )
    receipts = conn.execute(
        """select count(*) from protection_shadow_branch_events
           where parent_id=? and event_seq=?""",
        (parent_id, event_seq),
    ).fetchone()[0]
    if int(receipts) != len(BRANCH_KEYS):
        raise RuntimeError(
            f"fanout receipt mismatch: {receipts} != {len(BRANCH_KEYS)}"
        )
    return {
        "status": "FANOUT_OK",
        "parent_id": parent_id,
        "event_seq": event_seq,
        "source_event_id": source_event_id,
        "event_hash": event_hash,
        "receipt_count": int(receipts),
        "expected_receipts": len(BRANCH_KEYS),
        "branch_keys": list(BRANCH_KEYS),
        "execution_authority": EXECUTION_AUTHORITY,
    }


def _fanout_postgres(
    conn: Any,
    *,
    parent_id: str,
    source_event_id: str,
    event_time_ms: int,
    event_type: str,
    market_price: float,
    payload: dict[str, Any],
    event_hash: str,
) -> dict[str, Any]:
    runtime = _runtime_persistence()
    with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "select * from protection_shadow_parents where parent_id=%s for update",
            (parent_id,),
        )
        parent = cur.fetchone()
        if parent is None:
            raise KeyError(f"shadow parent not found: {parent_id}")
        if parent["status"] != "OPEN":
            return {"status": "PARENT_NOT_OPEN", "parent_id": parent_id}

        cur.execute(
            "select branch_key from protection_shadow_branches where parent_id=%s",
            (parent_id,),
        )
        branch_set = {str(r["branch_key"]) for r in cur.fetchall()}
        expected = set(BRANCH_KEYS)
        if branch_set != expected:
            details = {
                "expected": sorted(expected),
                "actual": sorted(branch_set),
                "missing": sorted(expected - branch_set),
                "extra": sorted(branch_set - expected),
            }
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="BRANCH_SET_MISMATCH",
                source_event_id=source_event_id,
                details=details,
            )
            return {"status": "PARITY_ERROR", "reason": "BRANCH_SET_MISMATCH", **details}

        cur.execute(
            """select event_seq,event_hash from protection_shadow_events
               where parent_id=%s and source_event_id=%s""",
            (parent_id, source_event_id),
        )
        existing = cur.fetchone()
        if existing is not None:
            if existing["event_hash"] == event_hash:
                cur.execute(
                    """select count(*) as total,
                              sum(case when event_hash=%s then 1 else 0 end) as matching
                       from protection_shadow_branch_events
                       where parent_id=%s and event_seq=%s""",
                    (event_hash, parent_id, existing["event_seq"]),
                )
                receipt_row = cur.fetchone()
                receipts = int(receipt_row["total"] or 0)
                matching = int(receipt_row["matching"] or 0)
                if receipts != len(BRANCH_KEYS) or matching != len(BRANCH_KEYS):
                    _record_issue_postgres(
                        cur,
                        parent_id=parent_id,
                        issue_type="DUPLICATE_RECEIPT_PARITY_FAILURE",
                        source_event_id=source_event_id,
                        event_seq=int(existing["event_seq"]),
                        details={
                            "receipt_count": receipts,
                            "matching_hash_count": matching,
                            "expected": len(BRANCH_KEYS),
                        },
                    )
                    return {
                        "status": "PARITY_ERROR",
                        "reason": "DUPLICATE_RECEIPT_PARITY_FAILURE",
                        "event_seq": int(existing["event_seq"]),
                        "receipt_count": receipts,
                        "expected_receipts": len(BRANCH_KEYS),
                    }
                return {
                    "status": "DUPLICATE",
                    "parent_id": parent_id,
                    "event_seq": int(existing["event_seq"]),
                    "event_hash": event_hash,
                    "receipt_count": receipts,
                    "expected_receipts": len(BRANCH_KEYS),
                }
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="SOURCE_EVENT_CONFLICT",
                source_event_id=source_event_id,
                event_seq=int(existing["event_seq"]),
                details={
                    "existing_hash": existing["event_hash"],
                    "incoming_hash": event_hash,
                },
            )
            return {
                "status": "PARITY_ERROR",
                "reason": "SOURCE_EVENT_CONFLICT",
                "event_seq": int(existing["event_seq"]),
            }

        if event_time_ms < int(parent["opened_at_ms"]):
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="EVENT_BEFORE_OPEN",
                source_event_id=source_event_id,
                details={
                    "event_time_ms": event_time_ms,
                    "opened_at_ms": int(parent["opened_at_ms"]),
                },
            )
            return {"status": "PARITY_ERROR", "reason": "EVENT_BEFORE_OPEN"}

        cur.execute(
            """select event_seq,event_time_ms from protection_shadow_events
               where parent_id=%s order by event_seq desc limit 1""",
            (parent_id,),
        )
        last = cur.fetchone()
        if last is not None and event_time_ms < int(last["event_time_ms"]):
            details = {
                "event_time_ms": event_time_ms,
                "last_event_time_ms": int(last["event_time_ms"]),
                "last_event_seq": int(last["event_seq"]),
            }
            _record_issue_postgres(
                cur,
                parent_id=parent_id,
                issue_type="OUT_OF_ORDER_EVENT",
                source_event_id=source_event_id,
                details=details,
            )
            return {"status": "PARITY_ERROR", "reason": "OUT_OF_ORDER_EVENT", **details}

        event_seq = 1 if last is None else int(last["event_seq"]) + 1
        now_ms = int(time.time() * 1000)
        cur.execute(
            """insert into protection_shadow_events (
                parent_id,event_seq,source_event_id,event_time_ms,event_type,
                market_price,event_hash,payload_json,event_version,created_at_ms
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                parent_id, event_seq, source_event_id, event_time_ms, event_type,
                market_price, event_hash, _canonical_json(payload),
                PARALLEL_SHADOW_EVENT_VERSION, now_ms,
            ),
        )
        cur.executemany(
            """insert into protection_shadow_branch_events (
                parent_id,branch_key,event_seq,source_event_id,event_time_ms,
                event_hash,receipt_status,delivered_at_ms,event_version
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [
                (
                    parent_id, branch_key, event_seq, source_event_id, event_time_ms,
                    event_hash, "DELIVERED", now_ms, PARALLEL_SHADOW_EVENT_VERSION,
                )
                for branch_key in BRANCH_KEYS
            ],
        )
        cur.execute(
            """update protection_shadow_branches
               set last_event_id=%s,last_event_time_ms=%s,updated_at_ms=%s
               where parent_id=%s""",
            (source_event_id, event_time_ms, now_ms, parent_id),
        )
        if cur.rowcount != len(BRANCH_KEYS):
            raise RuntimeError(
                f"fanout cursor update mismatch: {cur.rowcount} != {len(BRANCH_KEYS)}"
            )
        cur.execute(
            """select count(*) as count from protection_shadow_branch_events
               where parent_id=%s and event_seq=%s""",
            (parent_id, event_seq),
        )
        receipts = int(cur.fetchone()["count"])
        if receipts != len(BRANCH_KEYS):
            raise RuntimeError(
                f"fanout receipt mismatch: {receipts} != {len(BRANCH_KEYS)}"
            )
        return {
            "status": "FANOUT_OK",
            "parent_id": parent_id,
            "event_seq": event_seq,
            "source_event_id": source_event_id,
            "event_hash": event_hash,
            "receipt_count": receipts,
            "expected_receipts": len(BRANCH_KEYS),
            "branch_keys": list(BRANCH_KEYS),
            "execution_authority": EXECUTION_AUTHORITY,
        }


def fanout_shadow_event(
    *,
    parent_id: str,
    source_event_id: str,
    event_time_ms: int,
    event_type: str,
    market_price: float,
    payload: dict[str, Any] | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Atomically persist one canonical event and identical receipts to all branches."""
    parent_id = str(parent_id).strip()
    source_event_id = str(source_event_id).strip()
    event_type = str(event_type).strip().upper()
    event_time_ms = int(event_time_ms)
    market_price = float(market_price)
    payload = dict(payload or {})
    if not parent_id:
        raise ValueError("parent_id is required")
    if not source_event_id:
        raise ValueError("source_event_id is required")
    if event_time_ms <= 0:
        raise ValueError("event_time_ms must be positive")
    if not event_type:
        raise ValueError("event_type is required")
    if market_price <= 0:
        raise ValueError("market_price must be positive")
    initialize_parallel_shadow_store(path)
    event_hash = _event_hash(
        parent_id=parent_id,
        source_event_id=source_event_id,
        event_time_ms=event_time_ms,
        event_type=event_type,
        market_price=market_price,
        payload=payload,
    )
    with _FANOUT_LOCK:
        if path is not None:
            with _local_sqlite_connect(path) as conn:
                with conn:
                    return _fanout_sqlite(
                        conn,
                        parent_id=parent_id,
                        source_event_id=source_event_id,
                        event_time_ms=event_time_ms,
                        event_type=event_type,
                        market_price=market_price,
                        payload=payload,
                        event_hash=event_hash,
                    )
        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            with runtime._sqlite_connect(runtime.database_path()) as conn:
                with conn:
                    return _fanout_sqlite(
                        conn,
                        parent_id=parent_id,
                        source_event_id=source_event_id,
                        event_time_ms=event_time_ms,
                        event_type=event_type,
                        market_price=market_price,
                        payload=payload,
                        event_hash=event_hash,
                    )
        with runtime._postgres_connect() as conn:
            return _fanout_postgres(
                conn,
                parent_id=parent_id,
                source_event_id=source_event_id,
                event_time_ms=event_time_ms,
                event_type=event_type,
                market_price=market_price,
                payload=payload,
                event_hash=event_hash,
            )


def fanout_shadow_events_batch(
    *,
    parent_id: str,
    events: list[dict[str, Any]],
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Fan out multiple already-ordered canonical events in one DB transaction."""
    parent_id = str(parent_id).strip()
    if not parent_id:
        raise ValueError("parent_id is required")
    if not events:
        return {
            "status": "EMPTY",
            "parent_id": parent_id,
            "results": [],
            "accepted_n": 0,
            "execution_authority": EXECUTION_AUTHORITY,
        }

    normalized: list[dict[str, Any]] = []
    for raw in events:
        source_event_id = str(raw.get("source_event_id") or "").strip()
        event_type = str(raw.get("event_type") or "").strip().upper()
        event_time_ms = int(raw.get("event_time_ms") or 0)
        market_price = float(raw.get("market_price") or 0.0)
        payload = dict(raw.get("payload") or {})
        if not source_event_id:
            raise ValueError("source_event_id is required")
        if not event_type:
            raise ValueError("event_type is required")
        if event_time_ms <= 0:
            raise ValueError("event_time_ms must be positive")
        if market_price <= 0:
            raise ValueError("market_price must be positive")
        normalized.append(
            {
                "source_event_id": source_event_id,
                "event_time_ms": event_time_ms,
                "event_type": event_type,
                "market_price": market_price,
                "payload": payload,
                "event_hash": _event_hash(
                    parent_id=parent_id,
                    source_event_id=source_event_id,
                    event_time_ms=event_time_ms,
                    event_type=event_type,
                    market_price=market_price,
                    payload=payload,
                ),
            }
        )

    initialize_parallel_shadow_store(path)

    def run_sqlite(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in normalized:
            result = _fanout_sqlite(
                conn,
                parent_id=parent_id,
                source_event_id=item["source_event_id"],
                event_time_ms=item["event_time_ms"],
                event_type=item["event_type"],
                market_price=item["market_price"],
                payload=item["payload"],
                event_hash=item["event_hash"],
            )
            results.append(result)
            if result["status"] in {"PARITY_ERROR", "PARENT_NOT_OPEN"}:
                break
        return results

    def run_postgres(conn: Any) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for item in normalized:
            result = _fanout_postgres(
                conn,
                parent_id=parent_id,
                source_event_id=item["source_event_id"],
                event_time_ms=item["event_time_ms"],
                event_type=item["event_type"],
                market_price=item["market_price"],
                payload=item["payload"],
                event_hash=item["event_hash"],
            )
            results.append(result)
            if result["status"] in {"PARITY_ERROR", "PARENT_NOT_OPEN"}:
                break
        return results

    with _FANOUT_LOCK:
        if path is not None:
            with _local_sqlite_connect(path) as conn:
                with conn:
                    results = run_sqlite(conn)
        else:
            runtime = _runtime_persistence()
            if runtime.persistence_backend() == "sqlite":
                with runtime._sqlite_connect(runtime.database_path()) as conn:
                    with conn:
                        results = run_sqlite(conn)
            else:
                with runtime._postgres_connect() as conn:
                    results = run_postgres(conn)

    accepted = [
        r for r in results if r["status"] in {"FANOUT_OK", "DUPLICATE"}
    ]
    bad = next(
        (r for r in results if r["status"] not in {"FANOUT_OK", "DUPLICATE"}),
        None,
    )
    return {
        "status": "BATCH_OK" if bad is None and len(results) == len(normalized) else "BATCH_ERROR",
        "parent_id": parent_id,
        "requested_n": len(normalized),
        "processed_n": len(results),
        "accepted_n": len(accepted),
        "last_event_seq": (
            max(int(r["event_seq"]) for r in accepted if r.get("event_seq") is not None)
            if any(r.get("event_seq") is not None for r in accepted)
            else None
        ),
        "error": bad,
        "results": results,
        "execution_authority": EXECUTION_AUTHORITY,
    }


def get_shadow_event_by_source_id(
    parent_id: str,
    source_event_id: str,
    *,
    path: str | Path | None = None,
) -> dict[str, Any] | None:
    initialize_parallel_shadow_store(path)
    query = """select * from protection_shadow_events
               where parent_id=? and source_event_id=?"""
    params = (str(parent_id), str(source_event_id))
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None
    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None
    with runtime._postgres_connect() as conn:
        with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), params)
            row = cur.fetchone()
            return dict(row) if row else None


def list_shadow_events(
    parent_id: str,
    *,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    initialize_parallel_shadow_store(path)
    query = "select * from protection_shadow_events where parent_id=? order by event_seq"
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return [dict(r) for r in conn.execute(query, (parent_id,)).fetchall()]
    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            return [dict(r) for r in conn.execute(query, (parent_id,)).fetchall()]
    with runtime._postgres_connect() as conn:
        with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), (parent_id,))
            return [dict(r) for r in cur.fetchall()]


def list_shadow_branch_events(
    parent_id: str,
    branch_key: str,
    *,
    path: str | Path | None = None,
) -> list[dict[str, Any]]:
    if branch_key not in _SPEC_BY_KEY:
        raise ValueError(f"unknown branch_key: {branch_key}")
    initialize_parallel_shadow_store(path)
    query = """select * from protection_shadow_branch_events
               where parent_id=? and branch_key=? order by event_seq"""
    params = (parent_id, branch_key)
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]
    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        with runtime._sqlite_connect(runtime.database_path()) as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]
    with runtime._postgres_connect() as conn:
        with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), params)
            return [dict(r) for r in cur.fetchall()]


def audit_shadow_parity(
    parent_id: str,
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Verify every branch has the exact canonical sequence and hashes."""
    initialize_parallel_shadow_store(path)

    def evaluate(
        canonical: list[dict[str, Any]],
        receipts: dict[str, list[dict[str, Any]]],
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        expected = [(int(r["event_seq"]), r["event_hash"]) for r in canonical]
        branch_results: dict[str, Any] = {}
        parity_ok = True
        for branch_key in BRANCH_KEYS:
            got = [(int(r["event_seq"]), r["event_hash"]) for r in receipts[branch_key]]
            missing_seq = [seq for seq, _ in expected if seq not in {x[0] for x in got}]
            extra_seq = [seq for seq, _ in got if seq not in {x[0] for x in expected}]
            hash_mismatch = [
                seq
                for seq, expected_hash in expected
                for got_seq, got_hash in got
                if got_seq == seq and got_hash != expected_hash
            ]
            ok = got == expected
            parity_ok = parity_ok and ok
            branch_results[branch_key] = {
                "ok": ok,
                "receipt_count": len(got),
                "missing_seq": missing_seq,
                "extra_seq": extra_seq,
                "hash_mismatch_seq": hash_mismatch,
            }
        issue_types = sorted({str(r["issue_type"]) for r in issues})
        if issue_types:
            parity_ok = False
        return {
            "parent_id": parent_id,
            "status": "PARITY_OK" if parity_ok else "PARITY_ERROR",
            "comparison_eligible": bool(parity_ok),
            "canonical_event_count": len(canonical),
            "expected_receipts_per_branch": len(canonical),
            "branches": branch_results,
            "issue_count": len(issues),
            "issue_types": issue_types,
            "execution_authority": EXECUTION_AUTHORITY,
            "event_version": PARALLEL_SHADOW_EVENT_VERSION,
        }

    if path is not None:
        with _local_sqlite_connect(path) as conn:
            canonical = [
                dict(r) for r in conn.execute(
                    "select * from protection_shadow_events where parent_id=? order by event_seq",
                    (parent_id,),
                ).fetchall()
            ]
            receipts = {
                key: [
                    dict(r) for r in conn.execute(
                        """select * from protection_shadow_branch_events
                           where parent_id=? and branch_key=? order by event_seq""",
                        (parent_id, key),
                    ).fetchall()
                ]
                for key in BRANCH_KEYS
            }
            issues = [
                dict(r) for r in conn.execute(
                    """select * from protection_shadow_parity_issues
                       where parent_id=? order by detected_at_ms,issue_id""",
                    (parent_id,),
                ).fetchall()
            ]
            result = evaluate(canonical, receipts, issues)
            if result["status"] == "PARITY_ERROR" and not issues:
                _record_issue_sqlite(
                    conn,
                    parent_id=parent_id,
                    issue_type="AUDIT_PARITY_MISMATCH",
                    details={"branches": result["branches"]},
                )
                conn.commit()
                result["issue_count"] = 1
                result["issue_types"] = ["AUDIT_PARITY_MISMATCH"]
            return result

    runtime = _runtime_persistence()
    if runtime.persistence_backend() == "sqlite":
        return audit_shadow_parity(parent_id, path=runtime.database_path())

    with runtime._postgres_connect() as conn:
        with conn.cursor(cursor_factory=runtime.psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "select * from protection_shadow_events where parent_id=%s order by event_seq",
                (parent_id,),
            )
            canonical = [dict(r) for r in cur.fetchall()]
            receipts = {}
            for key in BRANCH_KEYS:
                cur.execute(
                    """select * from protection_shadow_branch_events
                       where parent_id=%s and branch_key=%s order by event_seq""",
                    (parent_id, key),
                )
                receipts[key] = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """select * from protection_shadow_parity_issues
                   where parent_id=%s order by detected_at_ms,issue_id""",
                (parent_id,),
            )
            issues = [dict(r) for r in cur.fetchall()]
            result = evaluate(canonical, receipts, issues)
            if result["status"] == "PARITY_ERROR" and not issues:
                _record_issue_postgres(
                    cur,
                    parent_id=parent_id,
                    issue_type="AUDIT_PARITY_MISMATCH",
                    details={"branches": result["branches"]},
                )
                result["issue_count"] = 1
                result["issue_types"] = ["AUDIT_PARITY_MISMATCH"]
            return result


def shadow_event_summary(*, path: str | Path | None = None) -> dict[str, Any]:
    initialize_parallel_shadow_store(path)
    if path is not None:
        with _local_sqlite_connect(path) as conn:
            events = int(conn.execute("select count(*) from protection_shadow_events").fetchone()[0])
            receipts = int(conn.execute("select count(*) from protection_shadow_branch_events").fetchone()[0])
            issues = int(conn.execute("select count(*) from protection_shadow_parity_issues").fetchone()[0])
    else:
        runtime = _runtime_persistence()
        if runtime.persistence_backend() == "sqlite":
            return shadow_event_summary(path=runtime.database_path())
        with runtime._postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from protection_shadow_events")
                events = int(cur.fetchone()[0])
                cur.execute("select count(*) from protection_shadow_branch_events")
                receipts = int(cur.fetchone()[0])
                cur.execute("select count(*) from protection_shadow_parity_issues")
                issues = int(cur.fetchone()[0])
    return {
        "canonical_events": events,
        "branch_receipts": receipts,
        "expected_receipts_per_event": len(BRANCH_KEYS),
        "parity_issues": issues,
        "execution_authority": EXECUTION_AUTHORITY,
        "event_version": PARALLEL_SHADOW_EVENT_VERSION,
    }
