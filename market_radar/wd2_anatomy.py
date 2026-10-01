from __future__ import annotations

import bisect
import json
import math
import statistics
from collections import Counter, defaultdict
from typing import Any

import psycopg2.extras

from .persistence import _postgres_connect


WD2_VERSION = "wd2-entry-horizon-anatomy-v1"
WD2_CUTOFF_MS = 1790826404280
WD2_LABEL_VERSION = "wd1-outcome-taxonomy-v1"

WRONG = "TRUE_WRONG_DIRECTION"
RECOVERED = "RECOVERED_DRAWDOWN"
STALL = "STALL_NO_EDGE"
FAILURE = "RIGHT_THEN_FAILURE"
RUNNER = "CORRECT_RUNNER"
LABELS = (WRONG, RECOVERED, STALL, FAILURE, RUNNER)
HORIZONS_MIN = (1, 3, 5, 10, 20, 30)


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _j(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        obj = json.loads(value or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def probability_b_greater_than_a(
    a: list[float],
    b: list[float],
) -> float | None:
    """Mann-Whitney probability P(B>A)+0.5*P(B=A)."""
    if not a or not b:
        return None
    aa = sorted(a)
    wins = 0.0
    for value in b:
        left = bisect.bisect_left(aa, value)
        right = bisect.bisect_right(aa, value)
        wins += left + 0.5 * (right - left)
    return wins / (len(a) * len(b))


def _entry_rows() -> list[dict[str, Any]]:
    query = """
        select
            w.position_id, w.signal_id, w.outcome_label,
            w.symbol, w.side, w.opened_at_ms, w.closed_at_ms,
            s.signal_time_ms, s.stage, s.long_score, s.short_score,
            s.score_edge, s.volume_ratio, s.structure_status,
            s.taker_bias, s.raw_oi_change_pct, s.funding_rate,
            s.market_regime, s.decision_context_balance,
            s.snapshot_json as signal_snapshot_json,
            e.candle_close_at_ms, e.signal_created_at_ms,
            e.ai_queued_at_ms, e.ai_started_at_ms, e.ai_finished_at_ms,
            e.stage11c_started_at_ms, e.stage11c_finished_at_ms,
            e.order_created_at_ms, e.position_opened_at_ms,
            r.checked_at_ms as gate_checked_at_ms,
            r.reasons_json as gate_reasons_json,
            r.snapshot_json as gate_snapshot_json
        from wd1_trade_labels w
        join signals s on s.signal_id=w.signal_id
        left join entry_latency e on e.signal_id=w.signal_id
        left join lateral (
            select checked_at_ms, reasons_json, snapshot_json
            from entry_revalidations x
            where x.signal_id=w.signal_id
              and x.verdict='ENTER'
              and x.checked_at_ms <= w.opened_at_ms
            order by x.checked_at_ms desc
            limit 1
        ) r on true
        where w.label_version=%s
          and w.closed_at_ms <= %s
        order by w.opened_at_ms, w.position_id
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_LABEL_VERSION, WD2_CUTOFF_MS))
            return [dict(row) for row in cur.fetchall()]


def _num_delta(a: int | None, b: int | None, scale: float = 1.0) -> float | None:
    if a is None or b is None:
        return None
    return (int(a) - int(b)) / scale


def build_entry_features(row: dict[str, Any]) -> tuple[dict[str, float | None], dict[str, str]]:
    side = str(row.get("side") or "").upper()
    sign = 1.0 if side == "LONG" else -1.0
    sig = _j(row.get("signal_snapshot_json"))
    gate = _j(row.get("gate_snapshot_json"))
    families = gate.get("evidence_families") or {}
    if not isinstance(families, dict):
        families = {}
    positioning = gate.get("positioning_detail") or {}
    if not isinstance(positioning, dict):
        positioning = {}

    selected_score = _f(row.get("long_score") if side == "LONG" else row.get("short_score"))
    opposite_score = _f(row.get("short_score") if side == "LONG" else row.get("long_score"))

    confirmations = sig.get("decision_context_confirmations") or []
    conflicts = sig.get("decision_context_conflicts") or []
    if not isinstance(confirmations, list):
        confirmations = []
    if not isinstance(conflicts, list):
        conflicts = []

    buy_share = _f(gate.get("taker_buy_share_1m"))
    taker_for_side = (
        buy_share if side == "LONG"
        else (1.0 - buy_share if buy_share is not None else None)
    )

    numeric: dict[str, float | None] = {
        "selected_score": selected_score,
        "opposite_score": opposite_score,
        "score_edge": _f(row.get("score_edge")),
        "volume_ratio": _f(row.get("volume_ratio")),
        "raw_oi_change_pct": _f(row.get("raw_oi_change_pct")),
        "funding_rate": _f(row.get("funding_rate")),
        "decision_context_balance": _f(row.get("decision_context_balance")),
        "context_confirmation_count": float(len(confirmations)),
        "context_conflict_count": float(len(conflicts)),
        "signal_side_ret_5m_pct": (_f(sig.get("ret_5m_pct")) or 0.0) * sign if _f(sig.get("ret_5m_pct")) is not None else None,
        "signal_side_ret_15m_pct": (_f(sig.get("ret_15m_pct")) or 0.0) * sign if _f(sig.get("ret_15m_pct")) is not None else None,
        "signal_side_ret_1h_pct": (_f(sig.get("ret_1h_pct")) or 0.0) * sign if _f(sig.get("ret_1h_pct")) is not None else None,
        "return_expansion_ratio": _f(sig.get("return_expansion_ratio")),
        "range_ratio": _f(sig.get("range_ratio")),
        "trades_ratio": _f(sig.get("trades_ratio")),
        "median_abs_ret_5m_pct": _f(sig.get("median_abs_ret_5m_pct")),
        "gate_side_ret_1m_pct": _f(gate.get("side_ret_1m_pct")),
        "gate_side_ret_3m_pct": _f(gate.get("side_ret_3m_pct")),
        "gate_side_adjusted_drift_pct": _f(gate.get("side_adjusted_drift_pct")),
        "gate_taker_share_for_side": taker_for_side,
        "gate_positioning_oi_change_pct": _f(positioning.get("oi_change_pct")),
        "gate_aligned_family_count": _f(gate.get("aligned_family_count")),
        "gate_opposing_family_count": _f(gate.get("opposing_family_count")),
        "gate_impulse_concentration_ratio": _f(gate.get("impulse_concentration_ratio")),
        "signal_age_s": (_f(gate.get("signal_age_ms")) / 1000.0) if _f(gate.get("signal_age_ms")) is not None else None,
        "approval_age_s": (_f(gate.get("approval_age_ms")) / 1000.0) if _f(gate.get("approval_age_ms")) is not None else None,
        "candle_to_fill_s": _num_delta(row.get("opened_at_ms"), row.get("candle_close_at_ms"), 1000.0),
        "signal_created_to_fill_s": _num_delta(row.get("opened_at_ms"), row.get("signal_created_at_ms"), 1000.0),
        "ai_latency_s": _num_delta(row.get("ai_finished_at_ms"), row.get("ai_started_at_ms"), 1000.0),
        "stage11c_latency_s": _num_delta(row.get("stage11c_finished_at_ms"), row.get("stage11c_started_at_ms"), 1000.0),
        "gate_to_fill_s": _num_delta(row.get("opened_at_ms"), row.get("gate_checked_at_ms"), 1000.0),
    }

    family_combo = "|".join(
        str(families.get(name) or "MISSING").upper()
        for name in ("PRICE_STRUCTURE", "FLOW", "POSITIONING", "REGIME")
    )
    categorical = {
        "side": side,
        "stage": str(row.get("stage") or "MISSING").upper(),
        "signal_structure_status": str(row.get("structure_status") or "MISSING").upper(),
        "signal_taker_bias": str(row.get("taker_bias") or "MISSING").upper(),
        "signal_market_regime": str(row.get("market_regime") or "MISSING").upper(),
        "movement_state": str(sig.get("movement_state") or "MISSING").upper(),
        "directional_persistence": str(sig.get("directional_persistence") or "MISSING").upper(),
        "price_family": str(families.get("PRICE_STRUCTURE") or "MISSING").upper(),
        "flow_family": str(families.get("FLOW") or "MISSING").upper(),
        "positioning_family": str(families.get("POSITIONING") or "MISSING").upper(),
        "regime_family": str(families.get("REGIME") or "MISSING").upper(),
        "family_combo": family_combo,
        "gate_near_entry_support": str(bool(gate.get("near_entry_support"))).upper(),
        "gate_soft_chase": str(bool(gate.get("soft_chase"))).upper(),
        "gate_concentrated_impulse": str(bool(gate.get("concentrated_impulse"))).upper(),
        "gate_taker_aligned": str(bool(gate.get("taker_aligned"))).upper(),
        "gate_taker_opposite": str(bool(gate.get("taker_opposite"))).upper(),
    }
    return numeric, categorical


def numeric_entry_anatomy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_label: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    all_features: set[str] = set()
    for row in rows:
        numeric, _ = build_entry_features(row)
        label = str(row["outcome_label"])
        for feature, value in numeric.items():
            all_features.add(feature)
            if value is not None:
                by_label[label][feature].append(float(value))

    summaries: dict[str, Any] = {}
    pairwise: dict[str, list[dict[str, Any]]] = {}
    for feature in sorted(all_features):
        summaries[feature] = {}
        for label in LABELS:
            values = by_label[label].get(feature, [])
            summaries[feature][label] = {
                "n": len(values),
                "median": _median(values),
                "q25": _quantile(values, 0.25),
                "q75": _quantile(values, 0.75),
            }

    for comparator in (RECOVERED, RUNNER):
        ranked: list[dict[str, Any]] = []
        for feature in sorted(all_features):
            a = by_label[WRONG].get(feature, [])
            b = by_label[comparator].get(feature, [])
            if len(a) < 30 or len(b) < 30:
                continue
            auc = probability_b_greater_than_a(a, b)
            if auc is None:
                continue
            wrong_med = _median(a)
            comp_med = _median(b)
            ranked.append({
                "feature": feature,
                "wrong_n": len(a),
                "comparator_n": len(b),
                "wrong_median": wrong_med,
                "comparator_median": comp_med,
                "median_delta_comparator_minus_wrong": (
                    None if wrong_med is None or comp_med is None
                    else comp_med - wrong_med
                ),
                "prob_comparator_greater": auc,
                "separation_0_to_1": abs(auc - 0.5) * 2.0,
            })
        ranked.sort(key=lambda row: row["separation_0_to_1"], reverse=True)
        pairwise[f"{WRONG}_VS_{comparator}"] = ranked
    return {"summary": summaries, "pairwise_ranked": pairwise}


def categorical_entry_anatomy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    feature_counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    label_n = Counter(str(row["outcome_label"]) for row in rows)
    for row in rows:
        _, categorical = build_entry_features(row)
        label = str(row["outcome_label"])
        for feature, value in categorical.items():
            feature_counts[feature][label][value] += 1

    prevalence: dict[str, Any] = {}
    pairwise: dict[str, list[dict[str, Any]]] = {}
    for feature, labels in feature_counts.items():
        values = sorted({value for counter in labels.values() for value in counter})
        prevalence[feature] = {}
        for value in values:
            prevalence[feature][value] = {
                label: {
                    "n": labels[label][value],
                    "rate_pct": (
                        100.0 * labels[label][value] / label_n[label]
                        if label_n[label] else None
                    ),
                }
                for label in LABELS
            }

    for comparator in (RECOVERED, RUNNER):
        ranked: list[dict[str, Any]] = []
        for feature, labels in feature_counts.items():
            values = {value for counter in labels.values() for value in counter}
            for value in values:
                wrong_count = labels[WRONG][value]
                comp_count = labels[comparator][value]
                wrong_rate = 100.0 * wrong_count / label_n[WRONG] if label_n[WRONG] else 0.0
                comp_rate = 100.0 * comp_count / label_n[comparator] if label_n[comparator] else 0.0
                if wrong_count + comp_count < 30:
                    continue
                ranked.append({
                    "feature": feature,
                    "value": value,
                    "wrong_n": wrong_count,
                    "comparator_n": comp_count,
                    "wrong_rate_pct": wrong_rate,
                    "comparator_rate_pct": comp_rate,
                    "delta_pp_comparator_minus_wrong": comp_rate - wrong_rate,
                    "abs_delta_pp": abs(comp_rate - wrong_rate),
                })
        ranked.sort(key=lambda row: row["abs_delta_pp"], reverse=True)
        pairwise[f"{WRONG}_VS_{comparator}"] = ranked
    return {
        "label_counts": dict(label_n),
        "prevalence": prevalence,
        "pairwise_ranked": pairwise,
    }


def segment_outcomes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    segments: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        _, cat = build_entry_features(row)
        label = str(row["outcome_label"])
        keys = {
            f"side={cat['side']}": label,
            f"stage={cat['stage']}": label,
            f"side={cat['side']}|stage={cat['stage']}": label,
            f"family={cat['family_combo']}": label,
            f"side={cat['side']}|family={cat['family_combo']}": label,
        }
        for segment in keys:
            segments[segment][label] += 1

    out: list[dict[str, Any]] = []
    for segment, counts in segments.items():
        n = sum(counts.values())
        if n < 30:
            continue
        out.append({
            "segment": segment,
            "n": n,
            "wrong_n": counts[WRONG],
            "wrong_rate_pct": 100.0 * counts[WRONG] / n,
            "recovered_n": counts[RECOVERED],
            "recovered_rate_pct": 100.0 * counts[RECOVERED] / n,
            "runner_n": counts[RUNNER],
            "runner_rate_pct": 100.0 * counts[RUNNER] / n,
            "right_then_failure_n": counts[FAILURE],
            "stall_n": counts[STALL],
        })
    out.sort(key=lambda row: (row["wrong_rate_pct"], row["n"]), reverse=True)
    return {
        "highest_wrong_rate": out[:40],
        "largest_segments": sorted(out, key=lambda row: row["n"], reverse=True)[:40],
    }


def _evaluation_rows() -> list[dict[str, Any]]:
    query = """
        select
            w.position_id, w.outcome_label, w.side,
            w.opened_at_ms, w.closed_at_ms,
            p.evaluated_at_ms, p.unrealized_pnl_pct,
            p.mfe_pct, p.mae_pct, p.contradictions_json,
            p.snapshot_json
        from wd1_trade_labels w
        join position_evaluations p on p.position_id=w.position_id
        where w.label_version=%s
          and w.closed_at_ms <= %s
          and p.evaluated_at_ms >= w.opened_at_ms
          and p.evaluated_at_ms <= w.closed_at_ms
        order by w.position_id, p.evaluated_at_ms
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_LABEL_VERSION, WD2_CUTOFF_MS))
            return [dict(row) for row in cur.fetchall()]


