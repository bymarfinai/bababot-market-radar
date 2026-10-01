from __future__ import annotations

import os
import threading
import time
from typing import Any

from .persistence import _postgres_connect, _sqlite_connect, database_path, persistence_backend


PP_DECISION_V2_DISCRIMINATOR_VERSION = "pp-decision-v2-stage5-runner-failure-discriminator"

# Frozen after chronological DEV / VAL / TEST analysis of the Stage 3 prospective cohort.
STAGE5_WATCH_SECONDS = 30.0
STAGE5_FAILURE_CURRENT_PNL_PCT = 0.15
STAGE5_TRANSIENT_INITIAL_MFE_PCT = 0.70
STAGE5_TRANSIENT_INITIAL_CURRENT_PNL_PCT = 0.45
STAGE5_TRANSIENT_FOLLOWUP_CURRENT_PNL_PCT = 0.30

_STORE_LOCK = threading.Lock()
_STORE_READY: set[tuple[str, str]] = set()
_STATE_LOCK = threading.Lock()
_STATE_CACHE: dict[str, dict[str, Any]] = {}


SQLITE_SCHEMA = """
create table if not exists pp_decision_v2_discriminator (
    position_id text primary key,
    opened_at_ms integer not null,
    watch_started_at_ms integer not null,
    initial_mfe_pct real not null,
    initial_current_pnl_pct real not null,
    initial_giveback_ratio real not null,
    initial_base_v1_action text not null,
    initial_final_action text not null,
    initial_fast_gate text not null,
    initial_danger_score integer not null,
    status text not null,
    classified_at_ms integer,
    followup_current_pnl_pct real,
    followup_mfe_pct real,
    confidence text,
    classifier_version text not null,
    updated_at_ms integer not null
);
create index if not exists idx_pp_decision_v2_discriminator_status
on pp_decision_v2_discriminator(status, watch_started_at_ms);
"""

POSTGRES_SCHEMA = """
create table if not exists pp_decision_v2_discriminator (
    position_id text primary key,
    opened_at_ms bigint not null,
    watch_started_at_ms bigint not null,
    initial_mfe_pct double precision not null,
    initial_current_pnl_pct double precision not null,
    initial_giveback_ratio double precision not null,
    initial_base_v1_action text not null,
    initial_final_action text not null,
    initial_fast_gate text not null,
    initial_danger_score integer not null,
    status text not null,
    classified_at_ms bigint,
    followup_current_pnl_pct double precision,
    followup_mfe_pct double precision,
    confidence text,
    classifier_version text not null,
    updated_at_ms bigint not null
);
create index if not exists idx_pp_decision_v2_discriminator_status
on pp_decision_v2_discriminator(status, watch_started_at_ms);
"""


def stage5_discriminator_enabled() -> bool:
    return os.environ.get("PP_DECISION_V2_STAGE5_DISCRIMINATOR_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def stage5_discriminator_start_ms() -> int:
    try:
        return int(os.environ.get("PP_DECISION_V2_STAGE5_START_MS", "0") or 0)
    except (TypeError, ValueError):
        return 0


def initialize_stage5_discriminator_store() -> None:
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


def _row_to_state(row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    keys = (
        "position_id", "opened_at_ms", "watch_started_at_ms", "initial_mfe_pct",
        "initial_current_pnl_pct", "initial_giveback_ratio", "initial_base_v1_action",
        "initial_final_action", "initial_fast_gate", "initial_danger_score", "status",
        "classified_at_ms", "followup_current_pnl_pct", "followup_mfe_pct", "confidence",
        "classifier_version", "updated_at_ms",
    )
    return dict(zip(keys, row))


def _load_state(position_id: str) -> dict[str, Any] | None:
    initialize_stage5_discriminator_store()
    sql = """
        select position_id,opened_at_ms,watch_started_at_ms,initial_mfe_pct,
               initial_current_pnl_pct,initial_giveback_ratio,initial_base_v1_action,
               initial_final_action,initial_fast_gate,initial_danger_score,status,
               classified_at_ms,followup_current_pnl_pct,followup_mfe_pct,confidence,
               classifier_version,updated_at_ms
        from pp_decision_v2_discriminator where position_id = {ph}
    """
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            row = conn.execute(sql.format(ph="?"), (str(position_id),)).fetchone()
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql.format(ph="%s"), (str(position_id),))
                row = cur.fetchone()
    return _row_to_state(row)


def _save_state(state: dict[str, Any]) -> None:
    initialize_stage5_discriminator_store()
    now = int(time.time() * 1000)
    state["updated_at_ms"] = now
    values = (
        str(state["position_id"]), int(state["opened_at_ms"]), int(state["watch_started_at_ms"]),
        float(state["initial_mfe_pct"]), float(state["initial_current_pnl_pct"]),
        float(state["initial_giveback_ratio"]), str(state["initial_base_v1_action"]),
        str(state["initial_final_action"]), str(state["initial_fast_gate"]),
        int(state["initial_danger_score"]), str(state["status"]),
        None if state.get("classified_at_ms") is None else int(state["classified_at_ms"]),
        None if state.get("followup_current_pnl_pct") is None else float(state["followup_current_pnl_pct"]),
        None if state.get("followup_mfe_pct") is None else float(state["followup_mfe_pct"]),
        state.get("confidence"), PP_DECISION_V2_DISCRIMINATOR_VERSION, now,
    )
    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                insert into pp_decision_v2_discriminator (
                    position_id,opened_at_ms,watch_started_at_ms,initial_mfe_pct,
                    initial_current_pnl_pct,initial_giveback_ratio,initial_base_v1_action,
                    initial_final_action,initial_fast_gate,initial_danger_score,status,
                    classified_at_ms,followup_current_pnl_pct,followup_mfe_pct,confidence,
                    classifier_version,updated_at_ms
                ) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                on conflict(position_id) do update set
                    status=excluded.status,
                    classified_at_ms=excluded.classified_at_ms,
                    followup_current_pnl_pct=excluded.followup_current_pnl_pct,
                    followup_mfe_pct=excluded.followup_mfe_pct,
                    confidence=excluded.confidence,
                    classifier_version=excluded.classifier_version,
                    updated_at_ms=excluded.updated_at_ms
                """,
                values,
            )
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into pp_decision_v2_discriminator (
                        position_id,opened_at_ms,watch_started_at_ms,initial_mfe_pct,
                        initial_current_pnl_pct,initial_giveback_ratio,initial_base_v1_action,
                        initial_final_action,initial_fast_gate,initial_danger_score,status,
                        classified_at_ms,followup_current_pnl_pct,followup_mfe_pct,confidence,
                        classifier_version,updated_at_ms
                    ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    on conflict(position_id) do update set
                        status=excluded.status,
                        classified_at_ms=excluded.classified_at_ms,
                        followup_current_pnl_pct=excluded.followup_current_pnl_pct,
                        followup_mfe_pct=excluded.followup_mfe_pct,
                        confidence=excluded.confidence,
                        classifier_version=excluded.classifier_version,
                        updated_at_ms=excluded.updated_at_ms
                    """,
                    values,
                )


