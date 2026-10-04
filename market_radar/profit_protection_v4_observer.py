from __future__ import annotations

import json
import os
import statistics
import threading
import time
from dataclasses import dataclass
from typing import Any

from .binance import BinancePublicClient
from .profit_protection_v4_stage2d_shadow import process_observation as process_stage2d_shadow_observation
from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    list_open_positions,
    persistence_backend,
)

PP_V4_VERSION = "pp-v4-stage1-observability-v1"
PP_V4_SOURCE_NAME = "BINANCE_FUTURES_REST_TICKER_PRICE_ALL"
PP_V4_SOURCE_MODE = "PRIMARY"
PP_V4_FALLBACK_MODE = "NONE_FAIL_CLOSED"

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
create table if not exists pp_v4_observation_cycles (
    cycle_id text primary key,
    started_at_ms integer not null,
    received_at_ms integer,
    completed_at_ms integer not null,
    cycle_gap_ms integer,
    request_latency_ms integer,
    eligible_positions integer not null,
    observed_positions integer not null,
    missing_positions integer not null,
    duplicate_positions integer not null,
    status text not null,
    source_name text not null,
    source_mode text not null,
    error_text text,
    created_at_ms integer not null
);
create index if not exists idx_pp_v4_cycles_time
on pp_v4_observation_cycles(started_at_ms);

create table if not exists pp_v4_peak_observations (
    observation_id text primary key,
    cycle_id text not null,
    position_id text not null,
    opened_at_ms integer not null,
    observed_at_ms integer not null,
    source_event_at_ms integer,
    receive_at_ms integer not null,
    symbol text not null,
    side text not null,
    entry_price real not null,
    current_price real not null,
    current_pnl_pct real not null,
    previous_pnl_pct real,
    delta_pnl_pct_points real,
    running_observed_peak_pct real not null,
    running_observed_peak_at_ms integer not null,
    sample_gap_ms integer,
    armed integer not null,
    source_name text not null,
    source_mode text not null,
    source_sequence text,
    data_quality_json text not null,
    position_status text not null,
    created_at_ms integer not null
);
create index if not exists idx_pp_v4_obs_position_time
on pp_v4_peak_observations(position_id, observed_at_ms);
create index if not exists idx_pp_v4_obs_time
on pp_v4_peak_observations(observed_at_ms);
create index if not exists idx_pp_v4_obs_cycle
on pp_v4_peak_observations(cycle_id);
"""


POSTGRES_SCHEMA = """
create table if not exists pp_v4_observation_cycles (
    cycle_id text primary key,
    started_at_ms bigint not null,
    received_at_ms bigint,
    completed_at_ms bigint not null,
    cycle_gap_ms bigint,
    request_latency_ms bigint,
    eligible_positions integer not null,
    observed_positions integer not null,
    missing_positions integer not null,
    duplicate_positions integer not null,
    status text not null,
    source_name text not null,
    source_mode text not null,
    error_text text,
    created_at_ms bigint not null
);
create index if not exists idx_pp_v4_cycles_time
on pp_v4_observation_cycles(started_at_ms);

