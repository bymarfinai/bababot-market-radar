from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from .binance import BinancePublicClient
from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    list_open_positions,
    persistence_backend,
)

PP_V3_STAGE2B1_VERSION = "pp-v3-stage2b1-fast-peak-observer"
_STORE_LOCK = threading.Lock()
_STORE_READY: set[tuple[str, str]] = set()
_LOOP_LOCK = threading.Lock()
_LOOP_STARTED = False
_STATE_LOCK = threading.Lock()


@dataclass(frozen=True)
class PeakState:
    running_peak_pct: float
    running_peak_at_ms: int
    previous_pnl_pct: float | None
    previous_observed_at_ms: int | None


_STATE: dict[str, PeakState] = {}


SQLITE_SCHEMA = """
create table if not exists pp_v3_fast_peak_observations (
    observation_id text primary key,
    position_id text not null,
    opened_at_ms integer not null,
    observed_at_ms integer not null,
    symbol text not null,
    side text not null,
    entry_price real not null,
    current_price real not null,
    current_pnl_pct real not null,
    previous_pnl_pct real,
    delta_pnl_pct_points real,
    running_peak_pct real not null,
    running_peak_at_ms integer not null,
    giveback_ratio real not null,
    seconds_since_peak real not null,
    sample_gap_ms integer,
    armed integer not null,
    position_status text not null,
    source text not null,
    created_at_ms integer not null
);
create index if not exists idx_pp_v3_fast_peak_position_time
on pp_v3_fast_peak_observations(position_id, observed_at_ms);
create index if not exists idx_pp_v3_fast_peak_time
on pp_v3_fast_peak_observations(observed_at_ms);
create index if not exists idx_pp_v3_fast_peak_armed_time
on pp_v3_fast_peak_observations(armed, observed_at_ms);
"""

POSTGRES_SCHEMA = """
create table if not exists pp_v3_fast_peak_observations (
    observation_id text primary key,
    position_id text not null,
    opened_at_ms bigint not null,
    observed_at_ms bigint not null,
    symbol text not null,
    side text not null,
    entry_price double precision not null,
    current_price double precision not null,
    current_pnl_pct double precision not null,
    previous_pnl_pct double precision,
    delta_pnl_pct_points double precision,
    running_peak_pct double precision not null,
    running_peak_at_ms bigint not null,
    giveback_ratio double precision not null,
    seconds_since_peak double precision not null,
    sample_gap_ms bigint,
    armed boolean not null,
    position_status text not null,
    source text not null,
    created_at_ms bigint not null
);
create index if not exists idx_pp_v3_fast_peak_position_time
on pp_v3_fast_peak_observations(position_id, observed_at_ms);
create index if not exists idx_pp_v3_fast_peak_time
on pp_v3_fast_peak_observations(observed_at_ms);
create index if not exists idx_pp_v3_fast_peak_armed_time
on pp_v3_fast_peak_observations(armed, observed_at_ms);
"""


def _cfg_float(name: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(value, hi))


