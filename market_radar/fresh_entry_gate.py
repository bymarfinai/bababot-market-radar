from __future__ import annotations

import json
import os
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
    update_entry_latency,
)


STAGE11C_VERSION = "stage11c-v2-evidence-families"

_STORE_LOCK = threading.Lock()
_STORE_READY: set[tuple[str, str]] = set()

SQLITE_SCHEMA = """
create table if not exists entry_revalidations (
    revalidation_id text primary key,
    signal_id text not null references signals(signal_id) on delete cascade,
    checked_at_ms integer not null,
    verdict text not null check(verdict in ('ENTER','WAIT','CANCEL')),
    reasons_json text not null,
    snapshot_json text not null,
    gate_version text not null
);
create index if not exists idx_entry_revalidation_signal_time
on entry_revalidations(signal_id, checked_at_ms desc);
create index if not exists idx_entry_revalidation_verdict_time
on entry_revalidations(verdict, checked_at_ms desc);
"""

POSTGRES_SCHEMA = """
create table if not exists entry_revalidations (
    revalidation_id text primary key,
    signal_id text not null references signals(signal_id) on delete cascade,
    checked_at_ms bigint not null,
    verdict text not null check(verdict in ('ENTER','WAIT','CANCEL')),
    reasons_json text not null,
    snapshot_json text not null,
    gate_version text not null
);
create index if not exists idx_entry_revalidation_signal_time
on entry_revalidations(signal_id, checked_at_ms desc);
create index if not exists idx_entry_revalidation_verdict_time
on entry_revalidations(verdict, checked_at_ms desc);
"""


def _initialize_store() -> None:
    initialize_database()
    backend = persistence_backend()
    key = (
        ("sqlite", str(database_path().resolve()))
        if backend == "sqlite"
        else ("postgres", "primary")
    )
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


def _max_signal_age_ms() -> int:
    seconds = max(
        30.0,
        min(float(os.environ.get("STAGE11C_MAX_SIGNAL_AGE_SECONDS", "180")), 900.0),
    )
    return int(seconds * 1000)


def _max_approval_age_ms() -> int:
    seconds = max(
        10.0,
        min(float(os.environ.get("STAGE11C_MAX_APPROVAL_AGE_SECONDS", "120")), 600.0),
    )
    return int(seconds * 1000)


def fill_max_age_ms() -> int:
    seconds = max(
        5.0,
        min(float(os.environ.get("STAGE11C_FILL_MAX_AGE_SECONDS", "30")), 120.0),
    )
    return int(seconds * 1000)


def _max_chase_pct() -> float:
    return max(
        0.10,
        min(float(os.environ.get("STAGE11C_MAX_CHASE_PCT", "0.75")), 5.0),
    )


def _max_adverse_pct() -> float:
    return max(
        0.10,
        min(float(os.environ.get("STAGE11C_MAX_ADVERSE_PCT", "0.75")), 5.0),
    )


def _ret1_threshold_pct() -> float:
    return max(
        0.0,
        min(float(os.environ.get("STAGE11C_RET1_THRESHOLD_PCT", "0.01")), 1.0),
    )


def _ret3_threshold_pct() -> float:
    return max(
        0.0,
        min(float(os.environ.get("STAGE11C_RET3_THRESHOLD_PCT", "0.03")), 2.0),
    )


def _taker_buy_threshold() -> float:
    return max(
        0.50,
        min(float(os.environ.get("STAGE11C_TAKER_BUY_SHARE", "0.55")), 0.90),
    )


def _taker_sell_threshold() -> float:
    return min(
        0.50,
        max(float(os.environ.get("STAGE11C_TAKER_SELL_SHARE", "0.45")), 0.10),
    )


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _closed_rows(rows: Iterable[list[Any]], now_ms: int) -> list[list[Any]]:
    return [
        row
        for row in rows
        if isinstance(row, list)
        and len(row) > 10
        and int(row[6]) < now_ms
    ]


def _taker_share(row: list[Any]) -> float:
    total = max(0.0, _f(row[7]))
    buy = min(total, max(0.0, _f(row[10])))
    return buy / total if total > 0 else 0.5


