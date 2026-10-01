from __future__ import annotations

import json
import threading
import time
from typing import Any

import psycopg2.extras

from .fresh_entry_gate import STAGE11C_VERSION
from .pipeline_cohort import POST_COHORT
from .persistence import (
    _postgres_connect,
    _sqlite_connect,
    database_path,
    initialize_database,
    persistence_backend,
)


WD1_LABEL_VERSION = "wd1-outcome-taxonomy-v1"
WD1_TARGET_GATE_VERSION = STAGE11C_VERSION
WD1_DISCOVERY_CUTOFF_MS = 1790826404280

TRUE_WRONG_DIRECTION = "TRUE_WRONG_DIRECTION"
RECOVERED_DRAWDOWN = "RECOVERED_DRAWDOWN"
STALL_NO_EDGE = "STALL_NO_EDGE"
RIGHT_THEN_FAILURE = "RIGHT_THEN_FAILURE"
CORRECT_RUNNER = "CORRECT_RUNNER"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

PRIMARY_LABELS = (
    TRUE_WRONG_DIRECTION,
    RECOVERED_DRAWDOWN,
    STALL_NO_EDGE,
    RIGHT_THEN_FAILURE,
    CORRECT_RUNNER,
)

# Frozen WD-1 outcome taxonomy thresholds. These are research labels, not
# production trading rules.
EARLY_WINDOW_MINUTES = 30.0
EARLY_ADVERSE_MAE_PCT = -0.35
WRONG_DIRECTION_MFE_CEILING_PCT = 0.35
DIRECTIONALLY_VALID_MFE_PCT = 0.50
RUNNER_MFE_PCT = 1.00

_LOCK = threading.Lock()
_READY: set[tuple[str, str]] = set()

SQLITE_SCHEMA = """
create table if not exists wd1_trade_labels (
    position_id text primary key references positions(position_id) on delete cascade,
    signal_id text,
    symbol text not null,
    side text not null,
    opened_at_ms integer not null,
    closed_at_ms integer not null,
    fresh_gate_version text not null,
    outcome_label text not null,
    label_version text not null,
    evaluation_count integer not null,
    max_mfe_pct real,
    min_mae_pct real,
    early_min_mae_pct real,
    first_early_adverse_at_ms integer,
    first_directional_mfe_at_ms integer,
    reached_runner_1pct integer not null default 0,
    realized_pnl real,
    realized_pnl_pct real,
    close_reason text,
    evidence_json text not null default '{}',
    labeled_at_ms integer not null
);
create index if not exists idx_wd1_label
on wd1_trade_labels(outcome_label, opened_at_ms);
create index if not exists idx_wd1_gate
on wd1_trade_labels(fresh_gate_version, opened_at_ms);
"""

POSTGRES_SCHEMA = """
create table if not exists wd1_trade_labels (
    position_id text primary key references positions(position_id) on delete cascade,
    signal_id text,
    symbol text not null,
    side text not null,
    opened_at_ms bigint not null,
    closed_at_ms bigint not null,
    fresh_gate_version text not null,
    outcome_label text not null,
    label_version text not null,
    evaluation_count integer not null,
    max_mfe_pct double precision,
    min_mae_pct double precision,
    early_min_mae_pct double precision,
    first_early_adverse_at_ms bigint,
    first_directional_mfe_at_ms bigint,
    reached_runner_1pct integer not null default 0,
    realized_pnl double precision,
    realized_pnl_pct double precision,
    close_reason text,
    evidence_json text not null default '{}',
    labeled_at_ms bigint not null
);
create index if not exists idx_wd1_label
on wd1_trade_labels(outcome_label, opened_at_ms);
create index if not exists idx_wd1_gate
on wd1_trade_labels(fresh_gate_version, opened_at_ms);
"""


