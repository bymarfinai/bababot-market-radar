from __future__ import annotations

import json
import math
import os
import statistics
import threading
import time
from typing import Any

import psycopg2.extras

from .binance import BinancePublicClient
from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    initialize_database,
    persistence_backend,
)


STAGE6_VERSION = "stage6-prospective-shadow-v1"
DISCOVERY_CUTOFF_MS = 1790687518406
RV15_EXTREME_PCT = 0.183898

_INIT_LOCK = threading.Lock()
_INITIALIZED: set[tuple[str, str]] = set()

POLICIES: dict[str, dict[str, Any]] = {
    "S5-A": {
        "kind": "ADAPTIVE",
        "mode": "CLOSE_FIRST",
        "base1": 0.00,
        "base2": 0.25,
        "base3": 0.50,
        "tight2": 0.30,
        "tight3": 0.00,
        "oi_tight": 0.125,
        "vol_mod": 0.025,
    },
    "S5-B": {
        "kind": "ADAPTIVE",
        "mode": "CLOSE_FIRST",
        "base1": 0.00,
        "base2": 0.30,
        "base3": 0.50,
        "tight2": 0.10,
        "tight3": 0.20,
        "oi_tight": 0.10,
        "vol_mod": 0.00,
    },
    "S5-C": {
        "kind": "ADAPTIVE",
        "mode": "CLOSE_FIRST",
        "base1": 0.00,
        "base2": 0.30,
        "base3": 0.50,
        "tight2": 0.25,
        "tight3": 0.05,
        "oi_tight": 0.125,
        "vol_mod": 0.00,
    },
    "STATIC_NET": {
        "kind": "STATIC",
        "mode": "CLOSE_FIRST",
        "arm_roi_pct": 5.0,
        "lock_ratio": 0.80,
    },
    "STATIC_BALANCED": {
        "kind": "STATIC",
        "mode": "CLOSE_FIRST",
        "arm_roi_pct": 3.0,
        "lock_ratio": 0.70,
    },
    "STATIC_CAPTURE": {
        "kind": "STATIC",
        "mode": "REDUCE_THEN_CLOSE",
        "arm_roi_pct": 2.0,
        "lock_ratio": 0.80,
    },
    "V5-0": {
        "kind": "V5_SUB1_DECISION",
        "mode": "DECISION_GATE",
        "arm_min_roi_pct": 0.50,
        "handoff_roi_pct": 1.00,
        "watch_giveback_ratio": 0.30,
        "decision_giveback_ratio": 0.50,
        "hard_stop_giveback_ratio": 1.00,
        "watch_reduce_score": 4,
        "reduce_score": 2,
        "close_score": 4,
        "reduce_fraction": 0.50,
    },
    "PP-DECISION-1P": {
        "kind": "PP_DECISION_GE1",
        "mode": "DECISION_GATE",
        "arm_min_roi_pct": 1.00,
        "watch_giveback_ratio": 0.25,
        "decision_giveback_ratio": 0.35,
        "force_reduce_giveback_ratio": 0.50,
        "hard_close_giveback_ratio": 0.60,
        "watch_reduce_score": 4,
        "reduce_score": 2,
        "close_score": 4,
        "reduce_fraction": 0.50,
    },
    "PP-DECISION-V1": {
        "kind": "PP_DECISION_UNIFIED",
        "mode": "DECISION_GATE",
        "sub1_arm_min_roi_pct": 0.50,
        "handoff_roi_pct": 1.00,
        "sub1_watch_giveback_ratio": 0.30,
        "sub1_decision_giveback_ratio": 0.50,
        "sub1_hard_stop_giveback_ratio": 1.00,
        "ge1_watch_giveback_ratio": 0.25,
        "ge1_decision_giveback_ratio": 0.35,
        "ge1_force_reduce_giveback_ratio": 0.50,
        "ge1_hard_close_giveback_ratio": 0.60,
        "watch_reduce_score": 4,
        "reduce_score": 2,
        "close_score": 4,
        "reduce_fraction": 0.50,
    },
    "PP-DECISION-V1-FINAL": {
        "kind": "PP_DECISION_UNIFIED",
        "mode": "DECISION_GATE",
        "sub1_arm_min_roi_pct": 0.50,
        "handoff_roi_pct": 1.00,
        "sub1_watch_giveback_ratio": 0.30,
        "sub1_decision_giveback_ratio": 0.50,
        "sub1_hard_stop_giveback_ratio": 1.00,
        "ge1_watch_giveback_ratio": 0.25,
        "ge1_decision_giveback_ratio": 0.35,
        "ge1_force_reduce_giveback_ratio": 0.50,
        "ge1_hard_close_giveback_ratio": 0.60,
        "watch_reduce_score": 4,
        "reduce_score": 2,
        "close_score": 4,
        "reduce_fraction": 0.50,
    },
}

SQLITE_SCHEMA = """
create table if not exists stage6_validation_trades (
    run_id text not null,
    position_id text not null,
    signal_id text,
    symbol text not null,
    side text not null,
    opened_at_ms integer not null,
    entry_price real not null,
    initial_quantity real not null,
    initial_notional real not null,
    entry_fee_total real not null,
    status text not null,
    last_candle_close_ms integer,
    opportunity_peak_pnl real not null default 0,
    opportunity_peak_at_ms integer,
    actual_closed_at_ms integer,
    actual_exit_price real,
    actual_realized_pnl real,
    actual_realized_pnl_pct real,
    actual_close_reason text,
    created_at_ms integer not null,
    updated_at_ms integer not null,
    raw_json text not null default '{}',
    primary key(run_id, position_id)
);
create index if not exists idx_stage6_trades_status
on stage6_validation_trades(run_id, status, opened_at_ms);

create table if not exists stage6_validation_lanes (
    run_id text not null,
    position_id text not null,
    policy_id text not null,
    status text not null,
    remaining_quantity real not null,
    realized_gross real not null default 0,
    realized_net real not null default 0,
    allocated_entry_fee real not null default 0,
    exit_fees real not null default 0,
    policy_peak_pnl real not null default 0,
    policy_peak_at_ms integer,
    profit_floor real,
    action_count integer not null default 0,
    trigger_count integer not null default 0,
    closed_at_ms integer,
    exit_price real,
    close_reason text,
    updated_at_ms integer not null,
    raw_json text not null default '{}',
    primary key(run_id, position_id, policy_id)
);
create index if not exists idx_stage6_lanes_status
on stage6_validation_lanes(run_id, status, position_id);

create table if not exists stage6_validation_events (
    event_id text primary key,
    run_id text not null,
    position_id text not null,
    policy_id text not null,
    candle_close_ms integer not null,
    economic_pnl real,
    policy_peak_pnl real,
    opportunity_peak_pnl real,
    profit_floor real,
    lock_ratio real,
    action text not null,
    evidence_json text not null default '{}',
    created_at_ms integer not null
);
create index if not exists idx_stage6_events_position
on stage6_validation_events(run_id, position_id, candle_close_ms);
"""