def build_horizon_anatomy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meta: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = str(row["position_id"])
        grouped[pid].append(row)
        meta[pid] = {
            "label": str(row["outcome_label"]),
            "side": str(row["side"]).upper(),
            "opened_at_ms": int(row["opened_at_ms"]),
        }

    label_total = Counter(info["label"] for info in meta.values())
    result: dict[str, Any] = {}
    for horizon in HORIZONS_MIN:
        target_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for pid, evals in grouped.items():
            opened = meta[pid]["opened_at_ms"]
            cutoff = opened + horizon * 60_000
            candidates = [row for row in evals if int(row["evaluated_at_ms"]) <= cutoff]
            if not candidates:
                continue
            chosen = candidates[-1]
            snap = _j(chosen.get("snapshot_json"))
            side = meta[pid]["side"]
            sign = 1.0 if side == "LONG" else -1.0
            contradictions = []
            try:
                contradictions = json.loads(chosen.get("contradictions_json") or "[]")
            except Exception:
                contradictions = []
            if not isinstance(contradictions, list):
                contradictions = []

            taker_bias = str(snap.get("taker_bias") or "").upper()
            taker_opposite = (
                (side == "LONG" and taker_bias == "SELL")
                or (side == "SHORT" and taker_bias == "BUY")
            )
            long_score = _f(snap.get("long_score"))
            short_score = _f(snap.get("short_score"))
            score_edge_for_position = None
            if long_score is not None and short_score is not None:
                score_edge_for_position = (long_score - short_score) * sign

            target_rows[meta[pid]["label"]].append({
                "age_min": (int(chosen["evaluated_at_ms"]) - opened) / 60_000.0,
                "pnl": _f(chosen.get("unrealized_pnl_pct")),
                "mfe": _f(chosen.get("mfe_pct")),
                "mae": _f(chosen.get("mae_pct")),
                "side_ret_5m": (_f(snap.get("ret_5m_pct")) or 0.0) * sign if _f(snap.get("ret_5m_pct")) is not None else None,
                "side_ret_15m": (_f(snap.get("ret_15m_pct")) or 0.0) * sign if _f(snap.get("ret_15m_pct")) is not None else None,
                "score_edge_for_position": score_edge_for_position,
                "taker_opposite": taker_opposite,
                "contradiction_count": float(len(contradictions)),
            })

        horizon_summary: dict[str, Any] = {}
        for label in LABELS:
            items = target_rows.get(label, [])
            def vals(key: str) -> list[float]:
                return [float(x[key]) for x in items if x.get(key) is not None]
            pnls = vals("pnl")
            mfes = vals("mfe")
            maes = vals("mae")
            horizon_summary[label] = {
                "n": len(items),
                "coverage_pct": 100.0 * len(items) / label_total[label] if label_total[label] else None,
                "median_observation_age_min": _median(vals("age_min")),
                "median_pnl_pct": _median(pnls),
                "median_mfe_pct": _median(mfes),
                "median_mae_pct": _median(maes),
                "pnl_positive_rate_pct": 100.0 * sum(v > 0 for v in pnls) / len(pnls) if pnls else None,
                "pnl_le_minus_035_rate_pct": 100.0 * sum(v <= -0.35 for v in pnls) / len(pnls) if pnls else None,
                "mfe_ge_050_rate_pct": 100.0 * sum(v >= 0.50 for v in mfes) / len(mfes) if mfes else None,
                "side_ret5_negative_rate_pct": (
                    100.0 * sum(v < 0 for v in vals("side_ret_5m")) / len(vals("side_ret_5m"))
                    if vals("side_ret_5m") else None
                ),
                "position_score_edge_negative_rate_pct": (
                    100.0 * sum(v < 0 for v in vals("score_edge_for_position")) / len(vals("score_edge_for_position"))
                    if vals("score_edge_for_position") else None
                ),
                "taker_opposite_rate_pct": (
                    100.0 * sum(bool(x["taker_opposite"]) for x in items) / len(items)
                    if items else None
                ),
                "median_contradiction_count": _median(vals("contradiction_count")),
            }
        result[str(horizon)] = horizon_summary
    return result