create table if not exists pp_v4_peak_observations (
    observation_id text primary key,
    cycle_id text not null,
    position_id text not null,
    opened_at_ms bigint not null,
    observed_at_ms bigint not null,
    source_event_at_ms bigint,
    receive_at_ms bigint not null,
    symbol text not null,
    side text not null,
    entry_price double precision not null,
    current_price double precision not null,
    current_pnl_pct double precision not null,
    previous_pnl_pct double precision,
    delta_pnl_pct_points double precision,
    running_observed_peak_pct double precision not null,
    running_observed_peak_at_ms bigint not null,
    sample_gap_ms bigint,
    armed boolean not null,
    source_name text not null,
    source_mode text not null,
    source_sequence text,
    data_quality_json text not null,
    position_status text not null,
    created_at_ms bigint not null
);
create index if not exists idx_pp_v4_obs_position_time
on pp_v4_peak_observations(position_id, observed_at_ms);
create index if not exists idx_pp_v4_obs_time
on pp_v4_peak_observations(observed_at_ms);
create index if not exists idx_pp_v4_obs_cycle
on pp_v4_peak_observations(cycle_id);
"""


PREREGISTERED_GATES = {
    "minimum_closed_matched_trades": 100,
    "minimum_true_mfe_ge_0_30_trades": 50,
    "data_quality": {
        "cycle_error_rate_max_pct": 2.0,
        "missing_position_rate_max_pct": 2.0,
        "median_sample_gap_max_ms": 5750,
        "p90_sample_gap_max_ms": 7500,
        "max_sample_gap_ms": 20000,
        "duplicate_observation_ids_allowed": 0,
    },
    "v4_2_observability": {
        "median_capture_uplift_min_pp": 3.0,
        "weighted_capture_uplift_min_pp": 3.0,
    },
    "v4_3_distribution": {
        "ge90_share_uplift_min_pp": 5.0,
        "lt80_share_reduction_min_pp": 5.0,
        "p10_uplift_min_pp": 5.0,
        "p25_uplift_min_pp": 3.0,
        "late_cohort_ge90_uplift_min_pp": 0.0,
        "late_cohort_lt80_change_max_pp": 0.0,
    },
}


def _cfg_float(name: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(value, hi))


def pp_v4_enabled() -> bool:
    return os.environ.get("PP_V4_STAGE1_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def pp_v4_start_ms() -> int:
    try:
        return int(os.environ.get("PP_V4_STAGE1_START_MS", "0") or 0)
    except (TypeError, ValueError):
        return 0


def pp_v4_poll_seconds() -> float:
    return _cfg_float("PP_V4_STAGE1_POLL_SECONDS", 5.0, 2.0, 15.0)


def pp_v4_arm_pct() -> float:
    return _cfg_float("PP_V4_STAGE1_ARM_PCT", 0.30, 0.05, 5.0)


def side_return_pct(side: str, entry_price: float, current_price: float) -> float:
    entry = float(entry_price)
    current = float(current_price)
    if entry <= 0.0 or current <= 0.0:
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
        peak_at = observed
    else:
        running_peak = float(previous.running_peak_pct)
        peak_at = int(previous.running_peak_at_ms)

    previous_pnl = None if previous is None else previous.previous_pnl_pct
    previous_observed = None if previous is None else previous.previous_observed_at_ms
    delta = None if previous_pnl is None else current - float(previous_pnl)
    sample_gap = None if previous_observed is None else observed - int(previous_observed)

    state = PeakState(
        running_peak_pct=running_peak,
        running_peak_at_ms=peak_at,
        previous_pnl_pct=current,
        previous_observed_at_ms=observed,
    )
    return state, {
        "previous_pnl_pct": previous_pnl,
        "delta_pnl_pct_points": delta,
        "running_observed_peak_pct": running_peak,
        "running_observed_peak_at_ms": peak_at,
        "sample_gap_ms": sample_gap,
        "armed": running_peak >= float(arm_pct),
    }


def initialize_pp_v4_store() -> None:
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


def _eligible_positions() -> list[dict[str, Any]]:
    start_ms = pp_v4_start_ms()
    positions: list[dict[str, Any]] = []
    for row in list_open_positions():
        if int(row.get("opened_at_ms") or 0) <= start_ms:
            continue
        mode = str(row.get("mode") or "PAPER").upper()
        if mode != "PAPER":
            continue
        positions.append(row)
    return positions


def _hydrate_state(position_id: str) -> PeakState | None:
    initialize_pp_v4_store()
    pid = str(position_id)
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                """
                select running_observed_peak_pct,running_observed_peak_at_ms,
                       current_pnl_pct,observed_at_ms
                from pp_v4_peak_observations
                where position_id=?
                order by observed_at_ms desc
                limit 1
                """,
                (pid,),
            ).fetchone()
            if row is None:
                return None
            return PeakState(
                running_peak_pct=float(row["running_observed_peak_pct"]),
                running_peak_at_ms=int(row["running_observed_peak_at_ms"]),
                previous_pnl_pct=float(row["current_pnl_pct"]),
                previous_observed_at_ms=int(row["observed_at_ms"]),
            )

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select running_observed_peak_pct,running_observed_peak_at_ms,
                       current_pnl_pct,observed_at_ms
                from pp_v4_peak_observations
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


def _last_cycle_receive_ms() -> int | None:
    initialize_pp_v4_store()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                """
                select received_at_ms
                from pp_v4_observation_cycles
                where received_at_ms is not null
                order by started_at_ms desc
                limit 1
                """
            ).fetchone()
            return None if row is None else int(row["received_at_ms"])
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select received_at_ms
                from pp_v4_observation_cycles
                where received_at_ms is not null
                order by started_at_ms desc
                limit 1
                """
            )
            row = cur.fetchone()
            return None if row is None else int(row[0])