def _soft_chase_pct() -> float:
    return max(
        0.10,
        min(float(os.environ.get("STAGE11C_SOFT_CHASE_PCT", "0.50")), _max_chase_pct()),
    )


def _oi_min_change_pct() -> float:
    return max(
        0.0,
        min(float(os.environ.get("STAGE11C_OI_MIN_CHANGE_PCT", "0.05")), 5.0),
    )


def _impulse_concentration_ratio() -> float:
    return max(
        0.50,
        min(float(os.environ.get("STAGE11C_IMPULSE_CONCENTRATION_RATIO", "0.80")), 1.50),
    )


def _impulse_ret1_min_pct() -> float:
    return max(
        0.05,
        min(float(os.environ.get("STAGE11C_IMPULSE_RET1_MIN_PCT", "0.20")), 2.0),
    )


def _decision_reasons(candidate: dict[str, Any]) -> list[str]:
    raw = candidate.get("decision_reasons_json")
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        parsed = json.loads(raw or "[]")
        return [str(x) for x in parsed] if isinstance(parsed, list) else []
    except Exception:
        return []


def _fresh_oi_change_pct(
    oi_hist: Iterable[dict[str, Any]] | None,
    now_ms: int,
) -> float | None:
    rows: list[tuple[int, float]] = []
    for item in oi_hist or []:
        try:
            ts = int(item.get("timestamp") or 0)
            oi = float(item.get("sumOpenInterest"))
        except (TypeError, ValueError):
            continue
        if ts <= now_ms and oi > 0:
            rows.append((ts, oi))
    rows.sort()
    if len(rows) < 2:
        return None
    first = rows[-2][1]
    last = rows[-1][1]
    if first <= 0:
        return None
    return 100.0 * (last / first - 1.0)


def _positioning_family(
    candidate: dict[str, Any],
    *,
    oi_hist: Iterable[dict[str, Any]] | None,
    now_ms: int,
    side_ret3: float,
) -> tuple[str, dict[str, Any]]:
    change = _fresh_oi_change_pct(oi_hist, now_ms)
    source = "fresh_5m_oi"
    threshold = _oi_min_change_pct()

    if change is not None:
        if abs(change) < threshold:
            return "NEUTRAL", {
                "source": source,
                "oi_change_pct": change,
                "threshold_pct": threshold,
                "interpretation": "oi_change_below_floor",
            }
        if change > 0:
            if side_ret3 >= _ret3_threshold_pct():
                status = "ALIGNED"
                interpretation = "fresh_positioning_with_proposed_move"
            elif side_ret3 <= -_ret3_threshold_pct():
                status = "OPPOSITE"
                interpretation = "fresh_positioning_against_proposed_move"
            else:
                status = "NEUTRAL"
                interpretation = "fresh_oi_without_directional_price_confirmation"
        else:
            if side_ret3 >= _ret3_threshold_pct():
                status = "SUPPORTIVE"
                interpretation = "position_unwind_supporting_proposed_move"
            elif side_ret3 <= -_ret3_threshold_pct():
                status = "OPPOSITE"
                interpretation = "proposed_side_liquidation_or_unwind"
            else:
                status = "NEUTRAL"
                interpretation = "oi_unwind_without_directional_price_confirmation"
        return status, {
            "source": source,
            "oi_change_pct": change,
            "threshold_pct": threshold,
            "interpretation": interpretation,
        }

    reasons = _decision_reasons(candidate)
    side = str(candidate.get("side") or "").upper()
    side_word = "long" if side == "LONG" else "short"
    opposite_word = "short" if side == "LONG" else "long"
    if any(f"confirm:oi_fresh_{side_word}" in reason for reason in reasons):
        return "ALIGNED", {
            "source": "signal_context_fallback",
            "oi_change_pct": candidate.get("raw_oi_change_pct"),
            "interpretation": f"signal_confirm_oi_fresh_{side_word}",
        }
    if any(f"confirm:oi_fresh_{opposite_word}" in reason for reason in reasons):
        return "OPPOSITE", {
            "source": "signal_context_fallback",
            "oi_change_pct": candidate.get("raw_oi_change_pct"),
            "interpretation": f"signal_confirm_oi_fresh_{opposite_word}",
        }
    supportive = (
        (side == "LONG" and any("oi_short_covering" in reason for reason in reasons))
        or (side == "SHORT" and any("oi_long_liquidation" in reason for reason in reasons))
    )
    if supportive:
        return "SUPPORTIVE", {
            "source": "signal_context_fallback",
            "oi_change_pct": candidate.get("raw_oi_change_pct"),
            "interpretation": "signal_position_unwind_supportive",
        }
    return "NEUTRAL", {
        "source": "signal_context_fallback",
        "oi_change_pct": candidate.get("raw_oi_change_pct"),
        "interpretation": "no_directional_positioning_confirmation",
    }


