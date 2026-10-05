"""Frozen LONG Stage 3C.7A paper-entry policy.

The original research router coefficients were not persisted.  This runtime
uses a behavior-compatible linear router recovered from 704 outcome-blind
constraints implied by the frozen Stage 3C.7A policy.  It uses only causal
T0/temporal market inputs at inference; outcome/PnL/MFE fields are never used.

Activation is opt-in via PAPER_LONG_DETECTOR_POLICY=stage3c7a.  The default
paper entry path is unchanged.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable

import psycopg2.extras

from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    initialize_database,
    persistence_backend,
)

LONG_DETECTOR_VERSION = "stage3c7a-runtime-compat-v1"
ROUTER_VERSION = "stage3c7a-router-recovered-compat-v1"
POLICY_HASH = "ada659086dc0b573ab1d70cd61b9c7dadc11161c35d371b54dcfd2345a76e383"
TEMPORAL_THRESHOLD_PCT = 0.158514
BENCHMARKS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")

NUMERIC_FEATURES = (
    "f_gate_taker_share_for_selected",
    "f_gate_side_ret_1m_pct",
    "f_new_flow_support",
    "f_new_micro_accel_1_vs_3",
    "f_f_coin_minus_market_30m",
    "f_f_oi_change_30m_pct",
    "f_micro_volume_ratio_last_vs_prev10",
)
CATEGORICAL_LEVELS = ("ALIGNED", "NEUTRAL", "OPPOSITE")
NUMERIC_MEDIANS = (
    0.6169283646548142,
    0.16435080688507187,
    1.0,
    -0.064296709379937,
    1.5216143441615508,
    0.3285398717764232,
    2.5419802941007825,
)
NUMERIC_MEAN = (
    0.6057325572566039,
    0.18528829317306794,
    0.5241477272727273,
    -0.08710865136000104,
    1.7317277053447533,
    0.5954397459137479,
    6.9047392231708296,
)
NUMERIC_SCALE = (
    0.1776447082262635,
    0.352987424558019,
    0.7590266350544673,
    0.3296570225586843,
    1.0673417304961308,
    1.2535813181763242,
    19.297422976860997,
)
ROUTER_COEFFICIENTS = (
    -1.0790736366137357,
    14.229721646048661,
    25.059533150666237,
    19.08743699472061,
    -9.720490492765316,
    -6.0474067588877585,
    -9.187351232530252,
    25.343019036686428,
    -11.210163247347625,
    -0.7122264522857128,
)
ROUTER_INTERCEPT = 13.420629337053159

VETO_ACCEL_5_VS_15_MAX = 0.6214308333
VETO_SLOPE5_MAX = 0.2612069909
VETO_COIN_MINUS_MARKET_30_MIN = -0.1486000362
VETO_COIN_MINUS_MARKET_15_MAX = 2.5904018610

_INIT_LOCK = threading.Lock()
_INITIALIZED: set[tuple[str, str]] = set()

SQLITE_SCHEMA = """
create table if not exists long_detector_stage3c7a_state (
    signal_id text primary key,
    created_at_ms integer not null,
    updated_at_ms integer not null,
    gate_checked_at_ms integer,
    gate_price real,
    route text,
    router_probability real,
    status text not null,
    terminal_reason text,
    t0_features_json text not null default '{}',
    gate_json text not null default '{}',
    last_temporal_horizon integer,
    last_temporal_return_pct real,
    detector_version text not null,
    router_version text not null,
    policy_hash text not null
);
create index if not exists idx_stage3c7a_status_time
on long_detector_stage3c7a_state(status, updated_at_ms desc);
"""

POSTGRES_SCHEMA = """
create table if not exists long_detector_stage3c7a_state (
    signal_id text primary key,
    created_at_ms bigint not null,
    updated_at_ms bigint not null,
    gate_checked_at_ms bigint,
    gate_price double precision,
    route text,
    router_probability double precision,
    status text not null,
    terminal_reason text,
    t0_features_json text not null default '{}',
    gate_json text not null default '{}',
    last_temporal_horizon integer,
    last_temporal_return_pct double precision,
    detector_version text not null,
    router_version text not null,
    policy_hash text not null
);
create index if not exists idx_stage3c7a_status_time
on long_detector_stage3c7a_state(status, updated_at_ms desc);
"""


def stage3c7a_enabled() -> bool:
    return os.environ.get("PAPER_LONG_DETECTOR_POLICY", "generic").strip().lower() == "stage3c7a"


def _initialize_store() -> None:
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


def get_stage3c7a_state(signal_id: str) -> dict[str, Any] | None:
    _initialize_store()
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(
                "select * from long_detector_stage3c7a_state where signal_id=?",
                (signal_id,),
            ).fetchone()
            out = dict(row) if row else None
    else:
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "select * from long_detector_stage3c7a_state where signal_id=%s",
                    (signal_id,),
                )
                row = cur.fetchone()
                out = dict(row) if row else None
    if out:
        for key, target in (("t0_features_json", "t0_features"), ("gate_json", "gate")):
            try:
                out[target] = json.loads(out.get(key) or "{}")
            except Exception:
                out[target] = {}
    return out


def _save_state(
    *,
    signal_id: str,
    gate_checked_at_ms: int | None,
    gate_price: float | None,
    route: str | None,
    router_probability: float | None,
    status: str,
    terminal_reason: str | None,
    t0_features: dict[str, Any] | None,
    gate: dict[str, Any] | None,
    last_temporal_horizon: int | None = None,
    last_temporal_return_pct: float | None = None,
) -> dict[str, Any]:
    _initialize_store()
    now_ms = int(time.time() * 1000)
    values = (
        signal_id, now_ms, now_ms, gate_checked_at_ms, gate_price, route,
        router_probability, status, terminal_reason,
        json.dumps(t0_features or {}, separators=(",", ":"), allow_nan=False),
        json.dumps(gate or {}, separators=(",", ":"), allow_nan=False),
        last_temporal_horizon, last_temporal_return_pct,
        LONG_DETECTOR_VERSION, ROUTER_VERSION, POLICY_HASH,
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                insert into long_detector_stage3c7a_state (
                    signal_id,created_at_ms,updated_at_ms,gate_checked_at_ms,
                    gate_price,route,router_probability,status,terminal_reason,
                    t0_features_json,gate_json,last_temporal_horizon,
                    last_temporal_return_pct,detector_version,router_version,policy_hash
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(signal_id) do update set
                    updated_at_ms=excluded.updated_at_ms,
                    status=excluded.status,
                    terminal_reason=excluded.terminal_reason,
                    last_temporal_horizon=excluded.last_temporal_horizon,
                    last_temporal_return_pct=excluded.last_temporal_return_pct
                """,
                values,
            )
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into long_detector_stage3c7a_state (
                        signal_id,created_at_ms,updated_at_ms,gate_checked_at_ms,
                        gate_price,route,router_probability,status,terminal_reason,
                        t0_features_json,gate_json,last_temporal_horizon,
                        last_temporal_return_pct,detector_version,router_version,policy_hash
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict(signal_id) do update set
                        updated_at_ms=excluded.updated_at_ms,
                        status=excluded.status,
                        terminal_reason=excluded.terminal_reason,
                        last_temporal_horizon=excluded.last_temporal_horizon,
                        last_temporal_return_pct=excluded.last_temporal_return_pct
                    """,
                    values,
                )
    return get_stage3c7a_state(signal_id) or {}


def _complete_initialization(
    *,
    signal_id: str,
    route: str,
    router_probability: float,
    status: str,
    terminal_reason: str | None,
    t0_features: dict[str, Any],
) -> dict[str, Any]:
    """Finalize T0 exactly once after the first Stage11C ENTER was frozen."""
    _initialize_store()
    payload = json.dumps(t0_features, separators=(",", ":"), allow_nan=False)
    now_ms = int(time.time() * 1000)
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                update long_detector_stage3c7a_state
                set updated_at_ms=?, route=?, router_probability=?, status=?,
                    terminal_reason=?, t0_features_json=?
                where signal_id=? and route='INIT_PENDING'
                """,
                (
                    now_ms, route, router_probability, status,
                    terminal_reason, payload, signal_id,
                ),
            )
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update long_detector_stage3c7a_state
                    set updated_at_ms=%s, route=%s, router_probability=%s, status=%s,
                        terminal_reason=%s, t0_features_json=%s
                    where signal_id=%s and route='INIT_PENDING'
                    """,
                    (
                        now_ms, route, router_probability, status,
                        terminal_reason, payload, signal_id,
                    ),
                )
    return get_stage3c7a_state(signal_id) or {}


def _f(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _family_score(value: str) -> float:
    v = str(value or "").upper()
    if v in {"ALIGNED", "SUPPORTIVE"}:
        return 1.0
    if v == "OPPOSITE":
        return -1.0
    return 0.0


def _safe_div(a: float, b: float, eps: float = 1e-9) -> float:
    return a / (abs(b) + eps)


def _bar(row: list[Any]) -> dict[str, float]:
    return {
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5]),
        "close_time": float(row[6]),
        "quote": float(row[7]),
        "trades": float(row[8]),
        "taker_buy_quote": float(row[10]),
    }


def _closed_rows(rows: Iterable[list[Any]], cutoff_ms: int) -> list[list[Any]]:
    by_open: dict[int, list[Any]] = {}
    for row in rows:
        if isinstance(row, list) and len(row) >= 11 and int(row[6]) <= cutoff_ms:
            by_open[int(row[0])] = row
    return [by_open[k] for k in sorted(by_open)]


def _ret(bars: list[dict[str, float]], minutes: int) -> float:
    if len(bars) < 2:
        return 0.0
    end = len(bars) - 1
    start = max(0, end - minutes)
    return 100.0 * (bars[end]["close"] / bars[start]["close"] - 1.0)


def _fetch_1m(client: Any, symbol: str, cutoff_ms: int, *, limit: int = 40) -> list[list[Any]]:
    rows = client.get(
        "/fapi/v1/klines",
        {"symbol": symbol.upper(), "interval": "1m", "endTime": int(cutoff_ms), "limit": int(limit)},
    )
    return _closed_rows(rows or [], cutoff_ms)


def _derive_market_relative(
    coin_rows: list[list[Any]],
    benchmark_rows: dict[str, list[list[Any]]],
    cutoff_ms: int,
) -> tuple[float, float]:
    coin = [_bar(r) for r in coin_rows[-30:]]
    if len(coin) < 20:
        raise RuntimeError("stage3c7a_insufficient_coin_history")
    benches = {
        symbol: [_bar(r) for r in _closed_rows(rows, cutoff_ms)[-30:]]
        for symbol, rows in benchmark_rows.items()
    }
    if not benches or min(len(x) for x in benches.values()) < 20:
        raise RuntimeError("stage3c7a_insufficient_benchmark_history")
    market15 = statistics.median(_ret(benches[s], 15) for s in BENCHMARKS)
    market30 = statistics.median(_ret(benches[s], 30) for s in BENCHMARKS)
    return _ret(coin, 15) - market15, _ret(coin, 30) - market30


def _derive_micro_volume_ratio(coin_rows: list[list[Any]]) -> float:
    bars = [_bar(r) for r in coin_rows[-30:]]
    if len(bars) < 16:
        raise RuntimeError("stage3c7a_insufficient_micro_history")
    prev10 = [b["volume"] for b in bars[-11:-1]]
    return _safe_div(bars[-1]["volume"], statistics.median(prev10))


def _derive_slope5(coin_rows: list[list[Any]]) -> float:
    bars = [_bar(r) for r in coin_rows[-30:]]
    if len(bars) < 5:
        raise RuntimeError("stage3c7a_insufficient_slope_history")
    closes = [x["close"] for x in bars[-5:]]
    xs = list(range(len(closes)))
    mx = sum(xs) / len(xs)
    my = sum(closes) / len(closes)
    denom = sum((x - mx) ** 2 for x in xs)
    slope = _safe_div(sum((x - mx) * (y - my) for x, y in zip(xs, closes)), denom)
    return 100.0 * slope / closes[-1]


def _derive_oi_change_30m(oi_rows: Iterable[dict[str, Any]], cutoff_ms: int) -> float:
    values = [
        float(r["sumOpenInterest"])
        for r in sorted(oi_rows or [], key=lambda x: int(x.get("timestamp", 0)))
        if int(r.get("timestamp", 0)) <= cutoff_ms and float(r.get("sumOpenInterest", 0)) > 0
    ]
    if len(values) < 3:
        return 0.0
    base = values[max(0, len(values) - 7)]
    return 100.0 * (values[-1] / base - 1.0) if base else 0.0


def build_t0_features(client: Any, candidate: dict[str, Any], gate: dict[str, Any]) -> dict[str, float | str]:
    if str(candidate.get("side") or "").upper() != "LONG":
        raise RuntimeError("stage3c7a_long_only")
    checked_at_ms = int(gate.get("checked_at_ms") or 0)
    snap = dict(gate.get("snapshot") or {})
    if checked_at_ms <= 0:
        raise RuntimeError("stage3c7a_missing_gate_time")
    signal_raw = candidate.get("signal_snapshot_json") or "{}"
    if isinstance(signal_raw, dict):
        signal = signal_raw
    else:
        signal = json.loads(signal_raw or "{}")
    symbol = str(candidate.get("symbol") or "").upper()

    with ThreadPoolExecutor(max_workers=6) as pool:
        coin_f = pool.submit(_fetch_1m, client, symbol, checked_at_ms, limit=40)
        bench_f = {
            s: pool.submit(_fetch_1m, client, s, checked_at_ms, limit=40)
            for s in BENCHMARKS
        }
        oi_f = pool.submit(client.open_interest_hist, symbol, "5m", 7)
        coin_rows = coin_f.result()
        benchmark_rows = {s: f.result() for s, f in bench_f.items()}
        try:
            oi_rows = oi_f.result()
        except Exception:
            oi_rows = []

    side1 = _f(snap.get("side_ret_1m_pct"))
    side3 = _f(snap.get("side_ret_3m_pct"))
    taker_buy = _f(snap.get("taker_buy_share_1m"))
    families = snap.get("evidence_families") or {}
    flow_family = str(families.get("FLOW") or "MISSING").upper()
    ret5 = _f(signal.get("ret_5m_pct"))
    ret15 = _f(signal.get("ret_15m_pct"))
    if None in (side1, side3, taker_buy, ret5, ret15):
        raise RuntimeError("stage3c7a_missing_t0_feature")

    coin_minus15, coin_minus30 = _derive_market_relative(
        coin_rows, benchmark_rows, checked_at_ms
    )
    return {
        "f_gate_flow_family": flow_family,
        "f_gate_taker_share_for_selected": float(taker_buy),
        "f_gate_side_ret_1m_pct": float(side1),
        "f_new_flow_support": _family_score(flow_family),
        "f_new_micro_accel_1_vs_3": float(side1) - float(side3) / 3.0,
        "f_f_coin_minus_market_30m": coin_minus30,
        "f_f_oi_change_30m_pct": _derive_oi_change_30m(oi_rows, checked_at_ms),
        "f_micro_volume_ratio_last_vs_prev10": _derive_micro_volume_ratio(coin_rows),
        "f_new_accel_5_vs_15": float(ret5) - float(ret15) / 3.0,
        "f_f_selected_slope5_norm": _derive_slope5(coin_rows),
        "f_f_coin_minus_market_15m": coin_minus15,
    }


def router_probability(features: dict[str, Any]) -> float:
    numeric = []
    for i, name in enumerate(NUMERIC_FEATURES):
        value = _f(features.get(name))
        if value is None:
            value = NUMERIC_MEDIANS[i]
        numeric.append((value - NUMERIC_MEAN[i]) / NUMERIC_SCALE[i])
    family = str(features.get("f_gate_flow_family") or "").upper()
    vector = numeric + [1.0 if family == lvl else 0.0 for lvl in CATEGORICAL_LEVELS]
    score = ROUTER_INTERCEPT + sum(c * x for c, x in zip(ROUTER_COEFFICIENTS, vector))
    if score >= 0:
        z = math.exp(-score)
        return 1.0 / (1.0 + z)
    z = math.exp(score)
    return z / (1.0 + z)


def route_t0(features: dict[str, Any]) -> tuple[str, float]:
    probability = router_probability(features)
    return ("FLOW_ALIGNED" if probability >= 0.5 else "COUNTERFLOW", probability)


def counterflow_veto(features: dict[str, Any]) -> bool:
    vals = {
        k: _f(features.get(k))
        for k in (
            "f_new_accel_5_vs_15",
            "f_f_selected_slope5_norm",
            "f_f_coin_minus_market_30m",
            "f_f_coin_minus_market_15m",
        )
    }
    if any(v is None for v in vals.values()):
        return True
    return bool(
        vals["f_new_accel_5_vs_15"] <= VETO_ACCEL_5_VS_15_MAX
        and vals["f_f_selected_slope5_norm"] <= VETO_SLOPE5_MAX
        and vals["f_f_coin_minus_market_30m"] >= VETO_COIN_MINUS_MARKET_30_MIN
        and vals["f_f_coin_minus_market_15m"] <= VETO_COIN_MINUS_MARKET_15_MAX
    )


def _result(state: dict[str, Any], *, reason: str | None = None) -> dict[str, Any]:
    status = str(state.get("status") or "WAIT").upper()
    return {
        "verdict": status,
        "reason": reason or state.get("terminal_reason"),
        "route": state.get("route"),
        "router_probability": state.get("router_probability"),
        "gate_checked_at_ms": state.get("gate_checked_at_ms"),
        "gate_price": state.get("gate_price"),
        "last_temporal_horizon": state.get("last_temporal_horizon"),
        "last_temporal_return_pct": state.get("last_temporal_return_pct"),
        "decision_at_ms": state.get("updated_at_ms"),
        "detector_version": LONG_DETECTOR_VERSION,
        "router_version": ROUTER_VERSION,
        "policy_hash": POLICY_HASH,
        "t0_features": state.get("t0_features") or {},
        "frozen_gate": state.get("gate") or {},
    }


def _temporal_rows(client: Any, symbol: str, gate_ms: int, now_ms: int) -> list[list[Any]]:
    rows = client.get(
        "/fapi/v1/klines",
        {
            "symbol": symbol.upper(),
            "interval": "1m",
            "startTime": max(0, gate_ms - 60_000),
            "endTime": now_ms,
            "limit": 10,
        },
    )
    return _closed_rows(rows or [], now_ms)


def _evaluate_flow_temporal(client: Any, candidate: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    gate_ms = int(state["gate_checked_at_ms"])
    gate_price = float(state["gate_price"])
    now_ms = int(time.time() * 1000)
    rows = _temporal_rows(client, str(candidate["symbol"]), gate_ms, now_ms)
    last_h: int | None = None
    last_ret: float | None = None
    for horizon in (1, 2, 3):
        target = gate_ms + horizon * 60_000
        if now_ms < target:
            break
        new_rows = [r for r in rows if int(r[6]) > gate_ms and int(r[6]) <= target]
        last_h = horizon
        if not new_rows:
            continue
        latest_close = float(new_rows[-1][4])
        last_ret = 100.0 * (latest_close / gate_price - 1.0)
        if last_ret >= TEMPORAL_THRESHOLD_PCT:
            saved = _save_state(
                signal_id=str(candidate["signal_id"]),
                gate_checked_at_ms=gate_ms,
                gate_price=gate_price,
                route="FLOW_ALIGNED",
                router_probability=float(state["router_probability"]),
                status="ENTER",
                terminal_reason=f"stage3c7a_temporal_t{horizon}_pass",
                t0_features=state.get("t0_features") or {},
                gate=state.get("gate") or {},
                last_temporal_horizon=horizon,
                last_temporal_return_pct=last_ret,
            )
            return _result(saved)
    if now_ms >= gate_ms + 3 * 60_000 and last_h == 3:
        saved = _save_state(
            signal_id=str(candidate["signal_id"]),
            gate_checked_at_ms=gate_ms,
            gate_price=gate_price,
            route="FLOW_ALIGNED",
            router_probability=float(state["router_probability"]),
            status="CANCEL",
            terminal_reason="stage3c7a_temporal_no_confirmation_by_t3",
            t0_features=state.get("t0_features") or {},
            gate=state.get("gate") or {},
            last_temporal_horizon=last_h,
            last_temporal_return_pct=last_ret,
        )
        return _result(saved)
    saved = _save_state(
        signal_id=str(candidate["signal_id"]),
        gate_checked_at_ms=gate_ms,
        gate_price=gate_price,
        route="FLOW_ALIGNED",
        router_probability=float(state["router_probability"]),
        status="WAIT",
        terminal_reason=None,
        t0_features=state.get("t0_features") or {},
        gate=state.get("gate") or {},
        last_temporal_horizon=last_h,
        last_temporal_return_pct=last_ret,
    )
    return _result(saved, reason="stage3c7a_wait_temporal")


def _initialize_from_frozen_gate(
    client: Any,
    candidate: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    gate = dict(state.get("gate") or {})
    features = build_t0_features(client, candidate, gate)
    route, probability = route_t0(features)
    signal_id = str(candidate["signal_id"])

    if route == "COUNTERFLOW":
        vetoed = counterflow_veto(features)
        saved = _complete_initialization(
            signal_id=signal_id,
            route=route,
            router_probability=probability,
            status="CANCEL" if vetoed else "ENTER",
            terminal_reason=(
                "stage3c7a_counterflow_veto"
                if vetoed else "stage3c7a_counterflow_pass"
            ),
            t0_features=features,
        )
        return _result(saved)

    saved = _complete_initialization(
        signal_id=signal_id,
        route=route,
        router_probability=probability,
        status="WAIT",
        terminal_reason=None,
        t0_features=features,
    )
    return _evaluate_flow_temporal(client, candidate, saved)


def evaluate_stage3c7a(
    client: Any,
    candidate: dict[str, Any],
    *,
    gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    signal_id = str(candidate["signal_id"])
    side = str(candidate.get("side") or "").upper()
    if side != "LONG":
        return {
            "verdict": "CANCEL",
            "reason": "stage3c7a_long_only_short_blocked",
            "route": None,
            "detector_version": LONG_DETECTOR_VERSION,
            "router_version": ROUTER_VERSION,
            "policy_hash": POLICY_HASH,
            "t0_features": {},
            "frozen_gate": {},
        }

    state = get_stage3c7a_state(signal_id)
    if state is not None:
        if str(state.get("status") or "").upper() in {"ENTER", "CANCEL"}:
            return _result(state)
        route = str(state.get("route") or "")
        if route == "INIT_PENDING":
            return _initialize_from_frozen_gate(client, candidate, state)
        if route == "FLOW_ALIGNED":
            return _evaluate_flow_temporal(client, candidate, state)
        return _result(state, reason="stage3c7a_invalid_persisted_state")

    if gate is None or str(gate.get("verdict") or "").upper() != "ENTER":
        return {
            "verdict": "WAIT",
            "reason": "stage3c7a_wait_stage11c_enter",
            "route": None,
            "detector_version": LONG_DETECTOR_VERSION,
            "router_version": ROUTER_VERSION,
            "policy_hash": POLICY_HASH,
            "t0_features": {},
            "frozen_gate": dict(gate or {}),
        }

    gate_snap = {
        "checked_at_ms": int(gate["checked_at_ms"]),
        "verdict": "ENTER",
        "version": gate.get("version"),
        "reasons": list(gate.get("reasons") or []),
        "snapshot": dict(gate.get("snapshot") or {}),
    }
    gate_price = _f((gate.get("snapshot") or {}).get("current_price"))
    if gate_price is None or gate_price <= 0:
        raise RuntimeError("stage3c7a_missing_gate_price")

    # Persist the first Stage11C ENTER before any heavier market fetch. If a
    # fetch fails, the retry resumes from this same causal cutoff after restart.
    state = _save_state(
        signal_id=signal_id,
        gate_checked_at_ms=int(gate["checked_at_ms"]),
        gate_price=gate_price,
        route="INIT_PENDING",
        router_probability=None,
        status="WAIT",
        terminal_reason="stage3c7a_t0_initializing",
        t0_features={},
        gate=gate_snap,
    )
    return _initialize_from_frozen_gate(client, candidate, state)