def _save_cycle(row: dict[str, Any]) -> None:
    initialize_pp_v4_store()
    values = (
        str(row["cycle_id"]),
        int(row["started_at_ms"]),
        None if row.get("received_at_ms") is None else int(row["received_at_ms"]),
        int(row["completed_at_ms"]),
        None if row.get("cycle_gap_ms") is None else int(row["cycle_gap_ms"]),
        None if row.get("request_latency_ms") is None else int(row["request_latency_ms"]),
        int(row["eligible_positions"]),
        int(row["observed_positions"]),
        int(row["missing_positions"]),
        int(row.get("duplicate_positions") or 0),
        str(row["status"]),
        str(row["source_name"]),
        str(row["source_mode"]),
        row.get("error_text"),
        int(row["created_at_ms"]),
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                insert or replace into pp_v4_observation_cycles (
                    cycle_id,started_at_ms,received_at_ms,completed_at_ms,
                    cycle_gap_ms,request_latency_ms,eligible_positions,
                    observed_positions,missing_positions,duplicate_positions,status,
                    source_name,source_mode,error_text,created_at_ms
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
        return

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into pp_v4_observation_cycles (
                    cycle_id,started_at_ms,received_at_ms,completed_at_ms,
                    cycle_gap_ms,request_latency_ms,eligible_positions,
                    observed_positions,missing_positions,duplicate_positions,status,
                    source_name,source_mode,error_text,created_at_ms
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(cycle_id) do update set
                    received_at_ms=excluded.received_at_ms,
                    completed_at_ms=excluded.completed_at_ms,
                    cycle_gap_ms=excluded.cycle_gap_ms,
                    request_latency_ms=excluded.request_latency_ms,
                    eligible_positions=excluded.eligible_positions,
                    observed_positions=excluded.observed_positions,
                    missing_positions=excluded.missing_positions,
                    duplicate_positions=excluded.duplicate_positions,
                    status=excluded.status,
                    error_text=excluded.error_text
                """,
                values,
            )


def _save_observation(row: dict[str, Any]) -> bool:
    initialize_pp_v4_store()
    values = (
        str(row["observation_id"]),
        str(row["cycle_id"]),
        str(row["position_id"]),
        int(row["opened_at_ms"]),
        int(row["observed_at_ms"]),
        row.get("source_event_at_ms"),
        int(row["receive_at_ms"]),
        str(row["symbol"]),
        str(row["side"]).upper(),
        float(row["entry_price"]),
        float(row["current_price"]),
        float(row["current_pnl_pct"]),
        row.get("previous_pnl_pct"),
        row.get("delta_pnl_pct_points"),
        float(row["running_observed_peak_pct"]),
        int(row["running_observed_peak_at_ms"]),
        row.get("sample_gap_ms"),
        bool(row["armed"]),
        str(row["source_name"]),
        str(row["source_mode"]),
        row.get("source_sequence"),
        json.dumps(row.get("data_quality") or {}, sort_keys=True),
        str(row["position_status"]).upper(),
        int(row["created_at_ms"]),
    )

    if persistence_backend() == "sqlite":
        sqlite_values = list(values)
        sqlite_values[17] = int(bool(sqlite_values[17]))
        with _sqlite_connect(database_path()) as conn:
            cur = conn.execute(
                """
                insert or ignore into pp_v4_peak_observations (
                    observation_id,cycle_id,position_id,opened_at_ms,observed_at_ms,
                    source_event_at_ms,receive_at_ms,symbol,side,entry_price,
                    current_price,current_pnl_pct,previous_pnl_pct,delta_pnl_pct_points,
                    running_observed_peak_pct,running_observed_peak_at_ms,sample_gap_ms,
                    armed,source_name,source_mode,source_sequence,data_quality_json,
                    position_status,created_at_ms
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                tuple(sqlite_values),
            )
            return cur.rowcount > 0

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into pp_v4_peak_observations (
                    observation_id,cycle_id,position_id,opened_at_ms,observed_at_ms,
                    source_event_at_ms,receive_at_ms,symbol,side,entry_price,
                    current_price,current_pnl_pct,previous_pnl_pct,delta_pnl_pct_points,
                    running_observed_peak_pct,running_observed_peak_at_ms,sample_gap_ms,
                    armed,source_name,source_mode,source_sequence,data_quality_json,
                    position_status,created_at_ms
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(observation_id) do nothing
                """,
                values,
            )
            return cur.rowcount > 0


def process_pp_v4_cycle(
    *,
    client: BinancePublicClient | None = None,
    started_at_ms: int | None = None,
) -> dict[str, Any]:
    if not pp_v4_enabled():
        return {"status": "DISABLED", "observed_positions": 0}

    start_boundary = pp_v4_start_ms()
    if start_boundary <= 0:
        return {"status": "WAITING_FOR_START_BOUNDARY", "observed_positions": 0}

    positions = _eligible_positions()
    if not positions:
        return {"status": "IDLE", "observed_positions": 0}

    initialize_pp_v4_store()
    client = client or BinancePublicClient(timeout=3.0, retries=1)
    started = int(started_at_ms or time.time() * 1000)
    cycle_id = f"PPV4:{started}"
    previous_receive = _last_cycle_receive_ms()
    request_started = int(time.time() * 1000)

    try:
        prices = client.ticker_prices()
        receive_at = int(time.time() * 1000)
        request_latency = max(0, receive_at - request_started)
        cycle_gap = (
            None if previous_receive is None else max(0, receive_at - previous_receive)
        )

        observed = 0
        missing = 0
        duplicates = 0
        rows: list[dict[str, Any]] = []
        open_ids = {str(position["position_id"]) for position in positions}

        for position in positions:
            pid = str(position["position_id"])
            symbol = str(position["symbol"]).upper()
            current_price = prices.get(symbol)
            if current_price is None:
                missing += 1
                continue

            side = str(position["side"]).upper()
            entry = float(position["entry_price"])
            pnl = side_return_pct(side, entry, current_price)
            previous = _state_for(pid)
            state, metrics = advance_peak_state(
                current_pnl_pct=pnl,
                observed_at_ms=receive_at,
                arm_pct=pp_v4_arm_pct(),
                previous=previous,
            )
            quality = {
                "request_latency_ms": request_latency,
                "cycle_gap_ms": cycle_gap,
                "source_event_timestamp_available": False,
                "fallback_used": False,
            }
            row = {
                "observation_id": f"{pid}:PPV4:{receive_at}",
                "cycle_id": cycle_id,
                "position_id": pid,
                "opened_at_ms": int(position["opened_at_ms"]),
                "observed_at_ms": receive_at,
                "source_event_at_ms": None,
                "receive_at_ms": receive_at,
                "symbol": symbol,
                "side": side,
                "entry_price": entry,
                "current_price": float(current_price),
                "current_pnl_pct": pnl,
                **metrics,
                "source_name": PP_V4_SOURCE_NAME,
                "source_mode": PP_V4_SOURCE_MODE,
                "source_sequence": None,
                "data_quality": quality,
                "position_status": str(position.get("status") or "OPEN").upper(),
                "created_at_ms": int(time.time() * 1000),
            }
            inserted = _save_observation(row)
            if inserted:
                with _STATE_LOCK:
                    _STATE[pid] = state
                row["stage2d_shadow"] = process_stage2d_shadow_observation(row)
                observed += 1
            else:
                row["stage2d_shadow"] = {"status": "SKIPPED_DUPLICATE_V4_OBSERVATION"}
                duplicates += 1
            row["inserted"] = inserted
            rows.append(row)

        with _STATE_LOCK:
            stale = [pid for pid in _STATE if pid not in open_ids]
            for pid in stale:
                _STATE.pop(pid, None)

        status = "COMPLETE" if missing == 0 and duplicates == 0 else "PARTIAL"
        completed = int(time.time() * 1000)
        _save_cycle(
            {
                "cycle_id": cycle_id,
                "started_at_ms": started,
                "received_at_ms": receive_at,
                "completed_at_ms": completed,
                "cycle_gap_ms": cycle_gap,
                "request_latency_ms": request_latency,
                "eligible_positions": len(positions),
                "observed_positions": observed,
                "missing_positions": missing,
                "duplicate_positions": duplicates,
                "status": status,
                "source_name": PP_V4_SOURCE_NAME,
                "source_mode": PP_V4_SOURCE_MODE,
                "error_text": None,
                "created_at_ms": completed,
            }
        )
        return {
            "status": status,
            "cycle_id": cycle_id,
            "eligible_positions": len(positions),
            "observed_positions": observed,
            "missing_positions": missing,
            "duplicate_positions": duplicates,
            "request_latency_ms": request_latency,
            "cycle_gap_ms": cycle_gap,
            "rows": rows,
        }
    except Exception as exc:
        completed = int(time.time() * 1000)
        _save_cycle(
            {
                "cycle_id": cycle_id,
                "started_at_ms": started,
                "received_at_ms": None,
                "completed_at_ms": completed,
                "cycle_gap_ms": None,
                "request_latency_ms": max(0, completed - request_started),
                "eligible_positions": len(positions),
                "observed_positions": 0,
                "missing_positions": len(positions),
                "duplicate_positions": 0,
                "status": "ERROR",
                "source_name": PP_V4_SOURCE_NAME,
                "source_mode": PP_V4_SOURCE_MODE,
                "error_text": f"{type(exc).__name__}: {str(exc)[:500]}",
                "created_at_ms": completed,
            }
        )
        return {
            "status": "ERROR",
            "eligible_positions": len(positions),
            "observed_positions": 0,
            "missing_positions": len(positions),
            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
        }


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * float(q)
    lo = int(position)
    hi = min(lo + 1, len(ordered) - 1)
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def pp_v4_summary(*, recent_limit: int = 10) -> dict[str, Any]:
    initialize_pp_v4_store()
    safe_limit = max(1, min(int(recent_limit), 100))
    cycle_gaps: list[float] = []
    sample_gaps: list[float] = []

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            obs = conn.execute(
                """
                select count(*) rows,count(distinct position_id) positions,
                       sum(case when armed=1 then 1 else 0 end) armed_rows,
                       min(observed_at_ms) first_ms,max(observed_at_ms) last_ms
                from pp_v4_peak_observations
                """
            ).fetchone()
            cyc = conn.execute(
                """
                select count(*) cycles,
                       sum(case when status='ERROR' then 1 else 0 end) error_cycles,
                       sum(eligible_positions) eligible,
                       sum(missing_positions) missing,
                       sum(duplicate_positions) duplicates
                from pp_v4_observation_cycles
                """
            ).fetchone()
            cycle_gaps = [
                float(row["cycle_gap_ms"])
                for row in conn.execute(
                    """
                    select cycle_gap_ms from pp_v4_observation_cycles
                    where cycle_gap_ms is not null
                    order by started_at_ms desc limit 10000
                    """
                ).fetchall()
            ]
            sample_gaps = [
                float(row["sample_gap_ms"])
                for row in conn.execute(
                    """
                    select sample_gap_ms from pp_v4_peak_observations
                    where sample_gap_ms is not null
                    order by observed_at_ms desc limit 20000
                    """
                ).fetchall()
            ]
            recent = [
                dict(row)
                for row in conn.execute(
                    """
                    select position_id,symbol,side,observed_at_ms,current_pnl_pct,
                           running_observed_peak_pct,sample_gap_ms,armed
                    from pp_v4_peak_observations
                    order by observed_at_ms desc limit ?
                    """,
                    (safe_limit,),
                ).fetchall()
            ]
            obs_row = dict(obs)
            cyc_row = dict(cyc)
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select count(*),count(distinct position_id),
                           count(*) filter (where armed),
                           min(observed_at_ms),max(observed_at_ms)
                    from pp_v4_peak_observations
                    """
                )
                obs = cur.fetchone()
                cur.execute(
                    """
                    select count(*),
                           count(*) filter (where status='ERROR'),
                           coalesce(sum(eligible_positions),0),
                           coalesce(sum(missing_positions),0),
                           coalesce(sum(duplicate_positions),0)
                    from pp_v4_observation_cycles
                    """
                )
                cyc = cur.fetchone()
                cur.execute(
                    """
                    select cycle_gap_ms from pp_v4_observation_cycles
                    where cycle_gap_ms is not null
                    order by started_at_ms desc limit 10000
                    """
                )
                cycle_gaps = [float(row[0]) for row in cur.fetchall()]
                cur.execute(
                    """
                    select sample_gap_ms from pp_v4_peak_observations
                    where sample_gap_ms is not null
                    order by observed_at_ms desc limit 20000
                    """
                )
                sample_gaps = [float(row[0]) for row in cur.fetchall()]
                cur.execute(
                    """
                    select position_id,symbol,side,observed_at_ms,current_pnl_pct,
                           running_observed_peak_pct,sample_gap_ms,armed
                    from pp_v4_peak_observations
                    order by observed_at_ms desc limit %s
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
                        "running_observed_peak_pct": float(row[5]),
                        "sample_gap_ms": None if row[6] is None else int(row[6]),
                        "armed": bool(row[7]),
                    }
                    for row in cur.fetchall()
                ]
            obs_row = {
                "rows": int(obs[0] or 0),
                "positions": int(obs[1] or 0),
                "armed_rows": int(obs[2] or 0),
                "first_ms": None if obs[3] is None else int(obs[3]),
                "last_ms": None if obs[4] is None else int(obs[4]),
            }
            cyc_row = {
                "cycles": int(cyc[0] or 0),
                "error_cycles": int(cyc[1] or 0),
                "eligible": int(cyc[2] or 0),
                "missing": int(cyc[3] or 0),
                "duplicates": int(cyc[4] or 0),
            }

    cycles = int(cyc_row.get("cycles") or 0)
    errors = int(cyc_row.get("error_cycles") or 0)
    eligible = int(cyc_row.get("eligible") or 0)
    missing = int(cyc_row.get("missing") or 0)
    duplicates = int(cyc_row.get("duplicates") or 0)

    return {
        "version": PP_V4_VERSION,
        "status": "ACTIVE" if pp_v4_enabled() else "DISABLED",
        "enabled": pp_v4_enabled(),
        "start_ms": pp_v4_start_ms(),
        "poll_seconds": pp_v4_poll_seconds(),
        "arm_pct": pp_v4_arm_pct(),
        "source_name": PP_V4_SOURCE_NAME,
        "source_mode": PP_V4_SOURCE_MODE,
        "fallback_mode": PP_V4_FALLBACK_MODE,
        "rows": int(obs_row.get("rows") or 0),
        "positions": int(obs_row.get("positions") or 0),
        "armed_rows": int(obs_row.get("armed_rows") or 0),
        "first_observed_at_ms": obs_row.get("first_ms"),
        "last_observed_at_ms": obs_row.get("last_ms"),
        "cycles": cycles,
        "error_cycles": errors,
        "cycle_error_rate_pct": (100.0 * errors / cycles) if cycles else 0.0,
        "eligible_position_samples": eligible,
        "missing_position_samples": missing,
        "missing_position_rate_pct": (100.0 * missing / eligible) if eligible else 0.0,
        "duplicate_observation_attempts": duplicates,
        "sample_gap_ms": {
            "p10": _percentile(sample_gaps, 0.10),
            "median": statistics.median(sample_gaps) if sample_gaps else None,
            "p90": _percentile(sample_gaps, 0.90),
            "max": max(sample_gaps) if sample_gaps else None,
        },
        "cycle_gap_ms": {
            "p10": _percentile(cycle_gaps, 0.10),
            "median": statistics.median(cycle_gaps) if cycle_gaps else None,
            "p90": _percentile(cycle_gaps, 0.90),
            "max": max(cycle_gaps) if cycle_gaps else None,
        },
        "preregistered_gates": PREREGISTERED_GATES,
        "recent": recent,
    }


def start_pp_v4_observer_loop() -> bool:
    global _LOOP_STARTED
    if not pp_v4_enabled():
        return False
    if pp_v4_start_ms() <= 0:
        return False

    with _LOOP_LOCK:
        if _LOOP_STARTED:
            return False
        _LOOP_STARTED = True

    def _runner() -> None:
        while True:
            started = time.time()
            try:
                result = process_pp_v4_cycle()
                if result.get("status") in {"ERROR", "PARTIAL"}:
                    print(
                        "PP-V4 Stage1 observer: "
                        f"status={result.get('status')} "
                        f"eligible={result.get('eligible_positions', 0)} "
                        f"observed={result.get('observed_positions', 0)} "
                        f"missing={result.get('missing_positions', 0)}",
                        flush=True,
                    )
            except Exception as exc:
                print(
                    "PP-V4 Stage1 observer error: "
                    f"{type(exc).__name__}: {str(exc)[:300]}",
                    flush=True,
                )
            elapsed = time.time() - started
            time.sleep(max(0.25, pp_v4_poll_seconds() - elapsed))

    threading.Thread(
        target=_runner,
        name="pp-v4-stage1-observability",
        daemon=True,
    ).start()
    return True