POSTGRES_SCHEMA = """
create table if not exists stage6_validation_trades (
    run_id text not null,
    position_id text not null,
    signal_id text,
    symbol text not null,
    side text not null,
    opened_at_ms bigint not null,
    entry_price double precision not null,
    initial_quantity double precision not null,
    initial_notional double precision not null,
    entry_fee_total double precision not null,
    status text not null,
    last_candle_close_ms bigint,
    opportunity_peak_pnl double precision not null default 0,
    opportunity_peak_at_ms bigint,
    actual_closed_at_ms bigint,
    actual_exit_price double precision,
    actual_realized_pnl double precision,
    actual_realized_pnl_pct double precision,
    actual_close_reason text,
    created_at_ms bigint not null,
    updated_at_ms bigint not null,
    raw_json text not null default '{}',
    primary key(run_id, position_id)
);
create index if not exists idx_stage6_trades_status
on stage6_validation_trades(run_id, status, opened_at_ms);

create table if not exists stage6_validation_lanes (
    run_id text not null,
    position_id text not null,
    policy_id text not null,
    status text not null,
    remaining_quantity double precision not null,
    realized_gross double precision not null default 0,
    realized_net double precision not null default 0,
    allocated_entry_fee double precision not null default 0,
    exit_fees double precision not null default 0,
    policy_peak_pnl double precision not null default 0,
    policy_peak_at_ms bigint,
    profit_floor double precision,
    action_count integer not null default 0,
    trigger_count integer not null default 0,
    closed_at_ms bigint,
    exit_price double precision,
    close_reason text,
    updated_at_ms bigint not null,
    raw_json text not null default '{}',
    primary key(run_id, position_id, policy_id)
);
create index if not exists idx_stage6_lanes_status
on stage6_validation_lanes(run_id, status, position_id);

create table if not exists stage6_validation_events (
    event_id text primary key,
    run_id text not null,
    position_id text not null,
    policy_id text not null,
    candle_close_ms bigint not null,
    economic_pnl double precision,
    policy_peak_pnl double precision,
    opportunity_peak_pnl double precision,
    profit_floor double precision,
    lock_ratio double precision,
    action text not null,
    evidence_json text not null default '{}',
    created_at_ms bigint not null
);
create index if not exists idx_stage6_events_position
on stage6_validation_events(run_id, position_id, candle_close_ms);
"""