def _regime_family(candidate: dict[str, Any]) -> str:
    side = str(candidate.get("side") or "").upper()
    regime = str(candidate.get("market_regime") or "").upper()
    if regime == "SIDEWAYS" or not regime:
        return "NEUTRAL"
    if (side == "LONG" and regime == "BULL") or (side == "SHORT" and regime == "BEAR"):
        return "ALIGNED"
    if (side == "LONG" and regime == "BEAR") or (side == "SHORT" and regime == "BULL"):
        return "OPPOSITE"
    return "NEUTRAL"


def evaluate_fresh_entry(
    candidate: dict[str, Any],
    *,
    current_price: float,
    klines_1m: Iterable[list[Any]],
    now_ms: int,
    oi_hist: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Stage 11C V2: normalize correlated evidence into independent families."""
    side = str(candidate.get("side") or "").upper()
    signal_price = _f(candidate.get("signal_price"), -1.0)
    signal_time_ms = int(candidate.get("signal_time_ms") or 0)
    approval_ms = int(candidate.get("reviewed_at_ms") or 0)
    rows = _closed_rows(klines_1m, now_ms)

    reasons: list[str] = []
    snapshot: dict[str, Any] = {
        "symbol": str(candidate.get("symbol") or "").upper(),
        "side": side,
        "signal_price": signal_price if signal_price > 0 else None,
        "current_price": current_price,
        "signal_time_ms": signal_time_ms,
        "approval_reviewed_at_ms": approval_ms,
        "closed_1m_count": len(rows),
        "stage": str(candidate.get("stage") or "").upper(),
        "signal_structure_status": str(candidate.get("structure_status") or "").upper(),
        "signal_market_regime": str(candidate.get("market_regime") or "").upper(),
    }

    if side not in {"LONG", "SHORT"}:
        return {"verdict": "CANCEL", "reasons": ["invalid_side"], "snapshot": snapshot, "version": STAGE11C_VERSION}
    if signal_price <= 0 or current_price <= 0:
        return {"verdict": "CANCEL", "reasons": ["invalid_price"], "snapshot": snapshot, "version": STAGE11C_VERSION}

    signal_age_ms = now_ms - signal_time_ms if signal_time_ms > 0 else 10**18
    approval_age_ms = now_ms - approval_ms if approval_ms > 0 else 10**18
    snapshot["signal_age_ms"] = signal_age_ms
    snapshot["approval_age_ms"] = approval_age_ms
    if signal_time_ms <= 0 or signal_age_ms > _max_signal_age_ms():
        reasons.append("signal_stale")
    if approval_ms <= 0 or approval_age_ms > _max_approval_age_ms():
        reasons.append("approval_stale")
    if reasons:
        return {"verdict": "CANCEL", "reasons": reasons, "snapshot": snapshot, "version": STAGE11C_VERSION}

    drift_pct = 100.0 * (current_price / signal_price - 1.0)
    side_drift_pct = drift_pct if side == "LONG" else -drift_pct
    snapshot["price_drift_pct"] = drift_pct
    snapshot["side_adjusted_drift_pct"] = side_drift_pct
    if side_drift_pct >= _max_chase_pct():
        return {"verdict": "CANCEL", "reasons": ["price_chased_too_far"], "snapshot": snapshot, "version": STAGE11C_VERSION}

    if len(rows) < 4:
        return {"verdict": "WAIT", "reasons": ["insufficient_closed_1m_bars"], "snapshot": snapshot, "version": STAGE11C_VERSION}

    latest = rows[-1]
    prev = rows[-2]
    base3 = rows[-4]
    latest_close = _f(latest[4])
    prev_close = _f(prev[4])
    base3_close = _f(base3[4])
    if min(latest_close, prev_close, base3_close) <= 0:
        return {"verdict": "WAIT", "reasons": ["invalid_1m_close"], "snapshot": snapshot, "version": STAGE11C_VERSION}

    ret1_pct = 100.0 * (latest_close / prev_close - 1.0)
    ret3_pct = 100.0 * (latest_close / base3_close - 1.0)
    side_ret1 = ret1_pct if side == "LONG" else -ret1_pct
    side_ret3 = ret3_pct if side == "LONG" else -ret3_pct
    taker_buy_share = _taker_share(latest)

    prior3 = rows[-4:-1]
    prior_high = max(_f(row[2]) for row in prior3)
    prior_low = min(_f(row[3]) for row in prior3)
    if side == "LONG":
        opposite_structure = latest_close < prior_low
        aligned_micro_structure = latest_close > prior_high
        taker_aligned = taker_buy_share >= _taker_buy_threshold()
        taker_opposite = taker_buy_share <= _taker_sell_threshold()
    else:
        opposite_structure = latest_close > prior_high
        aligned_micro_structure = latest_close < prior_low
        taker_aligned = taker_buy_share <= _taker_sell_threshold()
        taker_opposite = taker_buy_share >= _taker_buy_threshold()

    ret1_aligned = side_ret1 >= _ret1_threshold_pct()
    ret1_opposite = side_ret1 <= -_ret1_threshold_pct()
    ret3_aligned = side_ret3 >= _ret3_threshold_pct()
    ret3_opposite = side_ret3 <= -_ret3_threshold_pct()

    price_family = (
        "OPPOSITE"
        if opposite_structure or ret3_opposite
        else "ALIGNED"
        if ret3_aligned
        else "NEUTRAL"
    )
    flow_family = "ALIGNED" if taker_aligned else "OPPOSITE" if taker_opposite else "NEUTRAL"
    positioning_family, positioning_detail = _positioning_family(
        candidate,
        oi_hist=oi_hist,
        now_ms=now_ms,
        side_ret3=side_ret3,
    )
    regime_family = _regime_family(candidate)

    impulse_ratio = (
        abs(side_ret1) / max(abs(side_ret3), 1e-9)
        if abs(side_ret3) >= _ret3_threshold_pct()
        else 0.0
    )
    concentrated_impulse = (
        side_ret1 >= _impulse_ret1_min_pct()
        and impulse_ratio >= _impulse_concentration_ratio()
    )
    soft_chase = side_drift_pct >= _soft_chase_pct()

    families = {
        "PRICE_STRUCTURE": price_family,
        "FLOW": flow_family,
        "POSITIONING": positioning_family,
        "REGIME": regime_family,
    }
    aligned_count = sum(status == "ALIGNED" for status in families.values())
    opposing_count = sum(status == "OPPOSITE" for status in families.values())
    near_entry_support = (
        flow_family == "ALIGNED"
        or positioning_family in {"ALIGNED", "SUPPORTIVE"}
    )

    snapshot.update(
        {
            "latest_closed_1m_close": latest_close,
            "ret_1m_pct": ret1_pct,
            "ret_3m_pct": ret3_pct,
            "side_ret_1m_pct": side_ret1,
            "side_ret_3m_pct": side_ret3,
            "taker_buy_share_1m": taker_buy_share,
            "prior_3m_high": prior_high,
            "prior_3m_low": prior_low,
            "opposite_micro_structure": opposite_structure,
            "aligned_micro_structure": aligned_micro_structure,
            "ret1_aligned": ret1_aligned,
            "ret3_aligned": ret3_aligned,
            "ret1_opposite": ret1_opposite,
            "ret3_opposite": ret3_opposite,
            "taker_aligned": taker_aligned,
            "taker_opposite": taker_opposite,
            "evidence_families": families,
            "aligned_family_count": aligned_count,
            "opposing_family_count": opposing_count,
            "positioning_detail": positioning_detail,
            "near_entry_support": near_entry_support,
            "soft_chase": soft_chase,
            "soft_chase_threshold_pct": _soft_chase_pct(),
            "impulse_concentration_ratio": impulse_ratio,
            "concentrated_impulse": concentrated_impulse,
        }
    )

    # Hard reversal evidence from the price family remains fail-closed.
    if price_family == "OPPOSITE":
        cancel_reasons = ["family:price_structure_opposite"]
        if opposite_structure:
            cancel_reasons.append("opposite_micro_structure")
        if ret3_opposite:
            cancel_reasons.append("ret3_opposite")
        return {"verdict": "CANCEL", "reasons": cancel_reasons, "snapshot": snapshot, "version": STAGE11C_VERSION}

    # Two independent near-entry contradictions are enough to invalidate the setup.
    if flow_family == "OPPOSITE" and positioning_family == "OPPOSITE":
        return {
            "verdict": "CANCEL",
            "reasons": ["family:flow_opposite", "family:positioning_opposite"],
            "snapshot": snapshot,
            "version": STAGE11C_VERSION,
        }

    if side_drift_pct <= -_max_adverse_pct() and price_family != "ALIGNED":
        return {
            "verdict": "CANCEL",
            "reasons": ["adverse_drift_too_far", "family:price_structure_not_aligned"],
            "snapshot": snapshot,
            "version": STAGE11C_VERSION,
        }

    if price_family != "ALIGNED":
        return {
            "verdict": "WAIT",
            "reasons": ["family:price_structure_not_aligned"],
            "snapshot": snapshot,
            "version": STAGE11C_VERSION,
        }

    # Regime is a modifier only. It can never qualify a trade by itself.
    if not near_entry_support:
        return {
            "verdict": "WAIT",
            "reasons": ["independent_near_entry_support_missing"],
            "snapshot": snapshot,
            "version": STAGE11C_VERSION,
        }

    # A live price that has already run > soft chase requires BOTH independent
    # near-entry families to be fresh and aligned. This prevents momentum/chase
    # from being counted as multiple confirmations.
    if soft_chase and not (
        flow_family == "ALIGNED" and positioning_family == "ALIGNED"
    ):
        return {
            "verdict": "WAIT",
            "reasons": ["soft_chase_requires_flow_and_positioning"],
            "snapshot": snapshot,
            "version": STAGE11C_VERSION,
        }

    # If most of the 3m move is concentrated in the latest 1m, treat it as one
    # impulse, not two independent momentum confirmations.
    if concentrated_impulse and not (
        flow_family == "ALIGNED" and positioning_family == "ALIGNED"
    ):
        return {
            "verdict": "WAIT",
            "reasons": ["concentrated_impulse_requires_independent_support"],
            "snapshot": snapshot,
            "version": STAGE11C_VERSION,
        }

    enter_reasons = [
        "family:price_structure_aligned",
        f"family:flow_{flow_family.lower()}",
        f"family:positioning_{positioning_family.lower()}",
        f"family:regime_{regime_family.lower()}",
    ]
    if regime_family == "OPPOSITE":
        enter_reasons.append("counter_regime_entry")
    if positioning_family == "SUPPORTIVE":
        enter_reasons.append("positioning_unwind_supportive_not_fresh")
    return {
        "verdict": "ENTER",
        "reasons": enter_reasons,
        "snapshot": snapshot,
        "version": STAGE11C_VERSION,
    }


def save_revalidation(
    *,
    signal_id: str,
    checked_at_ms: int,
    verdict: str,
    reasons: list[str],
    snapshot: dict[str, Any],
) -> str:
    _initialize_store()
    revalidation_id = f"{signal_id}:{checked_at_ms}"
    reasons_json = json.dumps(reasons, separators=(",", ":"), allow_nan=False)
    snapshot_json = json.dumps(snapshot, separators=(",", ":"), allow_nan=False)
    values = (
        revalidation_id,
        signal_id,
        checked_at_ms,
        verdict,
        reasons_json,
        snapshot_json,
        STAGE11C_VERSION,
    )

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            conn.execute(
                """
                insert or replace into entry_revalidations (
                    revalidation_id, signal_id, checked_at_ms, verdict,
                    reasons_json, snapshot_json, gate_version
                ) values (?,?,?,?,?,?,?)
                """,
                values,
            )
    else:
        with _postgres_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into entry_revalidations (
                        revalidation_id, signal_id, checked_at_ms, verdict,
                        reasons_json, snapshot_json, gate_version
                    ) values (%s,%s,%s,%s,%s,%s,%s)
                    on conflict(revalidation_id) do update set
                        verdict=excluded.verdict,
                        reasons_json=excluded.reasons_json,
                        snapshot_json=excluded.snapshot_json,
                        gate_version=excluded.gate_version
                    """,
                    values,
                )
    return revalidation_id