def stage2b1_enabled() -> bool:
    return os.environ.get("PP_V3_STAGE2B1_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def stage2b1_start_ms() -> int:
    try:
        return int(os.environ.get("PP_V3_STAGE2B1_START_MS", "0") or 0)
    except (TypeError, ValueError):
        return 0


def stage2b1_poll_seconds() -> float:
    return _cfg_float("PP_V3_STAGE2B1_POLL_SECONDS", 5.0, 1.0, 15.0)


def stage2b1_arm_pct() -> float:
    return _cfg_float("PP_V3_STAGE2B1_ARM_PCT", 0.30, 0.05, 5.0)


def stage2b1_workers() -> int:
    return int(_cfg_float("PP_V3_STAGE2B1_WORKERS", 5.0, 1.0, 10.0))


def side_return_pct(side: str, entry_price: float, current_price: float) -> float:
    entry = float(entry_price)
    current = float(current_price)
    if entry <= 0.0:
        return 0.0
    raw = 100.0 * (current / entry - 1.0)
    return raw if str(side).upper() == "LONG" else -raw


def advance_peak_state(
    *,
    current_pnl_pct: float,
    observed_at_ms: int,
    arm_pct: float,
    previous: PeakState | None,
) -> tuple[PeakState, dict[str, Any]]:
    current = float(current_pnl_pct)
    observed = int(observed_at_ms)

    if previous is None or current > float(previous.running_peak_pct):
        running_peak = current
        running_peak_at = observed
    else:
        running_peak = float(previous.running_peak_pct)
        running_peak_at = int(previous.running_peak_at_ms)

    giveback_ratio = (
        max(0.0, (running_peak - current) / running_peak)
        if running_peak > 0.0
        else 0.0
    )
    seconds_since_peak = max(0.0, (observed - running_peak_at) / 1000.0)
    previous_pnl = None if previous is None else float(previous.previous_pnl_pct) if previous.previous_pnl_pct is not None else None
    previous_observed = None if previous is None else previous.previous_observed_at_ms
    delta = None if previous_pnl is None else current - previous_pnl
    sample_gap = None if previous_observed is None else observed - int(previous_observed)
    armed = running_peak >= float(arm_pct)

    state = PeakState(
        running_peak_pct=running_peak,
        running_peak_at_ms=running_peak_at,
        previous_pnl_pct=current,
        previous_observed_at_ms=observed,
    )
    metrics = {
        "previous_pnl_pct": previous_pnl,
        "delta_pnl_pct_points": delta,
        "running_peak_pct": running_peak,
        "running_peak_at_ms": running_peak_at,
        "giveback_ratio": giveback_ratio,
        "seconds_since_peak": seconds_since_peak,
        "sample_gap_ms": sample_gap,
        "armed": armed,
    }
    return state, metrics


def initialize_stage2b1_store() -> None:
    backend = persistence_backend()
    key = (backend, str(database_path()) if backend == "sqlite" else "postgres")
    with _STORE_LOCK:
        if key in _STORE_READY:
            return
        if backend == "sqlite":
            with _sqlite_connect(database_path()) as conn:
                conn.executescript(SQLITE_SCHEMA)
        else:
            with _postgres_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(POSTGRES_SCHEMA)
        _STORE_READY.add(key)


def _hydrate_state(position_id: str) -> PeakState | None:
    initialize_stage2b1_store()
    pid = str(position_id)
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                """
                select running_peak_pct,running_peak_at_ms,current_pnl_pct,observed_at_ms
                from pp_v3_fast_peak_observations
                where position_id=?
                order by observed_at_ms desc
                limit 1
                """,
                (pid,),
            ).fetchone()
            if row is None:
                return None
            return PeakState(
                running_peak_pct=float(row["running_peak_pct"]),
                running_peak_at_ms=int(row["running_peak_at_ms"]),
                previous_pnl_pct=float(row["current_pnl_pct"]),
                previous_observed_at_ms=int(row["observed_at_ms"]),
            )

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select running_peak_pct,running_peak_at_ms,current_pnl_pct,observed_at_ms
                from pp_v3_fast_peak_observations
                where position_id=%s
                order by observed_at_ms desc
                limit 1
                """,
                (pid,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return PeakState(
                running_peak_pct=float(row[0]),
                running_peak_at_ms=int(row[1]),
                previous_pnl_pct=float(row[2]),
                previous_observed_at_ms=int(row[3]),
            )


def _state_for(position_id: str) -> PeakState | None:
    pid = str(position_id)
    with _STATE_LOCK:
        if pid in _STATE:
            return _STATE[pid]
    hydrated = _hydrate_state(pid)
    if hydrated is not None:
        with _STATE_LOCK:
            _STATE[pid] = hydrated
    return hydrated


def _save_observation(row: dict[str, Any]) -> bool:
    initialize_stage2b1_store()
    values = (
        str(row["observation_id"]),
        str(row["position_id"]),
        int(row["opened_at_ms"]),
        int(row["observed_at_ms"]),
        str(row["symbol"]),
        str(row["side"]).upper(),
        float(row["entry_price"]),
        float(row["current_price"]),
        float(row["current_pnl_pct"]),
        None if row["previous_pnl_pct"] is None else float(row["previous_pnl_pct"]),
        None if row["delta_pnl_pct_points"] is None else float(row["delta_pnl_pct_points"]),
        float(row["running_peak_pct"]),
        int(row["running_peak_at_ms"]),
        float(row["giveback_ratio"]),
        float(row["seconds_since_peak"]),
        None if row["sample_gap_ms"] is None else int(row["sample_gap_ms"]),
        bool(row["armed"]),
        str(row["position_status"]).upper(),
        str(row["source"]),
        int(row["created_at_ms"]),
    )

    if persistence_backend() == "sqlite":
        sqlite_values = list(values)
        sqlite_values[16] = int(bool(sqlite_values[16]))
        with _sqlite_connect(database_path()) as conn:
            cur = conn.execute(
                """
                insert or ignore into pp_v3_fast_peak_observations (
                    observation_id,position_id,opened_at_ms,observed_at_ms,symbol,side,
                    entry_price,current_price,current_pnl_pct,previous_pnl_pct,
                    delta_pnl_pct_points,running_peak_pct,running_peak_at_ms,giveback_ratio,
                    seconds_since_peak,sample_gap_ms,armed,position_status,source,created_at_ms
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                tuple(sqlite_values),
            )
            return cur.rowcount > 0

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into pp_v3_fast_peak_observations (
                    observation_id,position_id,opened_at_ms,observed_at_ms,symbol,side,
                    entry_price,current_price,current_pnl_pct,previous_pnl_pct,
                    delta_pnl_pct_points,running_peak_pct,running_peak_at_ms,giveback_ratio,
                    seconds_since_peak,sample_gap_ms,armed,position_status,source,created_at_ms
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(observation_id) do nothing
                """,
                values,
            )
            return cur.rowcount > 0


def observe_position(
    client: BinancePublicClient,
    position: dict[str, Any],
    *,
    observed_at_ms: int | None = None,
) -> dict[str, Any]:
    pid = str(position["position_id"])
    symbol = str(position["symbol"]).upper()
    side = str(position["side"]).upper()
    entry = float(position["entry_price"])
    current = float(client.ticker_price(symbol))
    observed = int(observed_at_ms or time.time() * 1000)
    pnl = side_return_pct(side, entry, current)

    previous = _state_for(pid)
    state, metrics = advance_peak_state(
        current_pnl_pct=pnl,
        observed_at_ms=observed,
        arm_pct=stage2b1_arm_pct(),
        previous=previous,
    )

    row = {
        "observation_id": f"{pid}:PPV3B1:{observed}",
        "position_id": pid,
        "opened_at_ms": int(position.get("opened_at_ms") or observed),
        "observed_at_ms": observed,
        "symbol": symbol,
        "side": side,
        "entry_price": entry,
        "current_price": current,
        "current_pnl_pct": pnl,
        **metrics,
        "position_status": str(position.get("status") or "OPEN").upper(),
        "source": "TICKER_5S_SHADOW",
        "created_at_ms": int(time.time() * 1000),
    }
    inserted = _save_observation(row)
    if inserted:
        with _STATE_LOCK:
            _STATE[pid] = state
    row["inserted"] = inserted
    return row


def process_stage2b1_observations() -> dict[str, Any]:
    if not stage2b1_enabled():
        return {"status": "DISABLED", "processed": 0, "errors": []}

    start_ms = stage2b1_start_ms()
    if start_ms <= 0:
        return {
            "status": "WAITING_FOR_START_BOUNDARY",
            "processed": 0,
            "errors": [],
        }

    positions = [
        position
        for position in list_open_positions()
        if int(position.get("opened_at_ms") or 0) > start_ms
    ]
    if not positions:
        return {"status": "IDLE", "processed": 0, "errors": []}

    client = BinancePublicClient(timeout=3.0, retries=1)
    workers = max(1, min(stage2b1_workers(), len(positions)))
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(observe_position, client, position): position
            for position in positions
        }
        for future in as_completed(future_map):
            position = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append(
                    f"{position.get('position_id')}: "
                    f"{type(exc).__name__}: {str(exc)[:240]}"
                )

    open_ids = {str(position["position_id"]) for position in positions}
    with _STATE_LOCK:
        stale = [pid for pid in _STATE if pid not in open_ids]
        for pid in stale:
            _STATE.pop(pid, None)

    return {
        "status": "COMPLETE",
        "processed": len(results),
        "inserted": sum(bool(row.get("inserted")) for row in results),
        "armed": sum(bool(row.get("armed")) for row in results),
        "errors": errors,
        "results": results,
    }


def stage2b1_summary(*, recent_limit: int = 10) -> dict[str, Any]:
    initialize_stage2b1_store()
    safe_limit = max(1, min(int(recent_limit), 100))

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            agg = conn.execute(
                """
                select count(*) as rows,
                       count(distinct position_id) as positions,
                       sum(case when armed=1 then 1 else 0 end) as armed_rows,
                       min(observed_at_ms) as first_observed_at_ms,
                       max(observed_at_ms) as last_observed_at_ms
                from pp_v3_fast_peak_observations
                """
            ).fetchone()
            recent = [
                dict(row)
                for row in conn.execute(
                    """
                    select position_id,symbol,side,observed_at_ms,current_pnl_pct,
                           running_peak_pct,giveback_ratio,seconds_since_peak,armed
                    from pp_v3_fast_peak_observations
                    order by observed_at_ms desc
                    limit ?
                    """,
                    (safe_limit,),
                ).fetchall()
            ]
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select count(*) as rows,
                           count(distinct position_id) as positions,
                           count(*) filter (where armed) as armed_rows,
                           min(observed_at_ms) as first_observed_at_ms,
                           max(observed_at_ms) as last_observed_at_ms
                    from pp_v3_fast_peak_observations
                    """
                )
                agg = cur.fetchone()
                cur.execute(
                    """
                    select position_id,symbol,side,observed_at_ms,current_pnl_pct,
                           running_peak_pct,giveback_ratio,seconds_since_peak,armed
                    from pp_v3_fast_peak_observations
                    order by observed_at_ms desc
                    limit %s
                    """,
                    (safe_limit,),
                )
                recent = [
                    {
                        "position_id": row[0],
                        "symbol": row[1],
                        "side": row[2],
                        "observed_at_ms": int(row[3]),
                        "current_pnl_pct": float(row[4]),
                        "running_peak_pct": float(row[5]),
                        "giveback_ratio": float(row[6]),
                        "seconds_since_peak": float(row[7]),
                        "armed": bool(row[8]),
                    }
                    for row in cur.fetchall()
                ]

    if persistence_backend() == "sqlite":
        summary_row = dict(agg)
    else:
        summary_row = {
            "rows": int(agg[0] or 0),
            "positions": int(agg[1] or 0),
            "armed_rows": int(agg[2] or 0),
            "first_observed_at_ms": None if agg[3] is None else int(agg[3]),
            "last_observed_at_ms": None if agg[4] is None else int(agg[4]),
        }

    return {
        "version": PP_V3_STAGE2B1_VERSION,
        "enabled": stage2b1_enabled(),
        "start_ms": stage2b1_start_ms(),
        "poll_seconds": stage2b1_poll_seconds(),
        "arm_pct": stage2b1_arm_pct(),
        **summary_row,
        "recent": recent,
    }


def start_stage2b1_fast_peak_loop() -> bool:
    global _LOOP_STARTED
    if not stage2b1_enabled():
        return False
    if stage2b1_start_ms() <= 0:
        return False

    with _LOOP_LOCK:
        if _LOOP_STARTED:
            return False
        _LOOP_STARTED = True

    def _runner() -> None:
        while True:
            started = time.time()
            try:
                result = process_stage2b1_observations()
                if result.get("errors"):
                    print(
                        "PP-V3 Stage2B.1 fast observer: "
                        f"processed={result.get('processed', 0)} "
                        f"inserted={result.get('inserted', 0)} "
                        f"armed={result.get('armed', 0)} "
                        f"errors={len(result.get('errors') or [])}",
                        flush=True,
                    )
            except Exception as exc:
                print(
                    "PP-V3 Stage2B.1 fast observer error: "
                    f"{type(exc).__name__}: {str(exc)[:300]}",
                    flush=True,
                )

            elapsed = time.time() - started
            time.sleep(max(0.5, stage2b1_poll_seconds() - elapsed))

    threading.Thread(
        target=_runner,
        name="pp-v3-stage2b1-fast-peak-observer",
        daemon=True,
    ).start()
    return True