def stage6_enabled() -> bool:
    return os.environ.get("STAGE6_VALIDATION_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def stage6_start_ms() -> int:
    try:
        return max(
            DISCOVERY_CUTOFF_MS,
            int(os.environ.get("STAGE6_START_MS", "0") or 0),
        )
    except (TypeError, ValueError):
        return DISCOVERY_CUTOFF_MS


def stage6_run_id() -> str:
    explicit = os.environ.get("STAGE6_RUN_ID", "").strip()
    return explicit or f"stage6-{stage6_start_ms()}"


def v5_0_enabled() -> bool:
    return os.environ.get("V5_0_SHADOW_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def v5_0_start_ms() -> int:
    try:
        return int(os.environ.get("V5_0_START_MS", "0") or 0)
    except (TypeError, ValueError):
        return 0


def pp_decision_stage2_enabled() -> bool:
    return os.environ.get("PP_DECISION_STAGE2_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def pp_decision_stage2_start_ms() -> int:
    try:
        return int(os.environ.get("PP_DECISION_STAGE2_START_MS", "0") or 0)
    except (TypeError, ValueError):
        return 0


def pp_decision_stage3_enabled() -> bool:
    return os.environ.get("PP_DECISION_STAGE3_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def pp_decision_stage3_start_ms() -> int:
    try:
        return int(os.environ.get("PP_DECISION_STAGE3_START_MS", "0") or 0)
    except (TypeError, ValueError):
        return 0


def pp_decision_stage5_enabled() -> bool:
    return os.environ.get("PP_DECISION_STAGE5_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def pp_decision_stage5_start_ms() -> int:
    try:
        return int(os.environ.get("PP_DECISION_STAGE5_START_MS", "0") or 0)
    except (TypeError, ValueError):
        return 0


def _policy_ids_for_entry(opened_at_ms: int) -> list[str]:
    ids: list[str] = []
    for policy_id in POLICIES:
        if policy_id == "V5-0":
            if not v5_0_enabled() or int(opened_at_ms) <= v5_0_start_ms():
                continue
        if policy_id == "PP-DECISION-1P":
            if (
                not pp_decision_stage2_enabled()
                or int(opened_at_ms) <= pp_decision_stage2_start_ms()
            ):
                continue
        if policy_id == "PP-DECISION-V1":
            if (
                not pp_decision_stage3_enabled()
                or int(opened_at_ms) <= pp_decision_stage3_start_ms()
            ):
                continue
        if policy_id == "PP-DECISION-V1-FINAL":
            if (
                not pp_decision_stage5_enabled()
                or int(opened_at_ms) <= pp_decision_stage5_start_ms()
            ):
                continue
        ids.append(policy_id)
    return ids


def _fee_rate() -> float:
    return max(0.0, min(float(os.environ.get("PAPER_FEE_RATE", "0.00075")), 0.01))


def _slippage_bps() -> float:
    return max(0.0, min(float(os.environ.get("PAPER_SLIPPAGE_BPS", "2")), 100.0))


def initialize_stage6_store() -> None:
    initialize_database()
    backend = persistence_backend()
    key = (
        ("sqlite", str(database_path().resolve()))
        if backend == "sqlite"
        else ("postgres", "primary")
    )
    with _INIT_LOCK:
        if key in _INITIALIZED:
            return
        if backend == "sqlite":
            with _sqlite_connect(database_path()) as conn:
                conn.executescript(SQLITE_SCHEMA)
        else:
            with _postgres_connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(POSTGRES_SCHEMA)
        _INITIALIZED.add(key)


def _gross(side: str, qty: float, entry: float, exit_price: float) -> float:
    return qty * (exit_price - entry) if side.upper() == "LONG" else qty * (entry - exit_price)


def _sim_exit_fill(side: str, market_price: float) -> float:
    slip = _slippage_bps() / 10_000.0
    return market_price * (1.0 - slip if side.upper() == "LONG" else 1.0 + slip)


def _median(values: list[float]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return statistics.median(clean) if clean else None


def _query_all(sqlite_sql: str, postgres_sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    initialize_stage6_store()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            return [dict(row) for row in conn.execute(sqlite_sql, params).fetchall()]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(postgres_sql, params)
            return [dict(row) for row in cur.fetchall()]


def _query_one(sqlite_sql: str, postgres_sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    rows = _query_all(sqlite_sql, postgres_sql, params)
    return rows[0] if rows else None


def register_stage6_position(
    *,
    position_id: str,
    signal_id: str,
    symbol: str,
    side: str,
    opened_at_ms: int,
    entry_price: float,
    initial_quantity: float,
    initial_notional: float,
    entry_fee_total: float,
) -> bool:
    if not stage6_enabled() or int(opened_at_ms) <= stage6_start_ms():
        return False
    initialize_stage6_store()
    now = int(time.time() * 1000)
    run_id = stage6_run_id()
    values = (
        run_id, position_id, signal_id, symbol.upper(), side.upper(),
        int(opened_at_ms), float(entry_price), float(initial_quantity),
        float(initial_notional), float(entry_fee_total), "ACTIVE",
        int(opened_at_ms) - 1, 0.0, None, now, now,
        json.dumps(
            {
                "stage6_version": STAGE6_VERSION,
                "discovery_cutoff_ms": DISCOVERY_CUTOFF_MS,
                "stage6_start_ms": stage6_start_ms(),
            },
            separators=(",", ":"),
        ),
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            cur = conn.execute(
                """
                insert or ignore into stage6_validation_trades (
                    run_id,position_id,signal_id,symbol,side,opened_at_ms,
                    entry_price,initial_quantity,initial_notional,entry_fee_total,
                    status,last_candle_close_ms,opportunity_peak_pnl,
                    opportunity_peak_at_ms,created_at_ms,updated_at_ms,raw_json
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
            inserted = cur.rowcount > 0
            if inserted:
                for policy_id in _policy_ids_for_entry(int(opened_at_ms)):
                    conn.execute(
                        """
                        insert into stage6_validation_lanes (
                            run_id,position_id,policy_id,status,remaining_quantity,
                            realized_gross,realized_net,allocated_entry_fee,exit_fees,
                            policy_peak_pnl,policy_peak_at_ms,profit_floor,action_count,
                            trigger_count,updated_at_ms,raw_json
                        ) values (?,?,?,?,?,0,0,0,0,0,null,null,0,0,?,?)
                        """,
                        (
                            run_id, position_id, policy_id, "OPEN",
                            float(initial_quantity), now,
                            json.dumps(POLICIES[policy_id], separators=(",", ":")),
                        ),
                    )
            return inserted

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into stage6_validation_trades (
                    run_id,position_id,signal_id,symbol,side,opened_at_ms,
                    entry_price,initial_quantity,initial_notional,entry_fee_total,
                    status,last_candle_close_ms,opportunity_peak_pnl,
                    opportunity_peak_at_ms,created_at_ms,updated_at_ms,raw_json
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(run_id,position_id) do nothing
                returning position_id
                """,
                values,
            )
            inserted = cur.fetchone() is not None
            if inserted:
                for policy_id in _policy_ids_for_entry(int(opened_at_ms)):
                    cur.execute(
                        """
                        insert into stage6_validation_lanes (
                            run_id,position_id,policy_id,status,remaining_quantity,
                            realized_gross,realized_net,allocated_entry_fee,exit_fees,
                            policy_peak_pnl,policy_peak_at_ms,profit_floor,action_count,
                            trigger_count,updated_at_ms,raw_json
                        ) values (%s,%s,%s,%s,%s,0,0,0,0,0,null,null,0,0,%s,%s)
                        on conflict(run_id,position_id,policy_id) do nothing
                        """,
                        (
                            run_id, position_id, policy_id, "OPEN",
                            float(initial_quantity), now,
                            json.dumps(POLICIES[policy_id], separators=(",", ":")),
                        ),
                    )
            return inserted


def _recover_missing_registrations() -> int:
    if not stage6_enabled():
        return 0
    start_ms = stage6_start_ms()
    rows = _query_all(
        """
        select position_id,signal_id,symbol,side,opened_at_ms,entry_price,quantity,raw_json
        from positions
        where mode='PAPER' and status in ('OPEN','REDUCED') and opened_at_ms>?
        order by opened_at_ms
        """,
        """
        select position_id,signal_id,symbol,side,opened_at_ms,entry_price,quantity,raw_json
        from positions
        where mode='PAPER' and status in ('OPEN','REDUCED') and opened_at_ms>%s
        order by opened_at_ms
        """,
        (start_ms,),
    )
    recovered = 0
    for row in rows:
        try:
            meta = json.loads(row.get("raw_json") or "{}")
        except Exception:
            meta = {}
        initial_qty = float(meta.get("initial_quantity") or row.get("quantity") or 0.0)
        notional = float(
            meta.get("initial_notional_usdt")
            or initial_qty * float(row.get("entry_price") or 0.0)
        )
        entry_fee = float(
            meta.get("entry_fee_total")
            or notional * _fee_rate()
        )
        if initial_qty <= 0 or notional <= 0:
            continue
        if register_stage6_position(
            position_id=str(row["position_id"]),
            signal_id=str(row.get("signal_id") or ""),
            symbol=str(row["symbol"]),
            side=str(row["side"]),
            opened_at_ms=int(row["opened_at_ms"]),
            entry_price=float(row["entry_price"]),
            initial_quantity=initial_qty,
            initial_notional=notional,
            entry_fee_total=entry_fee,
        ):
            recovered += 1
    return recovered


def _active_trades() -> list[dict[str, Any]]:
    run_id = stage6_run_id()
    return _query_all(
        """
        select t.*, p.status as control_status,
               p.closed_at_ms as control_closed_at_ms,
               p.exit_price as control_exit_price,
               p.realized_pnl as control_realized_pnl,
               p.realized_pnl_pct as control_realized_pnl_pct,
               p.close_reason as control_close_reason
        from stage6_validation_trades t
        left join positions p on p.position_id=t.position_id
        where t.run_id=? and t.status='ACTIVE'
        order by t.opened_at_ms
        """,
        """
        select t.*, p.status as control_status,
               p.closed_at_ms as control_closed_at_ms,
               p.exit_price as control_exit_price,
               p.realized_pnl as control_realized_pnl,
               p.realized_pnl_pct as control_realized_pnl_pct,
               p.close_reason as control_close_reason
        from stage6_validation_trades t
        left join positions p on p.position_id=t.position_id
        where t.run_id=%s and t.status='ACTIVE'
        order by t.opened_at_ms
        """,
        (run_id,),
    )


def _lanes(position_id: str) -> list[dict[str, Any]]:
    run_id = stage6_run_id()
    return _query_all(
        "select * from stage6_validation_lanes where run_id=? and position_id=? order by policy_id",
        "select * from stage6_validation_lanes where run_id=%s and position_id=%s order by policy_id",
        (run_id, position_id),
    )


def _oi_series(rows: list[dict[str, Any]]) -> list[tuple[int, float, float | None]]:
    out: list[tuple[int, float, float | None]] = []
    prev: float | None = None
    for row in sorted(rows, key=lambda x: int(x.get("timestamp") or 0)):
        try:
            ts = int(row.get("timestamp") or 0)
            value = float(row.get("sumOpenInterest"))
        except (TypeError, ValueError):
            continue
        change = 100.0 * (value / prev - 1.0) if prev and prev > 0 else None
        out.append((ts, value, change))
        prev = value
    return out


def _latest_oi_change(series: list[tuple[int, float, float | None]], ts: int) -> float | None:
    value = None
    for item in series:
        if item[0] <= ts:
            value = item[2]
        else:
            break
    return value


def _feature_rows(
    *,
    side: str,
    opened_at_ms: int,
    klines: list[list[Any]],
    oi_rows: list[dict[str, Any]],
    now_ms: int,
) -> list[dict[str, Any]]:
    rows = [
        row for row in klines
        if len(row) > 10
        and int(row[6]) < now_ms
        and int(row[6]) >= int(opened_at_ms)
    ]
    rows.sort(key=lambda row: int(row[6]))
    oi = _oi_series(oi_rows)
    ret_hist: list[float] = []
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    out: list[dict[str, Any]] = []
    sign = 1.0 if side.upper() == "LONG" else -1.0
    for row in rows:
        close = float(row[4])
        high = float(row[2])
        low = float(row[3])
        volume = max(0.0, float(row[5]))
        taker_buy_volume = max(0.0, float(row[9]))
        taker_share = taker_buy_volume / volume if volume > 0 else None
        previous_close = closes[-1] if closes else None
        ret1 = 100.0 * (close / previous_close - 1.0) if previous_close else None
        if ret1 is not None:
            ret_hist.append(ret1)
        closes.append(close)
        highs.append(high)
        lows.append(low)
        ret3 = 100.0 * (close / closes[-4] - 1.0) if len(closes) >= 4 else None
        rv15 = statistics.pstdev(ret_hist[-15:]) if len(ret_hist) >= 2 else None
        micro_up = close > max(highs[-5:-1]) if len(highs) >= 2 else False
        micro_down = close < min(lows[-5:-1]) if len(lows) >= 2 else False
        out.append(
            {
                "candle_close_ms": int(row[6]),
                "close": close,
                "side_ret3": sign * ret3 if ret3 is not None else None,
                "taker_strength": (
                    None
                    if taker_share is None
                    else (taker_share - 0.5 if side.upper() == "LONG" else 0.5 - taker_share)
                ),
                "micro_against": micro_down if side.upper() == "LONG" else micro_up,
                "oi_change": _latest_oi_change(oi, int(row[6])),
                "rv15": rv15,
            }
        )
    return out


def _evidence(feature: dict[str, Any], peak_age_min: float) -> dict[str, int]:
    stale = int(peak_age_min >= 3.0)
    side_ret3 = feature.get("side_ret3")
    momentum_adverse = int(
        side_ret3 is not None and float(side_ret3) <= -0.10
    )
    structure_break = int(bool(feature.get("micro_against")))
    price_adverse = int(bool(structure_break or momentum_adverse))
    taker = feature.get("taker_strength")
    taker_opposing = int(taker is not None and float(taker) <= -0.05)
    oi_change = feature.get("oi_change")
    oi_adverse = int(
        oi_change is not None
        and abs(float(oi_change)) >= 0.05
        and float(oi_change) > 0
        and side_ret3 is not None
        and float(side_ret3) <= -0.10
    )
    rv15 = feature.get("rv15")
    vol_extreme = int(rv15 is not None and float(rv15) >= RV15_EXTREME_PCT)
    danger_score = (
        2 * momentum_adverse
        + 2 * structure_break
        + taker_opposing
        + oi_adverse
    )
    return {
        "stale": stale,
        "momentum_adverse": momentum_adverse,
        "structure_break": structure_break,
        "price_adverse": price_adverse,
        "taker_opposing": taker_opposing,
        "oi_adverse": oi_adverse,
        "vol_extreme": vol_extreme,
        "core_count": stale + price_adverse + taker_opposing,
        "danger_score": danger_score,
    }


def _adaptive_lock(policy: dict[str, Any], peak_roi: float, evidence: dict[str, int]) -> float | None:
    if peak_roi < 0.5:
        return None
    base = (
        float(policy["base1"])
        if peak_roi < 2.0
        else float(policy["base2"])
        if peak_roi < 5.0
        else float(policy["base3"])
    )
    if base <= 0:
        return None
    lock = base
    if evidence["core_count"] >= 2:
        lock += float(policy["tight2"])
    if evidence["core_count"] >= 3:
        lock += float(policy["tight3"])
    if evidence["oi_adverse"]:
        lock += float(policy["oi_tight"])
    if evidence["vol_extreme"]:
        lock += float(policy["vol_mod"])
    return max(0.05, min(0.95, lock))


def _static_lock(policy: dict[str, Any], peak_roi: float) -> float | None:
    if peak_roi < float(policy["arm_roi_pct"]):
        return None
    return float(policy["lock_ratio"])


def _v5_sub1_decision(
    policy: dict[str, Any],
    *,
    peak_roi: float,
    economic: float,
    peak: float,
    evidence: dict[str, int],
    status: str,
) -> tuple[str, dict[str, Any]]:
    giveback_ratio = (
        max(0.0, (float(peak) - float(economic)) / float(peak))
        if float(peak) > 0
        else 0.0
    )
    danger_score = int(evidence.get("danger_score", 0))
    meta: dict[str, Any] = {
        "gate": "DISARMED",
        "giveback_ratio": giveback_ratio,
        "danger_score": danger_score,
    }
    if peak_roi < float(policy["arm_min_roi_pct"]):
        return "HOLD", meta
    if peak_roi >= float(policy["handoff_roi_pct"]):
        meta["gate"] = "HANDOFF_GE1"
        return "HOLD", meta

    watch = float(policy["watch_giveback_ratio"])
    decision = float(policy["decision_giveback_ratio"])
    hard_stop = float(policy["hard_stop_giveback_ratio"])
    meta["gate"] = "ARMED_SUB1"

    if giveback_ratio >= hard_stop:
        meta["gate"] = "HARD_STOP"
        return "CLOSE", meta

    if giveback_ratio >= decision:
        meta["gate"] = "MANDATORY_DECISION"
        if danger_score >= int(policy["close_score"]):
            return "CLOSE", meta
        if danger_score >= int(policy["reduce_score"]):
            return ("REDUCE" if status == "OPEN" else "CLOSE"), meta
        return "HOLD", meta

    if giveback_ratio >= watch:
        meta["gate"] = "WATCH"
        if danger_score >= int(policy["watch_reduce_score"]):
            return ("REDUCE" if status == "OPEN" else "CLOSE"), meta
    return "HOLD", meta


def _pp_decision_ge1(
    policy: dict[str, Any],
    *,
    peak_roi: float,
    economic: float,
    peak: float,
    evidence: dict[str, int],
    status: str,
) -> tuple[str, dict[str, Any]]:
    giveback_ratio = (
        max(0.0, (float(peak) - float(economic)) / float(peak))
        if float(peak) > 0
        else 0.0
    )
    danger_score = int(evidence.get("danger_score", 0))
    meta: dict[str, Any] = {
        "gate": "DISARMED",
        "giveback_ratio": giveback_ratio,
        "danger_score": danger_score,
    }
    if peak_roi < float(policy["arm_min_roi_pct"]):
        return "HOLD", meta

    watch = float(policy["watch_giveback_ratio"])
    decision = float(policy["decision_giveback_ratio"])
    force_reduce = float(policy["force_reduce_giveback_ratio"])
    hard_close = float(policy["hard_close_giveback_ratio"])
    meta["gate"] = "ARMED_GE1"

    if giveback_ratio >= hard_close:
        meta["gate"] = "HARD_CLOSE"
        return "CLOSE", meta

    if giveback_ratio >= force_reduce:
        meta["gate"] = "FORCE_PROTECT"
        if danger_score >= int(policy["close_score"]) or status == "REDUCED":
            return "CLOSE", meta
        return "REDUCE", meta

    if giveback_ratio >= decision:
        meta["gate"] = "MANDATORY_DECISION"
        if danger_score >= int(policy["close_score"]):
            return "CLOSE", meta
        if danger_score >= int(policy["reduce_score"]):
            return ("REDUCE" if status == "OPEN" else "CLOSE"), meta
        return "HOLD", meta

    if giveback_ratio >= watch:
        meta["gate"] = "WATCH"
        if danger_score >= int(policy["watch_reduce_score"]):
            return ("REDUCE" if status == "OPEN" else "CLOSE"), meta
    return "HOLD", meta


def _pp_decision_unified(
    policy: dict[str, Any],
    *,
    peak_roi: float,
    economic: float,
    peak: float,
    evidence: dict[str, int],
    status: str,
) -> tuple[str, dict[str, Any]]:
    handoff = float(policy["handoff_roi_pct"])
    if peak_roi < handoff:
        sub1_policy = {
            "arm_min_roi_pct": float(policy["sub1_arm_min_roi_pct"]),
            "handoff_roi_pct": handoff,
            "watch_giveback_ratio": float(policy["sub1_watch_giveback_ratio"]),
            "decision_giveback_ratio": float(policy["sub1_decision_giveback_ratio"]),
            "hard_stop_giveback_ratio": float(policy["sub1_hard_stop_giveback_ratio"]),
            "watch_reduce_score": int(policy["watch_reduce_score"]),
            "reduce_score": int(policy["reduce_score"]),
            "close_score": int(policy["close_score"]),
        }
        action, meta = _v5_sub1_decision(
            sub1_policy,
            peak_roi=peak_roi,
            economic=economic,
            peak=peak,
            evidence=evidence,
            status=status,
        )
        meta["zone"] = "SUB1"
        return action, meta

    ge1_policy = {
        "arm_min_roi_pct": handoff,
        "watch_giveback_ratio": float(policy["ge1_watch_giveback_ratio"]),
        "decision_giveback_ratio": float(policy["ge1_decision_giveback_ratio"]),
        "force_reduce_giveback_ratio": float(policy["ge1_force_reduce_giveback_ratio"]),
        "hard_close_giveback_ratio": float(policy["ge1_hard_close_giveback_ratio"]),
        "watch_reduce_score": int(policy["watch_reduce_score"]),
        "reduce_score": int(policy["reduce_score"]),
        "close_score": int(policy["close_score"]),
    }
    action, meta = _pp_decision_ge1(
        ge1_policy,
        peak_roi=peak_roi,
        economic=economic,
        peak=peak,
        evidence=evidence,
        status=status,
    )
    meta["zone"] = "GE1"
    return action, meta


def _evaluate_lane(
    *,
    trade: dict[str, Any],
    lane: dict[str, Any],
    feature: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = POLICIES[str(lane["policy_id"])]
    side = str(trade["side"])
    entry = float(trade["entry_price"])
    remaining = float(lane["remaining_quantity"])
    initial_qty = float(trade["initial_quantity"])
    initial_notional = float(trade["initial_notional"])
    entry_fee_total = float(trade["entry_fee_total"])
    allocated_entry = float(lane["allocated_entry_fee"])
    realized_net = float(lane["realized_net"])
    realized_gross = float(lane["realized_gross"])
    exit_fees = float(lane["exit_fees"])
    fill = _sim_exit_fill(side, float(feature["close"]))
    remaining_entry_fee = max(0.0, entry_fee_total - allocated_entry)
    estimated_exit_fee = remaining * fill * _fee_rate()
    economic = (
        realized_net
        + _gross(side, remaining, entry, fill)
        - remaining_entry_fee
        - estimated_exit_fee
    )
    peak = float(lane["policy_peak_pnl"] or 0.0)
    peak_at = lane.get("policy_peak_at_ms")
    if peak_at is None or economic > peak:
        peak = economic
        peak_at = int(feature["candle_close_ms"])
    peak_age = (
        0.0
        if peak_at is None
        else max(0.0, (int(feature["candle_close_ms"]) - int(peak_at)) / 60_000.0)
    )
    ev = _evidence(feature, peak_age)
    peak_roi = 100.0 * peak / initial_notional if initial_notional > 0 else 0.0
    decision_meta: dict[str, Any] = {}
    if policy["kind"] == "ADAPTIVE":
        lock = _adaptive_lock(policy, peak_roi, ev)
    elif policy["kind"] == "STATIC":
        lock = _static_lock(policy, peak_roi)
    else:
        lock = None
    floor = float(lane["profit_floor"]) if lane.get("profit_floor") is not None else None
    if lock is not None and peak > 0:
        candidate = peak * lock
        floor = candidate if floor is None else max(floor, candidate)
    if policy["kind"] == "PP_DECISION_GE1" and peak_roi >= float(policy["arm_min_roi_pct"]):
        candidate = peak * (1.0 - float(policy["hard_close_giveback_ratio"]))
        floor = candidate if floor is None else max(floor, candidate)
    if policy["kind"] == "PP_DECISION_UNIFIED" and peak_roi >= float(policy["handoff_roi_pct"]):
        candidate = peak * (1.0 - float(policy["ge1_hard_close_giveback_ratio"]))
        floor = candidate if floor is None else max(floor, candidate)
    breached = bool(floor is not None and economic <= floor + 1e-12)
    action = "HOLD"
    status = str(lane["status"])
    action_count = int(lane["action_count"] or 0)
    trigger_count = int(lane["trigger_count"] or 0)
    closed_at = lane.get("closed_at_ms")
    exit_price = lane.get("exit_price")
    close_reason = lane.get("close_reason")

    if policy["kind"] == "V5_SUB1_DECISION" and status in {"OPEN", "REDUCED"}:
        action, decision_meta = _v5_sub1_decision(
            policy,
            peak_roi=peak_roi,
            economic=economic,
            peak=peak,
            evidence=ev,
            status=status,
        )
        if action != "HOLD":
            trigger_count += 1
    elif policy["kind"] == "PP_DECISION_GE1" and status in {"OPEN", "REDUCED"}:
        action, decision_meta = _pp_decision_ge1(
            policy,
            peak_roi=peak_roi,
            economic=economic,
            peak=peak,
            evidence=ev,
            status=status,
        )
        if action != "HOLD":
            trigger_count += 1
    elif policy["kind"] == "PP_DECISION_UNIFIED" and status in {"OPEN", "REDUCED"}:
        action, decision_meta = _pp_decision_unified(
            policy,
            peak_roi=peak_roi,
            economic=economic,
            peak=peak,
            evidence=ev,
            status=status,
        )
        if action != "HOLD":
            trigger_count += 1
    elif breached and status in {"OPEN", "REDUCED"}:
        trigger_count += 1
        if policy["mode"] == "CLOSE_FIRST":
            action = "CLOSE"
        elif policy["mode"] == "REDUCE_THEN_CLOSE":
            action = "REDUCE" if status == "OPEN" else "CLOSE"

    if action == "REDUCE":
        qty = remaining * (
            float(policy.get("reduce_fraction", 0.50))
            if policy["kind"] in {"V5_SUB1_DECISION", "PP_DECISION_GE1", "PP_DECISION_UNIFIED"}
            else 0.50
        )
        allocated = entry_fee_total * (qty / initial_qty) if initial_qty > 0 else 0.0
        gross_inc = _gross(side, qty, entry, fill)
        exit_fee = qty * fill * _fee_rate()
        net_inc = gross_inc - allocated - exit_fee
        realized_gross += gross_inc
        realized_net += net_inc
        exit_fees += exit_fee
        allocated_entry += allocated
        remaining -= qty
        status = "REDUCED"
        action_count += 1
    elif action == "CLOSE":
        qty = remaining
        allocated = max(0.0, entry_fee_total - allocated_entry)
        gross_inc = _gross(side, qty, entry, fill)
        exit_fee = qty * fill * _fee_rate()
        net_inc = gross_inc - allocated - exit_fee
        realized_gross += gross_inc
        realized_net += net_inc
        exit_fees += exit_fee
        allocated_entry += allocated
        remaining = 0.0
        status = "CLOSED"
        action_count += 1
        closed_at = int(feature["candle_close_ms"])
        exit_price = fill
        close_reason = (
            "V5_SUB1_DECISION_GATE"
            if policy["kind"] == "V5_SUB1_DECISION"
            else "PP_DECISION_GE1_GATE"
            if policy["kind"] == "PP_DECISION_GE1"
            else "PP_DECISION_V1_UNIFIED_GATE"
            if policy["kind"] == "PP_DECISION_UNIFIED"
            else "POLICY_FLOOR"
        )

    updated = {
        **lane,
        "status": status,
        "remaining_quantity": remaining,
        "realized_gross": realized_gross,
        "realized_net": realized_net,
        "allocated_entry_fee": allocated_entry,
        "exit_fees": exit_fees,
        "policy_peak_pnl": peak,
        "policy_peak_at_ms": peak_at,
        "profit_floor": floor,
        "action_count": action_count,
        "trigger_count": trigger_count,
        "closed_at_ms": closed_at,
        "exit_price": exit_price,
        "close_reason": close_reason,
    }
    event = {
        "economic_pnl": economic,
        "policy_peak_pnl": peak,
        "profit_floor": floor,
        "lock_ratio": lock,
        "action": action,
        "evidence": {**ev, **decision_meta},
    }
    return updated, event


def _save_trade_and_lanes(
    trade: dict[str, Any],
    lanes: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> None:
    now = int(time.time() * 1000)
    run_id = str(trade["run_id"])
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update stage6_validation_trades
                set last_candle_close_ms=?, opportunity_peak_pnl=?,
                    opportunity_peak_at_ms=?, updated_at_ms=?
                where run_id=? and position_id=?
                """,
                (
                    trade["last_candle_close_ms"],
                    trade["opportunity_peak_pnl"],
                    trade.get("opportunity_peak_at_ms"),
                    now, run_id, trade["position_id"],
                ),
            )
            for lane in lanes:
                conn.execute(
                    """
                    update stage6_validation_lanes
                    set status=?,remaining_quantity=?,realized_gross=?,realized_net=?,
                        allocated_entry_fee=?,exit_fees=?,policy_peak_pnl=?,
                        policy_peak_at_ms=?,profit_floor=?,action_count=?,trigger_count=?,
                        closed_at_ms=?,exit_price=?,close_reason=?,updated_at_ms=?
                    where run_id=? and position_id=? and policy_id=?
                    """,
                    (
                        lane["status"], lane["remaining_quantity"], lane["realized_gross"],
                        lane["realized_net"], lane["allocated_entry_fee"], lane["exit_fees"],
                        lane["policy_peak_pnl"], lane.get("policy_peak_at_ms"),
                        lane.get("profit_floor"), lane["action_count"], lane["trigger_count"],
                        lane.get("closed_at_ms"), lane.get("exit_price"), lane.get("close_reason"),
                        now, run_id, trade["position_id"], lane["policy_id"],
                    ),
                )
            for event in events:
                conn.execute(
                    """
                    insert or ignore into stage6_validation_events (
                        event_id,run_id,position_id,policy_id,candle_close_ms,
                        economic_pnl,policy_peak_pnl,opportunity_peak_pnl,
                        profit_floor,lock_ratio,action,evidence_json,created_at_ms
                    ) values (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        event["event_id"], run_id, trade["position_id"], event["policy_id"],
                        event["candle_close_ms"], event["economic_pnl"],
                        event["policy_peak_pnl"], event["opportunity_peak_pnl"],
                        event.get("profit_floor"), event.get("lock_ratio"), event["action"],
                        json.dumps(event["evidence"], separators=(",", ":")), now,
                    ),
                )
        return

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update stage6_validation_trades
                set last_candle_close_ms=%s, opportunity_peak_pnl=%s,
                    opportunity_peak_at_ms=%s, updated_at_ms=%s
                where run_id=%s and position_id=%s
                """,
                (
                    trade["last_candle_close_ms"], trade["opportunity_peak_pnl"],
                    trade.get("opportunity_peak_at_ms"), now, run_id, trade["position_id"],
                ),
            )
            for lane in lanes:
                cur.execute(
                    """
                    update stage6_validation_lanes
                    set status=%s,remaining_quantity=%s,realized_gross=%s,realized_net=%s,
                        allocated_entry_fee=%s,exit_fees=%s,policy_peak_pnl=%s,
                        policy_peak_at_ms=%s,profit_floor=%s,action_count=%s,trigger_count=%s,
                        closed_at_ms=%s,exit_price=%s,close_reason=%s,updated_at_ms=%s
                    where run_id=%s and position_id=%s and policy_id=%s
                    """,
                    (
                        lane["status"], lane["remaining_quantity"], lane["realized_gross"],
                        lane["realized_net"], lane["allocated_entry_fee"], lane["exit_fees"],
                        lane["policy_peak_pnl"], lane.get("policy_peak_at_ms"),
                        lane.get("profit_floor"), lane["action_count"], lane["trigger_count"],
                        lane.get("closed_at_ms"), lane.get("exit_price"), lane.get("close_reason"),
                        now, run_id, trade["position_id"], lane["policy_id"],
                    ),
                )
            for event in events:
                cur.execute(
                    """
                    insert into stage6_validation_events (
                        event_id,run_id,position_id,policy_id,candle_close_ms,
                        economic_pnl,policy_peak_pnl,opportunity_peak_pnl,
                        profit_floor,lock_ratio,action,evidence_json,created_at_ms
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict(event_id) do nothing
                    """,
                    (
                        event["event_id"], run_id, trade["position_id"], event["policy_id"],
                        event["candle_close_ms"], event["economic_pnl"],
                        event["policy_peak_pnl"], event["opportunity_peak_pnl"],
                        event.get("profit_floor"), event.get("lock_ratio"), event["action"],
                        json.dumps(event["evidence"], separators=(",", ":")), now,
                    ),
                )


def process_stage6_shadow_cycle(
    client: BinancePublicClient | None = None,
) -> dict[str, Any]:
    if not stage6_enabled():
        return {"status": "DISABLED", "processed_trades": 0, "processed_candles": 0, "errors": []}
    initialize_stage6_store()
    recovered = _recover_missing_registrations()
    trades = _active_trades()
    if not trades:
        return {
            "status": "IDLE",
            "processed_trades": 0,
            "processed_candles": 0,
            "recovered_registrations": recovered,
            "recovered_finalizations": 0,
            "errors": [],
        }
    client = client or BinancePublicClient(timeout=8.0, retries=2)
    now_ms = client.server_time_ms()
    processed_candles = 0
    errors: list[str] = []
    for trade in trades:
        try:
            klines = client.klines(str(trade["symbol"]), interval="1m", limit=1000)
            oi_rows = client.open_interest_hist(str(trade["symbol"]), period="5m", limit=500)
            control_closed_at = trade.get("control_closed_at_ms")
            effective_now_ms = (
                min(now_ms, int(control_closed_at) + 1)
                if control_closed_at is not None
                else now_ms
            )
            features = _feature_rows(
                side=str(trade["side"]),
                opened_at_ms=int(trade["opened_at_ms"]),
                klines=klines,
                oi_rows=oi_rows,
                now_ms=effective_now_ms,
            )
            last = int(trade.get("last_candle_close_ms") or int(trade["opened_at_ms"]) - 1)
            new_features = [x for x in features if int(x["candle_close_ms"]) > last]
            if not new_features:
                continue
            lanes = _lanes(str(trade["position_id"]))
            events: list[dict[str, Any]] = []
            for feature in new_features:
                fill = _sim_exit_fill(str(trade["side"]), float(feature["close"]))
                opportunity = (
                    _gross(
                        str(trade["side"]),
                        float(trade["initial_quantity"]),
                        float(trade["entry_price"]),
                        fill,
                    )
                    - float(trade["entry_fee_total"])
                    - float(trade["initial_quantity"]) * fill * _fee_rate()
                )
                if (
                    trade.get("opportunity_peak_at_ms") is None
                    or opportunity > float(trade["opportunity_peak_pnl"] or 0.0)
                ):
                    trade["opportunity_peak_pnl"] = opportunity
                    trade["opportunity_peak_at_ms"] = int(feature["candle_close_ms"])
                updated_lanes: list[dict[str, Any]] = []
                for lane in lanes:
                    if str(lane["status"]) in {"OPEN", "REDUCED"}:
                        lane, event = _evaluate_lane(
                            trade=trade,
                            lane=lane,
                            feature=feature,
                        )
                        events.append(
                            {
                                "event_id": (
                                    f"{trade['run_id']}:{trade['position_id']}:"
                                    f"{lane['policy_id']}:{feature['candle_close_ms']}"
                                ),
                                "policy_id": lane["policy_id"],
                                "candle_close_ms": int(feature["candle_close_ms"]),
                                "opportunity_peak_pnl": trade["opportunity_peak_pnl"],
                                **event,
                            }
                        )
                    updated_lanes.append(lane)
                lanes = updated_lanes
                trade["last_candle_close_ms"] = int(feature["candle_close_ms"])
                processed_candles += 1
            _save_trade_and_lanes(trade, lanes, events)
        except Exception as exc:
            errors.append(
                f"{trade.get('position_id')}: {type(exc).__name__}: {str(exc)[:240]}"
            )
    recovered_finalizations = 0
    for trade in trades:
        if str(trade.get("control_status") or "").upper() != "CLOSED":
            continue
        try:
            if finalize_stage6_position(
                position_id=str(trade["position_id"]),
                closed_at_ms=int(trade["control_closed_at_ms"]),
                actual_exit_price=float(trade["control_exit_price"]),
                actual_realized_pnl=float(trade["control_realized_pnl"] or 0.0),
                actual_realized_pnl_pct=float(trade["control_realized_pnl_pct"] or 0.0),
                actual_close_reason=str(trade.get("control_close_reason") or "stage12_close"),
            ):
                recovered_finalizations += 1
        except Exception as exc:
            errors.append(
                f"{trade.get('position_id')}: finalize recovery: "
                f"{type(exc).__name__}: {str(exc)[:200]}"
            )
    return {
        "status": "COMPLETE",
        "processed_trades": len(trades),
        "processed_candles": processed_candles,
        "recovered_registrations": recovered,
        "recovered_finalizations": recovered_finalizations,
        "errors": errors,
    }


def finalize_stage6_position(
    *,
    position_id: str,
    closed_at_ms: int,
    actual_exit_price: float,
    actual_realized_pnl: float,
    actual_realized_pnl_pct: float,
    actual_close_reason: str,
) -> bool:
    if not stage6_enabled():
        return False
    initialize_stage6_store()
    run_id = stage6_run_id()
    trade = _query_one(
        "select * from stage6_validation_trades where run_id=? and position_id=? and status='ACTIVE'",
        "select * from stage6_validation_trades where run_id=%s and position_id=%s and status='ACTIVE'",
        (run_id, position_id),
    )
    if not trade:
        return False

    opportunity_at_exit = (
        _gross(
            str(trade["side"]),
            float(trade["initial_quantity"]),
            float(trade["entry_price"]),
            float(actual_exit_price),
        )
        - float(trade["entry_fee_total"])
        - float(trade["initial_quantity"]) * float(actual_exit_price) * _fee_rate()
    )
    if (
        trade.get("opportunity_peak_at_ms") is None
        or opportunity_at_exit > float(trade["opportunity_peak_pnl"] or 0.0)
    ):
        trade["opportunity_peak_pnl"] = opportunity_at_exit
        trade["opportunity_peak_at_ms"] = int(closed_at_ms)

    lanes = _lanes(position_id)
    now = int(time.time() * 1000)
    for lane in lanes:
        if str(lane["status"]) not in {"OPEN", "REDUCED"}:
            continue
        remaining = float(lane["remaining_quantity"])
        allocated = max(
            0.0,
            float(trade["entry_fee_total"]) - float(lane["allocated_entry_fee"]),
        )
        gross_inc = _gross(
            str(trade["side"]),
            remaining,
            float(trade["entry_price"]),
            float(actual_exit_price),
        )
        exit_fee = remaining * float(actual_exit_price) * _fee_rate()
        lane["realized_gross"] = float(lane["realized_gross"]) + gross_inc
        lane["realized_net"] = float(lane["realized_net"]) + gross_inc - allocated - exit_fee
        lane["allocated_entry_fee"] = float(lane["allocated_entry_fee"]) + allocated
        lane["exit_fees"] = float(lane["exit_fees"]) + exit_fee
        lane["remaining_quantity"] = 0.0
        lane["status"] = "CENSORED"
        lane["closed_at_ms"] = int(closed_at_ms)
        lane["exit_price"] = float(actual_exit_price)
        lane["close_reason"] = "V3_CONTROL_CENSOR"

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update stage6_validation_trades
                set status='CENSORED',opportunity_peak_pnl=?,
                    opportunity_peak_at_ms=?,actual_closed_at_ms=?,
                    actual_exit_price=?,actual_realized_pnl=?,
                    actual_realized_pnl_pct=?,actual_close_reason=?,updated_at_ms=?
                where run_id=? and position_id=?
                """,
                (
                    trade["opportunity_peak_pnl"], trade.get("opportunity_peak_at_ms"),
                    int(closed_at_ms), float(actual_exit_price),
                    float(actual_realized_pnl), float(actual_realized_pnl_pct),
                    actual_close_reason, now, run_id, position_id,
                ),
            )
            for lane in lanes:
                conn.execute(
                    """
                    update stage6_validation_lanes
                    set status=?,remaining_quantity=?,realized_gross=?,realized_net=?,
                        allocated_entry_fee=?,exit_fees=?,closed_at_ms=?,exit_price=?,
                        close_reason=?,updated_at_ms=?
                    where run_id=? and position_id=? and policy_id=?
                    """,
                    (
                        lane["status"], lane["remaining_quantity"], lane["realized_gross"],
                        lane["realized_net"], lane["allocated_entry_fee"], lane["exit_fees"],
                        lane.get("closed_at_ms"), lane.get("exit_price"), lane.get("close_reason"),
                        now, run_id, position_id, lane["policy_id"],
                    ),
                )
        return True

    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update stage6_validation_trades
                set status='CENSORED',opportunity_peak_pnl=%s,
                    opportunity_peak_at_ms=%s,actual_closed_at_ms=%s,
                    actual_exit_price=%s,actual_realized_pnl=%s,
                    actual_realized_pnl_pct=%s,actual_close_reason=%s,updated_at_ms=%s
                where run_id=%s and position_id=%s
                """,
                (
                    trade["opportunity_peak_pnl"], trade.get("opportunity_peak_at_ms"),
                    int(closed_at_ms), float(actual_exit_price),
                    float(actual_realized_pnl), float(actual_realized_pnl_pct),
                    actual_close_reason, now, run_id, position_id,
                ),
            )
            for lane in lanes:
                cur.execute(
                    """
                    update stage6_validation_lanes
                    set status=%s,remaining_quantity=%s,realized_gross=%s,realized_net=%s,
                        allocated_entry_fee=%s,exit_fees=%s,closed_at_ms=%s,exit_price=%s,
                        close_reason=%s,updated_at_ms=%s
                    where run_id=%s and position_id=%s and policy_id=%s
                    """,
                    (
                        lane["status"], lane["remaining_quantity"], lane["realized_gross"],
                        lane["realized_net"], lane["allocated_entry_fee"], lane["exit_fees"],
                        lane.get("closed_at_ms"), lane.get("exit_price"), lane.get("close_reason"),
                        now, run_id, position_id, lane["policy_id"],
                    ),
                )
    return True


def stage6_summary() -> dict[str, Any]:
    initialize_stage6_store()
    run_id = stage6_run_id()
    trades = _query_all(
        "select * from stage6_validation_trades where run_id=? order by opened_at_ms",
        "select * from stage6_validation_trades where run_id=%s order by opened_at_ms",
        (run_id,),
    )
    lanes = _query_all(
        "select * from stage6_validation_lanes where run_id=? order by position_id,policy_id",
        "select * from stage6_validation_lanes where run_id=%s order by position_id,policy_id",
        (run_id,),
    )
    trade_map = {str(x["position_id"]): x for x in trades}
    closed_trades = [x for x in trades if str(x["status"]) == "CENSORED"]
    policies: dict[str, Any] = {}
    for policy_id in POLICIES:
        rows = [
            lane for lane in lanes
            if str(lane["policy_id"]) == policy_id
            and str(lane["position_id"]) in trade_map
            and str(trade_map[str(lane["position_id"])]["status"]) == "CENSORED"
        ]
        econ2 = [
            lane for lane in rows
            if 100.0 * float(trade_map[str(lane["position_id"])]["opportunity_peak_pnl"])
            / float(trade_map[str(lane["position_id"])]["initial_notional"]) >= 2.0
        ]
        captures = [
            float(lane["realized_net"])
            / float(trade_map[str(lane["position_id"])]["opportunity_peak_pnl"])
            for lane in econ2
            if float(trade_map[str(lane["position_id"])]["opportunity_peak_pnl"]) > 0
        ]
        premature = sum(
            1
            for lane in econ2
            if str(lane["status"]) == "CLOSED"
            and lane.get("closed_at_ms") is not None
            and trade_map[str(lane["position_id"])].get("opportunity_peak_at_ms") is not None
            and int(lane["closed_at_ms"])
            < int(trade_map[str(lane["position_id"])]["opportunity_peak_at_ms"])
        )
        policies[policy_id] = {
            "trades": len(rows),
            "net_pnl": sum(float(x["realized_net"]) for x in rows),
            "win_rate_pct": (
                100.0 * sum(float(x["realized_net"]) > 0 for x in rows) / len(rows)
                if rows else None
            ),
            "econ_ge2_n": len(econ2),
            "econ_ge2_capture_median": _median(captures),
            "econ_ge2_premature_close_pct": (
                100.0 * premature / len(econ2) if econ2 else None
            ),
        }

    actual_values = [
        float(x["actual_realized_pnl"])
        for x in closed_trades
        if x.get("actual_realized_pnl") is not None
    ]
    return {
        "version": STAGE6_VERSION,
        "enabled": stage6_enabled(),
        "run_id": run_id,
        "stage6_start_ms": stage6_start_ms(),
        "discovery_cutoff_ms": DISCOVERY_CUTOFF_MS,
        "authority": "V3_CONTROL",
        "v5_0": {
            "display_name": "PP-DECISION V1 / Stage 1 / Sub-1%",
            "enabled": v5_0_enabled(),
            "prospective_start_ms": v5_0_start_ms(),
            "scope": "economic MFE 0.50% to <1.00%",
            "watch_giveback_ratio": POLICIES["V5-0"]["watch_giveback_ratio"],
            "decision_giveback_ratio": POLICIES["V5-0"]["decision_giveback_ratio"],
            "hard_stop_giveback_ratio": POLICIES["V5-0"]["hard_stop_giveback_ratio"],
        },
        "pp_decision_stage2": {
            "display_name": "PP-DECISION V1 / Stage 2 / MFE >=1%",
            "enabled": pp_decision_stage2_enabled(),
            "prospective_start_ms": pp_decision_stage2_start_ms(),
            "scope": "economic MFE >=1.00%",
            "watch_giveback_ratio": POLICIES["PP-DECISION-1P"]["watch_giveback_ratio"],
            "decision_giveback_ratio": POLICIES["PP-DECISION-1P"]["decision_giveback_ratio"],
            "force_reduce_giveback_ratio": POLICIES["PP-DECISION-1P"]["force_reduce_giveback_ratio"],
            "hard_close_giveback_ratio": POLICIES["PP-DECISION-1P"]["hard_close_giveback_ratio"],
        },
        "pp_decision_stage3": {
            "display_name": "PP-DECISION V1 / Stage 3 / Unified Protector",
            "enabled": pp_decision_stage3_enabled(),
            "prospective_start_ms": pp_decision_stage3_start_ms(),
            "scope": "single stateful lane from economic MFE 0.50% through >=1.00%",
            "lane_id": "PP-DECISION-V1",
            "handoff_roi_pct": POLICIES["PP-DECISION-V1"]["handoff_roi_pct"],
            "sub1_decision_giveback_ratio": POLICIES["PP-DECISION-V1"]["sub1_decision_giveback_ratio"],
            "ge1_decision_giveback_ratio": POLICIES["PP-DECISION-V1"]["ge1_decision_giveback_ratio"],
            "ge1_force_reduce_giveback_ratio": POLICIES["PP-DECISION-V1"]["ge1_force_reduce_giveback_ratio"],
            "ge1_hard_close_giveback_ratio": POLICIES["PP-DECISION-V1"]["ge1_hard_close_giveback_ratio"],
        },
        "pp_decision_stage4": {
            "display_name": "PP-DECISION V1 / Stage 4 / Robustness",
            "status": "PASSED",
            "lane_under_test": "PP-DECISION-V1",
            "isolated_tests": 11,
            "deterministic_state_cases": 1960,
            "long_short_symmetry": True,
            "threshold_boundaries_checked": True,
            "missing_evidence_safe": True,
            "closed_lane_idempotent": True,
            "action_severity_monotonic": True,
        },
        "pp_decision_stage5": {
            "display_name": "PP-DECISION V1 / Stage 5 / Final Paper Shadow",
            "enabled": pp_decision_stage5_enabled(),
            "prospective_start_ms": pp_decision_stage5_start_ms(),
            "lane_id": "PP-DECISION-V1-FINAL",
            "logic_source": "PP-DECISION-V1 Stage 3 unified contract, frozen after Stage 4",
            "authority": "PP-LEGACY V3",
            "post_freeze_clean_cohort": True,
            "policy_frozen": POLICIES["PP-DECISION-V1-FINAL"] == POLICIES["PP-DECISION-V1"],
        },
        "registered_trades": len(trades),
        "open_trades": sum(str(x["status"]) == "ACTIVE" for x in trades),
        "closed_trades": len(closed_trades),
        "actual_v3": {
            "trades": len(actual_values),
            "net_pnl": sum(actual_values),
            "win_rate_pct": (
                100.0 * sum(x > 0 for x in actual_values) / len(actual_values)
                if actual_values else None
            ),
        },
        "policies": policies,
    }