def _public_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": PP_DECISION_V2_DISCRIMINATOR_VERSION,
        "status": state["status"],
        "watch_started_at_ms": int(state["watch_started_at_ms"]),
        "initial_mfe_pct": float(state["initial_mfe_pct"]),
        "initial_current_pnl_pct": float(state["initial_current_pnl_pct"]),
        "classified_at_ms": state.get("classified_at_ms"),
        "followup_current_pnl_pct": state.get("followup_current_pnl_pct"),
        "followup_mfe_pct": state.get("followup_mfe_pct"),
        "confidence": state.get("confidence"),
    }


def evaluate_stage5_discriminator(
    *,
    position_id: str,
    opened_at_ms: int,
    evaluated_at_ms: int,
    mfe_pct: float,
    current_pnl_pct: float,
    v2_result: dict[str, Any],
) -> dict[str, Any] | None:
    """Observation-only runner-vs-failure discriminator.

    This function never modifies ``v2_result`` or trading state. It watches the
    first actionable 0.5%-<1% V2 event, then classifies the fade using a causal
    30-second follow-up window. Final labels are intentionally conservative.
    """
    if not stage5_discriminator_enabled():
        return None
    if int(opened_at_ms) <= stage5_discriminator_start_ms():
        return None

    pid = str(position_id)
    with _STATE_LOCK:
        state = _STATE_CACHE.get(pid)
        if state is None:
            state = _load_state(pid)
            if state is not None:
                _STATE_CACHE[pid] = state

        if state is None:
            mfe = float(mfe_pct)
            action = str(v2_result.get("final_action") or "HOLD").upper()
            if not (0.50 <= mfe < 1.00 and action in {"REDUCE", "CLOSE"}):
                return None
            state = {
                "position_id": pid,
                "opened_at_ms": int(opened_at_ms),
                "watch_started_at_ms": int(evaluated_at_ms),
                "initial_mfe_pct": mfe,
                "initial_current_pnl_pct": float(current_pnl_pct),
                "initial_giveback_ratio": float(v2_result.get("giveback_ratio") or 0.0),
                "initial_base_v1_action": str(v2_result.get("base_v1_action") or "HOLD").upper(),
                "initial_final_action": action,
                "initial_fast_gate": str(v2_result.get("fast_gate") or "DISARMED"),
                "initial_danger_score": int(v2_result.get("danger_score") or 0),
                "status": "WATCHING",
                "classified_at_ms": None,
                "followup_current_pnl_pct": None,
                "followup_mfe_pct": None,
                "confidence": None,
                "classifier_version": PP_DECISION_V2_DISCRIMINATOR_VERSION,
                "updated_at_ms": int(evaluated_at_ms),
            }
            _save_state(state)
            _STATE_CACHE[pid] = state
            return _public_state(state)

        if state["status"] != "WATCHING":
            return _public_state(state)

        elapsed = max(0.0, (int(evaluated_at_ms) - int(state["watch_started_at_ms"])) / 1000.0)
        current = float(current_pnl_pct)
        mfe = float(mfe_pct)

        if mfe >= 1.00:
            state["status"] = "TRANSIENT_CONFIRMED"
            state["confidence"] = "CONFIRMED"
        elif elapsed < STAGE5_WATCH_SECONDS:
            return _public_state(state)
        elif current < STAGE5_FAILURE_CURRENT_PNL_PCT:
            state["status"] = "FAILURE_LIKELY"
            state["confidence"] = "HIGH"
        elif (
            float(state["initial_mfe_pct"]) >= STAGE5_TRANSIENT_INITIAL_MFE_PCT
            and float(state["initial_current_pnl_pct"]) >= STAGE5_TRANSIENT_INITIAL_CURRENT_PNL_PCT
            and str(state["initial_base_v1_action"]) == "HOLD"
            and current >= STAGE5_TRANSIENT_FOLLOWUP_CURRENT_PNL_PCT
        ):
            state["status"] = "TRANSIENT_LIKELY"
            state["confidence"] = "MEDIUM_HIGH"
        else:
            state["status"] = "AMBIGUOUS"
            state["confidence"] = "LOW"

        state["classified_at_ms"] = int(evaluated_at_ms)
        state["followup_current_pnl_pct"] = current
        state["followup_mfe_pct"] = mfe
        _save_state(state)
        _STATE_CACHE[pid] = state
        return _public_state(state)