def initialize_wd1_store() -> None:
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


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _realized_pct(position: dict[str, Any]) -> float | None:
    direct = _f(position.get("realized_pnl_pct"))
    if direct is not None:
        return direct
    pnl = _f(position.get("realized_pnl"))
    if pnl is None:
        return None
    raw: dict[str, Any] = {}
    try:
        raw = json.loads(position.get("raw_json") or "{}")
    except Exception:
        raw = {}
    notional = _f(raw.get("initial_notional_usdt"))
    if notional and notional > 0:
        return 100.0 * pnl / notional
    return None


def classify_trade_outcome(
    position: dict[str, Any],
    evaluations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify one fully closed paper trade using outcome data only.

    The label intentionally does not use Stage 4/5/6/11C features. Those become
    explanatory features in WD-2. WD-1 labels are based on the realized outcome
    plus post-entry excursion path, preventing feature/label circularity.
    """
    opened_at_ms = int(position.get("opened_at_ms") or 0)
    closed_at_ms = int(position.get("closed_at_ms") or 0)
    if opened_at_ms <= 0 or closed_at_ms <= 0 or closed_at_ms < opened_at_ms:
        return {
            "label": INSUFFICIENT_DATA,
            "reason": "invalid_position_timestamps",
            "evaluation_count": 0,
        }

    usable: list[dict[str, Any]] = []
    for row in evaluations:
        ts = int(row.get("evaluated_at_ms") or row.get("candle_close_time_ms") or 0)
        if ts < opened_at_ms or ts > closed_at_ms:
            continue
        mfe = _f(row.get("mfe_pct"))
        mae = _f(row.get("mae_pct"))
        if mfe is None and mae is None:
            continue
        usable.append({**row, "_ts": ts, "_mfe": mfe, "_mae": mae})
    usable.sort(key=lambda row: int(row["_ts"]))

    if not usable:
        return {
            "label": INSUFFICIENT_DATA,
            "reason": "no_causal_excursion_evaluations",
            "evaluation_count": 0,
        }

    mfe_values = [float(row["_mfe"]) for row in usable if row["_mfe"] is not None]
    mae_values = [float(row["_mae"]) for row in usable if row["_mae"] is not None]
    if not mfe_values or not mae_values:
        return {
            "label": INSUFFICIENT_DATA,
            "reason": "missing_mfe_or_mae_path",
            "evaluation_count": len(usable),
        }

    max_mfe = max(mfe_values)
    min_mae = min(mae_values)
    early_end_ms = opened_at_ms + int(EARLY_WINDOW_MINUTES * 60_000)

    early_mae_rows = [
        row
        for row in usable
        if int(row["_ts"]) <= early_end_ms and row["_mae"] is not None
    ]
    early_min_mae = (
        min(float(row["_mae"]) for row in early_mae_rows)
        if early_mae_rows
        else None
    )

    adverse_rows = [
        row
        for row in early_mae_rows
        if float(row["_mae"]) <= EARLY_ADVERSE_MAE_PCT
    ]
    first_adverse_at = (
        min(int(row["_ts"]) for row in adverse_rows)
        if adverse_rows
        else None
    )

    directional_rows = [
        row
        for row in usable
        if row["_mfe"] is not None
        and float(row["_mfe"]) >= DIRECTIONALLY_VALID_MFE_PCT
    ]
    first_directional_at = (
        min(int(row["_ts"]) for row in directional_rows)
        if directional_rows
        else None
    )

    realized_pnl = _f(position.get("realized_pnl"))
    realized_pct = _realized_pct(position)
    if realized_pnl is None and realized_pct is None:
        return {
            "label": INSUFFICIENT_DATA,
            "reason": "missing_realized_outcome",
            "evaluation_count": len(usable),
            "max_mfe_pct": max_mfe,
            "min_mae_pct": min_mae,
            "early_min_mae_pct": early_min_mae,
        }

    final_profitable = (
        realized_pnl > 0
        if realized_pnl is not None
        else bool(realized_pct is not None and realized_pct > 0)
    )
    final_nonpositive = not final_profitable
    early_adverse = first_adverse_at is not None
    reached_directional = max_mfe >= DIRECTIONALLY_VALID_MFE_PCT
    reached_runner = max_mfe >= RUNNER_MFE_PCT

    # Priority matters. If a trade demonstrated >=0.50% favorable excursion
    # and still ended non-positive, direction was validated at least once; that
    # is a profit/exit failure, not a true wrong-direction label.
    if reached_directional and final_nonpositive:
        label = RIGHT_THEN_FAILURE
        reason = "directional_mfe_reached_but_final_nonpositive"
    elif (
        reached_directional
        and final_profitable
        and early_adverse
        and first_directional_at is not None
        and first_adverse_at < first_directional_at
    ):
        label = RECOVERED_DRAWDOWN
        reason = "early_adverse_then_later_directional_recovery"
    elif reached_directional and final_profitable:
        label = CORRECT_RUNNER
        reason = "directional_mfe_reached_and_final_profitable"
    elif (
        max_mfe < WRONG_DIRECTION_MFE_CEILING_PCT
        and early_adverse
        and final_nonpositive
    ):
        label = TRUE_WRONG_DIRECTION
        reason = "early_adverse_low_mfe_final_nonpositive"
    else:
        label = STALL_NO_EDGE
        reason = "never_reached_directional_mfe_without_strict_wrong_direction_path"

    return {
        "label": label,
        "reason": reason,
        "evaluation_count": len(usable),
        "max_mfe_pct": max_mfe,
        "min_mae_pct": min_mae,
        "early_min_mae_pct": early_min_mae,
        "first_early_adverse_at_ms": first_adverse_at,
        "first_directional_mfe_at_ms": first_directional_at,
        "reached_runner_1pct": reached_runner,
        "realized_pnl": realized_pnl,
        "realized_pnl_pct": realized_pct,
        "thresholds": {
            "early_window_minutes": EARLY_WINDOW_MINUTES,
            "early_adverse_mae_pct": EARLY_ADVERSE_MAE_PCT,
            "wrong_direction_mfe_ceiling_pct": WRONG_DIRECTION_MFE_CEILING_PCT,
            "directionally_valid_mfe_pct": DIRECTIONALLY_VALID_MFE_PCT,
            "runner_mfe_pct": RUNNER_MFE_PCT,
        },
    }


def _fetch_eligible_positions() -> list[dict[str, Any]]:
    query = """
        select
            p.position_id, p.signal_id, p.symbol, p.side,
            p.opened_at_ms, p.closed_at_ms,
            p.realized_pnl, p.realized_pnl_pct,
            p.close_reason, p.raw_json,
            c.fresh_gate_version
        from positions p
        join pipeline_cohorts c on c.signal_id=p.signal_id
        where p.mode='PAPER'
          and p.status='CLOSED'
          and p.opened_at_ms is not null
          and p.closed_at_ms is not null
          and c.cohort=?
          and c.fresh_gate_version=?
          and p.closed_at_ms <= ?
        order by p.opened_at_ms asc, p.position_id asc
    """
    params = (POST_COHORT, WD1_TARGET_GATE_VERSION, WD1_DISCOVERY_CUTOFF_MS)
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            return [
                dict(row)
                for row in conn.execute(query, params).fetchall()
            ]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), params)
            return [dict(row) for row in cur.fetchall()]


def _fetch_evaluations(position_id: str, closed_at_ms: int) -> list[dict[str, Any]]:
    query = """
        select
            evaluated_at_ms, candle_close_time_ms,
            unrealized_pnl_pct, mfe_pct, mae_pct,
            final_action, lifecycle_version
        from position_evaluations
        where position_id=?
          and evaluated_at_ms <= ?
        order by evaluated_at_ms asc
    """
    params = (position_id, int(closed_at_ms))
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query.replace("?", "%s"), params)
            return [dict(row) for row in cur.fetchall()]


def _upsert_label(position: dict[str, Any], result: dict[str, Any]) -> None:
    now_ms = int(time.time() * 1000)
    evidence = {
        "classification_reason": result.get("reason"),
        "thresholds": result.get("thresholds") or {},
    }
    values = (
        str(position["position_id"]),
        position.get("signal_id"),
        str(position.get("symbol") or ""),
        str(position.get("side") or "").upper(),
        int(position["opened_at_ms"]),
        int(position["closed_at_ms"]),
        str(position.get("fresh_gate_version") or ""),
        str(result["label"]),
        WD1_LABEL_VERSION,
        int(result.get("evaluation_count") or 0),
        result.get("max_mfe_pct"),
        result.get("min_mae_pct"),
        result.get("early_min_mae_pct"),
        result.get("first_early_adverse_at_ms"),
        result.get("first_directional_mfe_at_ms"),
        int(bool(result.get("reached_runner_1pct"))),
        result.get("realized_pnl"),
        result.get("realized_pnl_pct"),
        position.get("close_reason"),
        json.dumps(evidence, separators=(",", ":"), allow_nan=False),
        now_ms,
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                insert into wd1_trade_labels (
                    position_id, signal_id, symbol, side,
                    opened_at_ms, closed_at_ms, fresh_gate_version,
                    outcome_label, label_version, evaluation_count,
                    max_mfe_pct, min_mae_pct, early_min_mae_pct,
                    first_early_adverse_at_ms, first_directional_mfe_at_ms,
                    reached_runner_1pct, realized_pnl, realized_pnl_pct,
                    close_reason, evidence_json, labeled_at_ms
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(position_id) do update set
                    signal_id=excluded.signal_id,
                    symbol=excluded.symbol,
                    side=excluded.side,
                    opened_at_ms=excluded.opened_at_ms,
                    closed_at_ms=excluded.closed_at_ms,
                    fresh_gate_version=excluded.fresh_gate_version,
                    outcome_label=excluded.outcome_label,
                    label_version=excluded.label_version,
                    evaluation_count=excluded.evaluation_count,
                    max_mfe_pct=excluded.max_mfe_pct,
                    min_mae_pct=excluded.min_mae_pct,
                    early_min_mae_pct=excluded.early_min_mae_pct,
                    first_early_adverse_at_ms=excluded.first_early_adverse_at_ms,
                    first_directional_mfe_at_ms=excluded.first_directional_mfe_at_ms,
                    reached_runner_1pct=excluded.reached_runner_1pct,
                    realized_pnl=excluded.realized_pnl,
                    realized_pnl_pct=excluded.realized_pnl_pct,
                    close_reason=excluded.close_reason,
                    evidence_json=excluded.evidence_json,
                    labeled_at_ms=excluded.labeled_at_ms
                """,
                values,
            )
        return
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into wd1_trade_labels (
                    position_id, signal_id, symbol, side,
                    opened_at_ms, closed_at_ms, fresh_gate_version,
                    outcome_label, label_version, evaluation_count,
                    max_mfe_pct, min_mae_pct, early_min_mae_pct,
                    first_early_adverse_at_ms, first_directional_mfe_at_ms,
                    reached_runner_1pct, realized_pnl, realized_pnl_pct,
                    close_reason, evidence_json, labeled_at_ms
                ) values (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )
                on conflict(position_id) do update set
                    signal_id=excluded.signal_id,
                    symbol=excluded.symbol,
                    side=excluded.side,
                    opened_at_ms=excluded.opened_at_ms,
                    closed_at_ms=excluded.closed_at_ms,
                    fresh_gate_version=excluded.fresh_gate_version,
                    outcome_label=excluded.outcome_label,
                    label_version=excluded.label_version,
                    evaluation_count=excluded.evaluation_count,
                    max_mfe_pct=excluded.max_mfe_pct,
                    min_mae_pct=excluded.min_mae_pct,
                    early_min_mae_pct=excluded.early_min_mae_pct,
                    first_early_adverse_at_ms=excluded.first_early_adverse_at_ms,
                    first_directional_mfe_at_ms=excluded.first_directional_mfe_at_ms,
                    reached_runner_1pct=excluded.reached_runner_1pct,
                    realized_pnl=excluded.realized_pnl,
                    realized_pnl_pct=excluded.realized_pnl_pct,
                    close_reason=excluded.close_reason,
                    evidence_json=excluded.evidence_json,
                    labeled_at_ms=excluded.labeled_at_ms
                """,
                values,
            )


def backfill_wd1_labels() -> dict[str, Any]:
    """Idempotently classify the WD-0-clean Stage 11C V2 closed-paper cohort."""
    initialize_wd1_store()
    positions = _fetch_eligible_positions()
    counts = {label: 0 for label in (*PRIMARY_LABELS, INSUFFICIENT_DATA)}
    for position in positions:
        evaluations = _fetch_evaluations(
            str(position["position_id"]),
            int(position["closed_at_ms"]),
        )
        result = classify_trade_outcome(position, evaluations)
        _upsert_label(position, result)
        counts[str(result["label"])] += 1
    return {
        "version": WD1_LABEL_VERSION,
        "target_gate_version": WD1_TARGET_GATE_VERSION,
        "discovery_cutoff_ms": WD1_DISCOVERY_CUTOFF_MS,
        "eligible_closed_positions": len(positions),
        "counts": counts,
    }


def list_wd1_labels(
    *,
    outcome_label: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    initialize_wd1_store()
    safe_limit = max(1, min(int(limit), 10000))
    where = ""
    params: list[Any] = []
    if outcome_label:
        where = " where outcome_label=?"
        params.append(str(outcome_label).upper())
    query = (
        "select * from wd1_trade_labels"
        + where
        + " order by opened_at_ms asc, position_id asc limit ?"
    )
    params.append(safe_limit)
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = [dict(row) for row in conn.execute(query, params).fetchall()]
    else:
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query.replace("?", "%s"), params)
                rows = [dict(row) for row in cur.fetchall()]
    for row in rows:
        try:
            row["evidence"] = json.loads(row.pop("evidence_json") or "{}")
        except Exception:
            row["evidence"] = {}
    return rows


def wd1_summary() -> dict[str, Any]:
    initialize_wd1_store()
    rows = list_wd1_labels(limit=10000)
    usable = [row for row in rows if row["outcome_label"] in PRIMARY_LABELS]
    total = len(usable)
    by_label: dict[str, dict[str, Any]] = {}
    for label in PRIMARY_LABELS:
        subset = [row for row in usable if row["outcome_label"] == label]
        pnl = sum(float(row.get("realized_pnl") or 0.0) for row in subset)
        by_label[label] = {
            "trades": len(subset),
            "share_pct": round(100.0 * len(subset) / total, 4) if total else None,
            "net_pnl": round(pnl, 8),
            "runner_1pct": sum(int(row.get("reached_runner_1pct") or 0) for row in subset),
        }
    insufficient = sum(1 for row in rows if row["outcome_label"] == INSUFFICIENT_DATA)
    return {
        "version": WD1_LABEL_VERSION,
        "authority": "RESEARCH_LABELS_ONLY",
        "target_gate_version": WD1_TARGET_GATE_VERSION,
        "discovery_cutoff_ms": WD1_DISCOVERY_CUTOFF_MS,
        "thresholds": {
            "early_window_minutes": EARLY_WINDOW_MINUTES,
            "early_adverse_mae_pct": EARLY_ADVERSE_MAE_PCT,
            "wrong_direction_mfe_ceiling_pct": WRONG_DIRECTION_MFE_CEILING_PCT,
            "directionally_valid_mfe_pct": DIRECTIONALLY_VALID_MFE_PCT,
            "runner_mfe_pct": RUNNER_MFE_PCT,
        },
        "labeled_rows": len(rows),
        "usable_rows": total,
        "insufficient_data_rows": insufficient,
        "by_label": by_label,
    }

[executed on device: core-prod (c128f313-5bdb-41c3-a53a-0590e5cfa134)]