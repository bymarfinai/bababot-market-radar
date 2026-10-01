from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import psycopg2.extras

from market_radar.persistence import _postgres_connect
from .wd2_anatomy import WD2_CUTOFF_MS
from .wd5a_features import reconstruct_row, causal_audit


WD5C_VERSION = "wd5c-winner-archetype-mapping-v1"
EXPECTED_ROWS = 2175
CSV_OUTPUT_PATH = Path("/app/data/wd5c_winner_archetypes.csv")
JSON_OUTPUT_PATH = Path("/app/data/wd5c_winner_archetypes_results.json")

FEATURE_EXCLUDE = {
    "f_decision_hour_utc",
    "f_decision_hour_sin",
    "f_decision_hour_cos",
    "f_decision_weekday_utc",
}
SCALE_PROXY_FEATURES = {
    "f_context_quote_volume_5m",
    "f_context_quote_volume_24h",
    "f_context_regime_ema7",
    "f_context_regime_ema20",
}


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _load_rows() -> list[dict[str, Any]]:
    query = """
        select
            w.position_id, w.signal_id, w.symbol, w.side, w.opened_at_ms,
            w.closed_at_ms, w.outcome_label, w.max_mfe_pct, w.min_mae_pct,
            w.early_min_mae_pct, w.first_early_adverse_at_ms,
            w.first_directional_mfe_at_ms, w.reached_runner_1pct,
            w.realized_pnl, w.realized_pnl_pct, w.close_reason,
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
        join entry_latency e on e.signal_id=w.signal_id
        join lateral (
            select checked_at_ms, reasons_json, snapshot_json
            from entry_revalidations x
            where x.signal_id=w.signal_id
              and x.verdict='ENTER'
              and x.checked_at_ms <= w.opened_at_ms
            order by x.checked_at_ms desc
            limit 1
        ) r on true
        where w.closed_at_ms <= %s
        order by w.opened_at_ms, w.position_id
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_CUTOFF_MS,))
            rows = [dict(row) for row in cur.fetchall()]
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(f"WD5C expected {EXPECTED_ROWS} rows, got {len(rows)}")
    return rows


def opportunity_tier(mfe: float) -> str:
    if mfe >= 2.0:
        return "BIG_RUNNER"
    if mfe >= 1.0:
        return "RUNNER"
    if mfe >= 0.5:
        return "SMALL_EDGE"
    if mfe >= 0.35:
        return "BORDERLINE"
    return "NO_EDGE"


def realized_win_tier(realized_pct: float) -> str:
    if realized_pct >= 1.0:
        return "BIG_REALIZED_WIN"
    if realized_pct >= 0.5:
        return "MEDIUM_REALIZED_WIN"
    if realized_pct > 0.0:
        return "SMALL_REALIZED_WIN"
    return "NON_WIN"


def path_style(outcome_label: str) -> str:
    mapping = {
        "RECOVERED_DRAWDOWN": "RECOVERED_WINNER",
        "CORRECT_RUNNER": "CLEAN_WINNER",
        "RIGHT_THEN_FAILURE": "MISSED_OPPORTUNITY",
        "TRUE_WRONG_DIRECTION": "WRONG_DIRECTION",
        "STALL_NO_EDGE": "STALL",
    }
    return mapping.get(outcome_label, "OTHER")


def capture_class(mfe: float, realized_pct: float) -> tuple[str, float | None]:
    if mfe < 0.5:
        return "NO_MEANINGFUL_OPPORTUNITY", None
    ratio = realized_pct / mfe if mfe > 0 else None
    if realized_pct <= 0:
        return "MISSED", ratio
    if ratio is not None and ratio >= 0.50:
        return "HIGH_CAPTURE_GE50", ratio
    if ratio is not None and ratio >= 0.25:
        return "MEDIUM_CAPTURE_25_50", ratio
    return "LOW_CAPTURE_LT25", ratio


def composite_archetype(
    opportunity: str,
    path: str,
    realized: str,
) -> str:
    if opportunity == "BIG_RUNNER":
        if path == "MISSED_OPPORTUNITY":
            return "BIG_RUNNER_MISSED"
        if path == "RECOVERED_WINNER":
            return "BIG_RUNNER_RECOVERED"
        if path == "CLEAN_WINNER":
            return "BIG_RUNNER_CLEAN"
        return "BIG_RUNNER_OTHER"
    if opportunity == "RUNNER":
        if path == "MISSED_OPPORTUNITY":
            return "RUNNER_MISSED"
        if path == "RECOVERED_WINNER":
            return "RUNNER_RECOVERED"
        if path == "CLEAN_WINNER":
            return "RUNNER_CLEAN"
        return "RUNNER_OTHER"
    if opportunity == "SMALL_EDGE":
        if realized != "NON_WIN":
            return "SMALL_EDGE_WIN"
        return "SMALL_EDGE_FAILED"
    if opportunity == "BORDERLINE":
        return "BORDERLINE_WIN" if realized != "NON_WIN" else "BORDERLINE_NONWIN"
    return "NO_EDGE_WIN" if realized != "NON_WIN" else "NO_EDGE_NONWIN"


def build_row(source: dict[str, Any]) -> dict[str, Any]:
    dummy_targets = {
        "target_strict_1_to_1": "NA",
        "target_extended_stop": "NA",
        "target_robust_1_to_1": "NA",
    }
    base = reconstruct_row(source, dummy_targets)
    for key in list(base):
        if key.startswith("target_"):
            base.pop(key)

    mfe = float(source["max_mfe_pct"])
    mae = float(source["min_mae_pct"])
    realized_pct = float(source["realized_pnl_pct"])
    opp = opportunity_tier(mfe)
    realized = realized_win_tier(realized_pct)
    path = path_style(str(source["outcome_label"]))
    capture, ratio = capture_class(mfe, realized_pct)
    first_mfe = source.get("first_directional_mfe_at_ms")
    opened = int(source["opened_at_ms"])

    base.update({
        "label_opportunity_tier": opp,
        "label_realized_win_tier": realized,
        "label_path_style": path,
        "label_capture_class": capture,
        "label_composite_archetype": composite_archetype(opp, path, realized),
        "future_outcome_label": str(source["outcome_label"]),
        "future_max_mfe_pct": mfe,
        "future_min_mae_pct": mae,
        "future_early_min_mae_pct": _f(source.get("early_min_mae_pct")),
        "future_realized_pnl": float(source["realized_pnl"]),
        "future_realized_pnl_pct": realized_pct,
        "future_capture_ratio": ratio,
        "future_duration_min": (
            (int(source["closed_at_ms"]) - opened) / 60000.0
        ),
        "future_time_to_0p5_mfe_min": (
            None if first_mfe is None
            else (int(first_mfe) - opened) / 60000.0
        ),
        "future_reached_runner_1pct": int(source["reached_runner_1pct"]),
        "future_close_reason": str(source.get("close_reason") or ""),
    })
    return base


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def summarize_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"n": 0}
    def vals(key: str) -> list[float]:
        return [
            float(r[key]) for r in rows
            if r.get(key) is not None
        ]
    pnl = vals("future_realized_pnl")
    pnl_pct = vals("future_realized_pnl_pct")
    capture = vals("future_capture_ratio")
    return {
        "n": n,
        "share_pct": 100.0 * n / EXPECTED_ROWS,
        "net_pnl": sum(pnl),
        "positive_final_n": sum(float(r["future_realized_pnl_pct"]) > 0 for r in rows),
        "positive_final_pct": 100.0 * sum(
            float(r["future_realized_pnl_pct"]) > 0 for r in rows
        ) / n,
        "median_mfe_pct": _median(vals("future_max_mfe_pct")),
        "median_mae_pct": _median(vals("future_min_mae_pct")),
        "median_early_mae_pct": _median(vals("future_early_min_mae_pct")),
        "median_realized_pct": _median(pnl_pct),
        "median_capture_ratio": _median(capture),
        "median_duration_min": _median(vals("future_duration_min")),
        "median_time_to_0p5_mfe_min": _median(vals("future_time_to_0p5_mfe_min")),
        "wd1_outcomes": dict(Counter(r["future_outcome_label"] for r in rows)),
        "path_styles": dict(Counter(r["label_path_style"] for r in rows)),
        "capture_classes": dict(Counter(r["label_capture_class"] for r in rows)),
        "side_counts": dict(Counter(r["meta_original_side"] for r in rows)),
        "stage_counts": dict(Counter(r["f_stage"] for r in rows)),
    }


def auc_score(y: list[int], score: list[float]) -> float | None:
    n_pos = sum(y)
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    ranked = sorted(zip(score, y), key=lambda x: x[0])
    rank_sum = 0.0
    rank = 1
    i = 0
    while i < len(ranked):
        j = i + 1
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        avg = (rank + rank + (j - i) - 1) / 2.0
        rank_sum += avg * sum(v for _, v in ranked[i:j])
        rank += j - i
        i = j
    u = rank_sum - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def numeric_sep(
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
    feature: str,
) -> dict[str, Any]:
    av = [float(r[feature]) for r in a]
    bv = [float(r[feature]) for r in b]
    y = [1] * len(av) + [0] * len(bv)
    score = av + bv
    auc = auc_score(y, score)
    sep = 0.0 if auc is None else abs(auc - 0.5) * 2.0
    med_a = _median(av)
    med_b = _median(bv)
    direction = (
        1 if med_a is not None and med_b is not None and med_a > med_b
        else -1 if med_a is not None and med_b is not None and med_a < med_b
        else 0
    )
    return {
        "separation": sep,
        "auc_a_higher": auc,
        "a_median": med_a,
        "b_median": med_b,
        "direction": direction,
    }


def categorical_sep(
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
    feature: str,
) -> dict[str, Any]:
    rows = [(r[feature], 1) for r in a] + [(r[feature], 0) for r in b]
    base = len(a) / len(rows)
    groups: dict[str, list[int]] = defaultdict(list)
    for value, target in rows:
        groups[str(value)].append(target)
    weighted = 0.0
    rates = {}
    for value, ys in groups.items():
        rate = sum(ys) / len(ys)
        weighted += len(ys) / len(rows) * abs(rate - base)
        rates[value] = {
            "n": len(ys),
            "a_rate": rate,
        }
    return {
        "separation": min(1.0, 2.0 * weighted),
        "category_rates": rates,
    }


def feature_manifest(rows: list[dict[str, Any]]) -> dict[str, str]:
    out = {}
    for key in rows[0]:
        if not key.startswith("f_"):
            continue
        values = [r[key] for r in rows]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            out[key] = "numeric"
        else:
            out[key] = "categorical"
    return out


def pairwise_anatomy(
    rows: list[dict[str, Any]],
    *,
    name: str,
    a_filter,
    b_filter,
    feature_types: dict[str, str],
) -> dict[str, Any]:
    a = [r for r in rows if a_filter(r)]
    b = [r for r in rows if b_filter(r)]
    usable_features = [
        f for f in feature_types
        if f not in FEATURE_EXCLUDE
        and f not in SCALE_PROXY_FEATURES
        and not f.startswith("f_latency_")
        and len({str(r[f]) for r in rows}) > 1
    ]

    ranked = []
    n_all = len(rows)
    fifths = [
        rows[i * n_all // 5:(i + 1) * n_all // 5]
        for i in range(5)
    ]

    for feature in usable_features:
        if feature_types[feature] == "numeric":
            info = numeric_sep(a, b, feature)
        else:
            info = categorical_sep(a, b, feature)

        block_scores = []
        directions = []
        for block in fifths:
            ba = [r for r in block if a_filter(r)]
            bb = [r for r in block if b_filter(r)]
            if len(ba) < 5 or len(bb) < 5:
                continue
            if feature_types[feature] == "numeric":
                bi = numeric_sep(ba, bb, feature)
                directions.append(bi["direction"])
            else:
                bi = categorical_sep(ba, bb, feature)
            block_scores.append(bi["separation"])

        direction_consistent = None
        if feature_types[feature] == "numeric":
            nonzero = [d for d in directions if d]
            direction_consistent = len(set(nonzero)) <= 1 if nonzero else True

        ranked.append({
            "feature": feature,
            "type": feature_types[feature],
            **info,
            "fifth_scores": block_scores,
            "median_fifth_separation": (
                statistics.median(block_scores) if block_scores else None
            ),
            "min_fifth_separation": min(block_scores) if block_scores else None,
            "numeric_direction_consistent": direction_consistent,
        })

    ranked.sort(
        key=lambda x: (
            x["median_fifth_separation"]
            if x["median_fifth_separation"] is not None else -1.0,
            x["min_fifth_separation"]
            if x["min_fifth_separation"] is not None else -1.0,
            x["separation"],
        ),
        reverse=True,
    )
    return {
        "comparison": name,
        "a_n": len(a),
        "b_n": len(b),
        "a_summary": summarize_group(a),
        "b_summary": summarize_group(b),
        "top_features": ranked[:30],
    }


def run_wd5c() -> dict[str, Any]:
    sources = _load_rows()
    audit = causal_audit(sources)
    if not audit["causal_pass"]:
        raise RuntimeError(f"WD5C causal audit failed: {audit}")

    rows = [build_row(source) for source in sources]
    types = feature_manifest(rows)

    CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUTPUT_PATH.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    groups = {}
    for label_name in (
        "label_opportunity_tier",
        "label_realized_win_tier",
        "label_path_style",
        "label_capture_class",
        "label_composite_archetype",
    ):
        groups[label_name] = {
            value: summarize_group([r for r in rows if r[label_name] == value])
            for value in sorted({r[label_name] for r in rows})
        }

    comparisons = [
        pairwise_anatomy(
            rows,
            name="BIG_RUNNER_vs_SMALL_EDGE",
            a_filter=lambda r: r["label_opportunity_tier"] == "BIG_RUNNER",
            b_filter=lambda r: r["label_opportunity_tier"] == "SMALL_EDGE",
            feature_types=types,
        ),
        pairwise_anatomy(
            rows,
            name="BIG_RUNNER_vs_NO_EDGE",
            a_filter=lambda r: r["label_opportunity_tier"] == "BIG_RUNNER",
            b_filter=lambda r: r["label_opportunity_tier"] == "NO_EDGE",
            feature_types=types,
        ),
        pairwise_anatomy(
            rows,
            name="BIG_REALIZED_WIN_vs_SMALL_REALIZED_WIN",
            a_filter=lambda r: r["label_realized_win_tier"] == "BIG_REALIZED_WIN",
            b_filter=lambda r: r["label_realized_win_tier"] == "SMALL_REALIZED_WIN",
            feature_types=types,
        ),
        pairwise_anatomy(
            rows,
            name="CLEAN_WINNER_vs_RECOVERED_WINNER",
            a_filter=lambda r: r["label_path_style"] == "CLEAN_WINNER",
            b_filter=lambda r: r["label_path_style"] == "RECOVERED_WINNER",
            feature_types=types,
        ),
        pairwise_anatomy(
            rows,
            name="BIG_RUNNER_WINNER_vs_BIG_RUNNER_MISSED",
            a_filter=lambda r: (
                r["label_opportunity_tier"] == "BIG_RUNNER"
                and float(r["future_realized_pnl_pct"]) > 0
            ),
            b_filter=lambda r: r["label_composite_archetype"] == "BIG_RUNNER_MISSED",
            feature_types=types,
        ),
        pairwise_anatomy(
            rows,
            name="RUNNER_WINNER_vs_RUNNER_MISSED",
            a_filter=lambda r: (
                r["label_opportunity_tier"] == "RUNNER"
                and float(r["future_realized_pnl_pct"]) > 0
            ),
            b_filter=lambda r: r["label_composite_archetype"] == "RUNNER_MISSED",
            feature_types=types,
        ),
    ]

    result = {
        "version": WD5C_VERSION,
        "authority": "RESEARCH_ONLY",
        "discovery_cutoff_ms": WD2_CUTOFF_MS,
        "rows": len(rows),
        "causal_audit": audit,
        "definitions": {
            "opportunity_tier": {
                "BIG_RUNNER": "MFE >= 2.0%",
                "RUNNER": "1.0% <= MFE < 2.0%",
                "SMALL_EDGE": "0.5% <= MFE < 1.0%",
                "BORDERLINE": "0.35% <= MFE < 0.5%",
                "NO_EDGE": "MFE < 0.35%",
            },
            "realized_win_tier": {
                "BIG_REALIZED_WIN": "realized pnl pct >= 1.0%",
                "MEDIUM_REALIZED_WIN": "0.5% <= realized pnl pct < 1.0%",
                "SMALL_REALIZED_WIN": "0 < realized pnl pct < 0.5%",
                "NON_WIN": "realized pnl pct <= 0",
            },
            "capture_class": {
                "HIGH_CAPTURE_GE50": "positive final and realized/MFE >= 50%",
                "MEDIUM_CAPTURE_25_50": "positive final and 25% <= realized/MFE < 50%",
                "LOW_CAPTURE_LT25": "positive final and realized/MFE < 25%",
                "MISSED": "MFE >= 0.5% but final <= 0",
            },
        },
        "group_summaries": groups,
        "pairwise_anatomy": comparisons,
        "feature_count": len(types),
        "portable_feature_count": sum(
            f not in FEATURE_EXCLUDE
            and f not in SCALE_PROXY_FEATURES
            and not f.startswith("f_latency_")
            and len({str(r[f]) for r in rows}) > 1
            for f in types
        ),
        "outputs": {
            "csv": str(CSV_OUTPUT_PATH),
            "json": str(JSON_OUTPUT_PATH),
        },
    }
    JSON_OUTPUT_PATH.write_text(json.dumps(result, indent=2, allow_nan=False))
    return result