def _pp_observation_rows() -> list[dict[str, Any]]:
    query = """
        select
            w.position_id, w.outcome_label, w.side,
            w.opened_at_ms, w.closed_at_ms,
            o.evaluated_at_ms, o.current_pnl_pct,
            o.mfe_pct, o.danger_score, o.fast_gate,
            o.snapshot_json
        from wd1_trade_labels w
        join pp_decision_v2_observations o on o.position_id=w.position_id
        where w.label_version=%s
          and w.closed_at_ms <= %s
          and o.evaluated_at_ms >= w.opened_at_ms
          and o.evaluated_at_ms <= w.closed_at_ms
        order by w.position_id, o.evaluated_at_ms
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_LABEL_VERSION, WD2_CUTOFF_MS))
            return [dict(row) for row in cur.fetchall()]


def build_high_res_horizon_anatomy(
    observations: list[dict[str, Any]],
    entry_rows: list[dict[str, Any]],
    tolerance_seconds: float = 45.0,
) -> dict[str, Any]:
    """Exact-near-target horizon lane from the 15s PP observation stream.

    Only observations within +/- tolerance_seconds of the requested horizon
    are accepted. Trades that already closed before a horizon are counted
    separately instead of carrying a stale earlier snapshot forward.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meta: dict[str, dict[str, Any]] = {}
    for row in observations:
        pid = str(row["position_id"])
        grouped[pid].append(row)
        meta[pid] = {
            "label": str(row["outcome_label"]),
            "side": str(row["side"]).upper(),
            "opened_at_ms": int(row["opened_at_ms"]),
            "closed_at_ms": int(row["closed_at_ms"]),
        }

    all_meta = {
        str(row["position_id"]): {
            "label": str(row["outcome_label"]),
            "side": str(row["side"]).upper(),
            "opened_at_ms": int(row["opened_at_ms"]),
            "closed_at_ms": int(row["closed_at_ms"]),
        }
        for row in entry_rows
    }
    full_counts = Counter(info["label"] for info in all_meta.values())
    lane_counts = Counter(info["label"] for info in meta.values())

    result: dict[str, Any] = {
        "tolerance_seconds": tolerance_seconds,
        "lane_coverage": {
            label: {
                "full_n": full_counts[label],
                "observed_lane_n": lane_counts[label],
                "observed_lane_coverage_pct": (
                    100.0 * lane_counts[label] / full_counts[label]
                    if full_counts[label] else None
                ),
            }
            for label in LABELS
        },
        "horizons": {},
    }

    tolerance_ms = int(tolerance_seconds * 1000)
    for horizon in HORIZONS_MIN:
        horizon_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
        alive_counts = Counter()
        closed_before_counts = Counter()

        for pid, info in all_meta.items():
            target = info["opened_at_ms"] + horizon * 60_000
            if info["closed_at_ms"] < target:
                closed_before_counts[info["label"]] += 1
            else:
                alive_counts[info["label"]] += 1

        for pid, evals in grouped.items():
            info = meta[pid]
            target = info["opened_at_ms"] + horizon * 60_000
            if info["closed_at_ms"] < target:
                continue
            chosen = min(
                evals,
                key=lambda row: abs(int(row["evaluated_at_ms"]) - target),
            )
            distance_ms = abs(int(chosen["evaluated_at_ms"]) - target)
            if distance_ms > tolerance_ms:
                continue

            snap = _j(chosen.get("snapshot_json"))
            contradictions = snap.get("contradictions") or []
            if not isinstance(contradictions, list):
                contradictions = []
            horizon_data[info["label"]].append({
                "distance_s": distance_ms / 1000.0,
                "pnl": _f(chosen.get("current_pnl_pct")),
                "mfe": _f(chosen.get("mfe_pct")),
                "danger_score": _f(chosen.get("danger_score")),
                "side_ret_1m": _f(snap.get("side_ret_1m_pct")),
                "side_ret_3m": _f(snap.get("side_ret_3m_pct")),
                "flow_opposite": bool(snap.get("flow_opposite")),
                "positioning_opposite": bool(snap.get("positioning_opposite")),
                "micro_structure_opposite": bool(snap.get("opposite_micro_structure")),
                "contradiction_count": float(len(contradictions)),
            })

        by_label: dict[str, Any] = {}
        for label in LABELS:
            items = horizon_data.get(label, [])
            def vals(key: str) -> list[float]:
                return [float(x[key]) for x in items if x.get(key) is not None]
            pnls = vals("pnl")
            mfes = vals("mfe")
            ret3 = vals("side_ret_3m")
            danger = vals("danger_score")
            by_label[label] = {
                "full_n": full_counts[label],
                "alive_at_horizon_n": alive_counts[label],
                "closed_before_horizon_n": closed_before_counts[label],
                "closed_before_horizon_rate_pct": (
                    100.0 * closed_before_counts[label] / full_counts[label]
                    if full_counts[label] else None
                ),
                "matched_snapshot_n": len(items),
                "matched_of_alive_pct": (
                    100.0 * len(items) / alive_counts[label]
                    if alive_counts[label] else None
                ),
                "median_distance_to_target_s": _median(vals("distance_s")),
                "median_pnl_pct": _median(pnls),
                "median_mfe_pct": _median(mfes),
                "pnl_positive_rate_pct": (
                    100.0 * sum(v > 0 for v in pnls) / len(pnls)
                    if pnls else None
                ),
                "pnl_le_minus_035_rate_pct": (
                    100.0 * sum(v <= -0.35 for v in pnls) / len(pnls)
                    if pnls else None
                ),
                "mfe_ge_050_rate_pct": (
                    100.0 * sum(v >= 0.50 for v in mfes) / len(mfes)
                    if mfes else None
                ),
                "side_ret3_negative_rate_pct": (
                    100.0 * sum(v < 0 for v in ret3) / len(ret3)
                    if ret3 else None
                ),
                "flow_opposite_rate_pct": (
                    100.0 * sum(bool(x["flow_opposite"]) for x in items) / len(items)
                    if items else None
                ),
                "positioning_opposite_rate_pct": (
                    100.0 * sum(bool(x["positioning_opposite"]) for x in items) / len(items)
                    if items else None
                ),
                "micro_structure_opposite_rate_pct": (
                    100.0 * sum(bool(x["micro_structure_opposite"]) for x in items) / len(items)
                    if items else None
                ),
                "danger_ge_2_rate_pct": (
                    100.0 * sum(v >= 2 for v in danger) / len(danger)
                    if danger else None
                ),
                "danger_ge_4_rate_pct": (
                    100.0 * sum(v >= 4 for v in danger) / len(danger)
                    if danger else None
                ),
                "median_contradiction_count": _median(vals("contradiction_count")),
            }
        result["horizons"][str(horizon)] = by_label
    return result

def run_wd2() -> dict[str, Any]:
    entry = _entry_rows()
    evaluations = _evaluation_rows()
    pp_observations = _pp_observation_rows()
    gate_missing = sum(1 for row in entry if not row.get("gate_snapshot_json"))
    return {
        "version": WD2_VERSION,
        "authority": "RESEARCH_ONLY",
        "discovery_cutoff_ms": WD2_CUTOFF_MS,
        "trades": len(entry),
        "gate_snapshot_missing": gate_missing,
        "numeric_entry": numeric_entry_anatomy(entry),
        "categorical_entry": categorical_entry_anatomy(entry),
        "segments": segment_outcomes(entry),
        "event_driven_horizons": build_horizon_anatomy(evaluations),
        "high_res_horizons": build_high_res_horizon_anatomy(
            pp_observations,
            entry,
        ),
    }