def list_revalidations(
    *,
    signal_id: str | None = None,
    verdict: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    _initialize_store()
    safe_limit = max(1, min(int(limit), 1000))
    verdict_clean = str(verdict or "").upper() or None

    where: list[str] = []
    params: list[Any] = []
    if signal_id:
        where.append("signal_id=?")
        params.append(signal_id)
    if verdict_clean:
        where.append("verdict=?")
        params.append(verdict_clean)

    clause = (" where " + " and ".join(where)) if where else ""
    query = (
        "select * from entry_revalidations"
        + clause
        + " order by checked_at_ms desc limit ?"
    )
    params.append(safe_limit)

    if persistence_backend() == "sqlite":
        with _sqlite_connect(database_path()) as conn:
            rows = conn.execute(query, params).fetchall()
            out = [dict(row) for row in rows]
    else:
        with _postgres_connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query.replace("?", "%s"), params)
                out = [dict(row) for row in cur.fetchall()]

    for row in out:
        try:
            row["reasons"] = json.loads(row.pop("reasons_json") or "[]")
        except Exception:
            row["reasons"] = []
        try:
            row["snapshot"] = json.loads(row.pop("snapshot_json") or "{}")
        except Exception:
            row["snapshot"] = {}
    return out


def check_fresh_entry(
    client: Any,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    signal_id = str(candidate["signal_id"])
    started_at_ms = int(time.time() * 1000)
    update_entry_latency(
        signal_id,
        stage11c_started_at_ms=started_at_ms,
    )

    try:
        symbol = str(candidate["symbol"]).upper()
        with ThreadPoolExecutor(max_workers=3) as pool:
            kline_future = pool.submit(client.klines, symbol=symbol, interval="1m", limit=8)
            price_future = pool.submit(client.ticker_price, symbol)
            oi_future = pool.submit(client.open_interest_hist, symbol, "5m", 3)
            rows = kline_future.result()
            current_price = float(price_future.result())
            try:
                oi_hist = oi_future.result()
            except Exception:
                oi_hist = None
        checked_at_ms = int(time.time() * 1000)
        result = evaluate_fresh_entry(
            candidate,
            current_price=current_price,
            klines_1m=rows,
            now_ms=checked_at_ms,
            oi_hist=oi_hist,
        )
    except Exception as exc:
        checked_at_ms = int(time.time() * 1000)
        result = {
            "verdict": "WAIT",
            "reasons": [f"fresh_market_fetch_failed:{type(exc).__name__}"],
            "snapshot": {
                "symbol": str(candidate.get("symbol") or "").upper(),
                "side": str(candidate.get("side") or "").upper(),
                "error": str(exc)[:300],
            },
            "version": STAGE11C_VERSION,
        }

    result["checked_at_ms"] = checked_at_ms
    result["latency_ms"] = max(0, checked_at_ms - started_at_ms)
    save_revalidation(
        signal_id=signal_id,
        checked_at_ms=checked_at_ms,
        verdict=result["verdict"],
        reasons=list(result.get("reasons") or []),
        snapshot=dict(result.get("snapshot") or {}),
    )
    update_entry_latency(
        signal_id,
        stage11c_finished_at_ms=checked_at_ms,
    )
    return result
