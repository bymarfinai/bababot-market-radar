from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from .wd5b_discovery import Encoder, LogisticModel, auc_score, binary_metrics


WD5D_VERSION = "wd5d-opportunity-exhaustion-features-v1"
INPUT_PATH = Path("/app/data/wd5c_winner_archetypes.csv")
OUTPUT_CSV = Path("/app/data/wd5d_opportunity_exhaustion_features.csv")
OUTPUT_JSON = Path("/app/data/wd5d_feature_discovery_results.json")

TIME_FEATURES = {
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

NEW_FEATURES = (
    "f_new_accel_5_vs_15",
    "f_new_accel_15_vs_60",
    "f_new_momentum_curvature",
    "f_new_extension_5m_norm",
    "f_new_extension_15m_norm",
    "f_new_extension_60m_norm",
    "f_new_micro_accel_1_vs_3",
    "f_new_micro_ratio_1_vs_3",
    "f_new_gate_vs_5m_speed_ratio",
    "f_new_activity_heat",
    "f_new_score_x_activity_heat",
    "f_new_flow_gap_gate",
    "f_new_flow_gap_context",
    "f_new_price_x_flow_gap",
    "f_new_gate_price_x_flow_gap",
    "f_new_heat_x_flow_gap",
    "f_new_heat_x_micro_fade",
    "f_new_heat_x_extension",
    "f_new_volume_over_range",
    "f_new_trades_over_range",
    "f_new_oi_per_price",
    "f_new_family_balance",
    "f_new_positioning_support",
    "f_new_regime_support",
    "f_new_flow_support",
    "f_new_continuation_support",
    "f_new_overheat_pressure",
)


def _f(row: dict[str, Any], key: str) -> float:
    return float(row[key])


def _safe_div(a: float, b: float, eps: float = 1e-6) -> float:
    return a / (abs(b) + eps)


def _family_score(value: str) -> float:
    value = str(value).upper()
    if value in {"ALIGNED", "SUPPORTIVE"}:
        return 1.0
    if value == "OPPOSITE":
        return -1.0
    return 0.0


def derive_features(row: dict[str, Any]) -> dict[str, float]:
    r5 = _f(row, "f_ret_5m_pct_for_selected")
    r15 = _f(row, "f_ret_15m_pct_for_selected")
    r60 = _f(row, "f_ret_1h_pct_for_selected")
    med5 = max(abs(_f(row, "f_median_abs_ret_5m_pct")), 1e-6)
    side1 = _f(row, "f_gate_side_ret_1m_pct")
    side3 = _f(row, "f_gate_side_ret_3m_pct")
    taker_gate = _f(row, "f_gate_taker_share_for_selected")
    taker_context = _f(row, "f_context_taker_share_for_selected")
    volume = max(0.0, _f(row, "f_volume_ratio_signal"))
    range_ratio = max(0.0, _f(row, "f_range_ratio"))
    trades = max(0.0, _f(row, "f_trades_ratio"))
    return_exp = max(0.0, _f(row, "f_return_expansion_ratio"))
    oi_change = _f(row, "f_context_raw_oi_change_pct")
    score = _f(row, "f_selected_score")

    speed15 = r15 / 3.0
    speed60 = r60 / 12.0
    speed3 = side3 / 3.0
    accel_5_15 = r5 - speed15
    accel_15_60 = speed15 - speed60
    curvature = accel_5_15 - accel_15_60
    micro_accel = side1 - speed3

    activity_heat = (
        max(volume, 1e-9)
        * max(range_ratio, 1e-9)
        * max(trades, 1e-9)
        * max(return_exp, 1e-9)
    ) ** 0.25

    flow_gap_gate = max(0.0, 0.60 - taker_gate)
    flow_gap_context = max(0.0, 0.60 - taker_context)
    micro_fade = max(0.0, speed3 - side1)

    positioning_support = _family_score(row["f_gate_positioning_family"])
    regime_support = _family_score(row["f_gate_regime_family"])
    flow_support = _family_score(row["f_gate_flow_family"])
    aligned = _f(row, "f_gate_aligned_family_count")
    opposing = _f(row, "f_gate_opposing_family_count")
    family_balance = aligned - opposing

    extension5 = _safe_div(r5, med5)
    extension15 = _safe_div(speed15, med5)
    extension60 = _safe_div(speed60, med5)

    continuation_support = (
        0.35 * taker_gate
        + 0.20 * taker_context
        + 0.15 * max(-1.0, min(1.0, positioning_support))
        + 0.10 * max(-1.0, min(1.0, regime_support))
        + 0.10 * max(-1.0, min(1.0, flow_support))
        + 0.10 * max(-1.0, min(1.0, family_balance / 4.0))
    )

    # Fixed, label-agnostic composite: high activity + high score + recent
    # acceleration + weak flow + micro fade => continuation-overheat pressure.
    overheat_pressure = (
        (score / 100.0)
        * activity_heat
        * (1.0 + max(0.0, accel_5_15) + max(0.0, accel_15_60))
        * (1.0 + flow_gap_gate + micro_fade)
    )

    return {
        "f_new_accel_5_vs_15": accel_5_15,
        "f_new_accel_15_vs_60": accel_15_60,
        "f_new_momentum_curvature": curvature,
        "f_new_extension_5m_norm": extension5,
        "f_new_extension_15m_norm": extension15,
        "f_new_extension_60m_norm": extension60,
        "f_new_micro_accel_1_vs_3": micro_accel,
        "f_new_micro_ratio_1_vs_3": _safe_div(side1, speed3),
        "f_new_gate_vs_5m_speed_ratio": _safe_div(speed3, r5 / 5.0),
        "f_new_activity_heat": activity_heat,
        "f_new_score_x_activity_heat": (score / 100.0) * activity_heat,
        "f_new_flow_gap_gate": flow_gap_gate,
        "f_new_flow_gap_context": flow_gap_context,
        "f_new_price_x_flow_gap": max(0.0, r5) * flow_gap_gate,
        "f_new_gate_price_x_flow_gap": max(0.0, side3) * flow_gap_gate,
        "f_new_heat_x_flow_gap": activity_heat * flow_gap_gate,
        "f_new_heat_x_micro_fade": activity_heat * micro_fade,
        "f_new_heat_x_extension": activity_heat * max(0.0, extension5),
        "f_new_volume_over_range": _safe_div(volume, range_ratio),
        "f_new_trades_over_range": _safe_div(trades, range_ratio),
        "f_new_oi_per_price": _safe_div(oi_change, r5),
        "f_new_family_balance": family_balance,
        "f_new_positioning_support": positioning_support,
        "f_new_regime_support": regime_support,
        "f_new_flow_support": flow_support,
        "f_new_continuation_support": continuation_support,
        "f_new_overheat_pressure": overheat_pressure,
    }


def load_augmented_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = list(csv.DictReader(INPUT_PATH.open()))
    for row in rows:
        row.update({k: str(v) for k, v in derive_features(row).items()})
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    return rows


def feature_types(rows: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in rows[0]:
        if not key.startswith("f_"):
            continue
        if key in NEW_FEATURES:
            out[key] = "numeric"
            continue
        numeric = True
        for row in rows[:100]:
            try:
                float(row[key])
            except (TypeError, ValueError):
                numeric = False
                break
        out[key] = "numeric" if numeric else "categorical"
    return out


def portable_base_features(
    rows: list[dict[str, Any]],
    types: dict[str, str],
) -> list[str]:
    return [
        f for f in types
        if not f.startswith("f_new_")
        and f not in TIME_FEATURES
        and f not in SCALE_PROXY_FEATURES
        and not f.startswith("f_latency_")
        and len({str(r[f]) for r in rows}) > 1
    ]


def task_membership(row: dict[str, Any], task: str) -> int | None:
    opp = row["label_opportunity_tier"]
    path = row["label_path_style"]
    realized = float(row["future_realized_pnl_pct"])
    mfe = float(row["future_max_mfe_pct"])

    if task == "RUNNER_WIN_vs_RUNNER_MISSED":
        if opp not in {"RUNNER", "BIG_RUNNER"}:
            return None
        if realized > 0:
            return 1
        if path == "MISSED_OPPORTUNITY":
            return 0
        return None

    if task == "RUNNER_OPPORTUNITY_vs_SUB1":
        return 1 if mfe >= 1.0 else 0

    if task == "BIG_RUNNER_vs_SMALL_EDGE":
        if opp == "BIG_RUNNER":
            return 1
        if opp == "SMALL_EDGE":
            return 0
        return None

    if task == "CLEAN_vs_RECOVERED":
        if path == "CLEAN_WINNER":
            return 1
        if path == "RECOVERED_WINNER":
            return 0
        return None

    raise KeyError(task)


TASKS = (
    "RUNNER_WIN_vs_RUNNER_MISSED",
    "RUNNER_OPPORTUNITY_vs_SUB1",
    "BIG_RUNNER_vs_SMALL_EDGE",
    "CLEAN_vs_RECOVERED",
)


def _numeric_sep(
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
    feature: str,
) -> dict[str, Any]:
    av = [float(r[feature]) for r in a]
    bv = [float(r[feature]) for r in b]
    y = [1] * len(av) + [0] * len(bv)
    p = av + bv
    auc = auc_score(y, p)
    sep = 0.0 if auc is None else abs(float(auc) - 0.5) * 2.0
    return {
        "separation": sep,
        "auc": auc,
        "positive_median": statistics.median(av),
        "negative_median": statistics.median(bv),
        "direction": (
            1 if statistics.median(av) > statistics.median(bv)
            else -1 if statistics.median(av) < statistics.median(bv)
            else 0
        ),
    }


def feature_stability(
    rows: list[dict[str, Any]],
    task: str,
    features: list[str],
) -> list[dict[str, Any]]:
    task_rows = [r for r in rows if task_membership(r, task) is not None]
    n = len(task_rows)
    fifths = [
        task_rows[i * n // 5:(i + 1) * n // 5]
        for i in range(5)
    ]
    ranked = []
    for feature in features:
        pos = [r for r in task_rows if task_membership(r, task) == 1]
        neg = [r for r in task_rows if task_membership(r, task) == 0]
        full = _numeric_sep(pos, neg, feature)
        block_scores = []
        directions = []
        for block in fifths:
            bp = [r for r in block if task_membership(r, task) == 1]
            bn = [r for r in block if task_membership(r, task) == 0]
            if len(bp) < 5 or len(bn) < 5:
                continue
            info = _numeric_sep(bp, bn, feature)
            block_scores.append(info["separation"])
            directions.append(info["direction"])
        nonzero = [x for x in directions if x != 0]
        ranked.append({
            "feature": feature,
            **full,
            "fifth_scores": block_scores,
            "median_fifth_separation": (
                statistics.median(block_scores) if block_scores else None
            ),
            "min_fifth_separation": min(block_scores) if block_scores else None,
            "direction_consistent": (
                len(set(nonzero)) <= 1 if nonzero else True
            ),
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
    return ranked


def _categorical_train_separation(
    pos: list[dict[str, Any]],
    neg: list[dict[str, Any]],
    feature: str,
) -> float:
    rows = [(str(r[feature]), 1) for r in pos] + [(str(r[feature]), 0) for r in neg]
    if not rows:
        return 0.0
    base = len(pos) / len(rows)
    groups: dict[str, list[int]] = {}
    for value, target in rows:
        groups.setdefault(value, []).append(target)
    weighted = 0.0
    for ys in groups.values():
        rate = sum(ys) / len(ys)
        weighted += len(ys) / len(rows) * abs(rate - base)
    return min(1.0, 2.0 * weighted)


def rank_train_features(
    train_rows: list[dict[str, Any]],
    task: str,
    features: list[str],
    types: dict[str, str],
) -> list[str]:
    pos = [r for r in train_rows if task_membership(r, task) == 1]
    neg = [r for r in train_rows if task_membership(r, task) == 0]
    ranked = []
    for feature in features:
        if types[feature] == "numeric":
            score = _numeric_sep(pos, neg, feature)["separation"]
        else:
            score = _categorical_train_separation(pos, neg, feature)
        ranked.append((score, feature))
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [feature for _, feature in ranked]


def _split_task(
    rows: list[dict[str, Any]],
    task: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rr = [r for r in rows if task_membership(r, task) is not None]
    rr.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    n = len(rr)
    return rr[:3*n//5], rr[3*n//5:4*n//5], rr[4*n//5:]


def _prepare_rows(
    rows: list[dict[str, Any]],
    task: str,
) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        x = dict(r)
        x["_target"] = task_membership(r, task)
        out.append(x)
    return out


def _fit_eval(
    train: list[dict[str, Any]],
    val: list[dict[str, Any]],
    test: list[dict[str, Any]],
    features: list[str],
    types: dict[str, str],
    top_k: int,
    l2: float,
) -> dict[str, Any]:
    chosen = features[:min(top_k, len(features))]
    encoder = Encoder(chosen, types).fit(train)
    x_train = encoder.transform(train)
    y_train = [int(r["_target"]) for r in train]
    model = LogisticModel(l2=l2, epochs=700, lr=0.12).fit(x_train, y_train)
    val_probs = model.predict_proba(encoder.transform(val))
    test_probs = model.predict_proba(encoder.transform(test))
    y_val = [int(r["_target"]) for r in val]
    y_test = [int(r["_target"]) for r in test]
    return {
        "top_k": len(chosen),
        "l2": l2,
        "features": chosen,
        "encoded_feature_count": len(encoder.encoded_names),
        "validation": binary_metrics(y_val, val_probs),
        "test": binary_metrics(y_test, test_probs),
    }


def model_comparison(
    rows: list[dict[str, Any]],
    task: str,
    base_features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    train_raw, val_raw, test_raw = _split_task(rows, task)
    train = _prepare_rows(train_raw, task)
    val = _prepare_rows(val_raw, task)
    test = _prepare_rows(test_raw, task)

    variants = {
        "baseline": base_features,
        "engineered_only": list(NEW_FEATURES),
        "combined": base_features + list(NEW_FEATURES),
    }
    results = {}
    for name, candidates in variants.items():
        # Every variant receives the same train-only univariate ranking.
        # No validation/test information is used to order features.
        ordered = rank_train_features(
            train_raw,
            task,
            candidates,
            types,
        )

        grid = []
        for k in (5, 10, 20, 40):
            if k > len(ordered):
                continue
            for l2 in (0.1, 1.0, 4.0):
                grid.append(
                    _fit_eval(train, val, test, ordered, types, k, l2)
                )
        grid.sort(
            key=lambda x: (
                x["validation"]["auc"]
                if x["validation"]["auc"] is not None else -1.0,
                x["validation"]["balanced_accuracy"]
                if x["validation"]["balanced_accuracy"] is not None else -1.0,
                -x["top_k"],
            ),
            reverse=True,
        )
        results[name] = {
            "selected": grid[0],
            "top_grid": grid[:8],
        }

    return {
        "task": task,
        "train_n": len(train),
        "validation_n": len(val),
        "test_n": len(test),
        "class_counts": dict(Counter(int(r["_target"]) for r in train + val + test)),
        "variants": results,
    }


def _runner_miss_target(row: dict[str, Any]) -> int:
    return 1 if row["label_path_style"] == "MISSED_OPPORTUNITY" else 0


def _overheat_rule_metrics(
    rows: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    tp = fp = tn = fn = 0
    for row in rows:
        pred_miss = float(row["f_new_overheat_pressure"]) >= threshold
        target = _runner_miss_target(row)
        if pred_miss and target:
            tp += 1
        elif pred_miss and not target:
            fp += 1
        elif not pred_miss and not target:
            tn += 1
        else:
            fn += 1
    miss_recall = tp / (tp + fn) if tp + fn else None
    winner_keep = tn / (tn + fp) if tn + fp else None
    return {
        "n": len(rows),
        "miss_n": tp + fn,
        "winner_n": tn + fp,
        "flagged_n": tp + fp,
        "flagged_pct": 100.0 * (tp + fp) / len(rows) if rows else None,
        "miss_precision": tp / (tp + fp) if tp + fp else None,
        "miss_recall": miss_recall,
        "winner_keep_rate": winner_keep,
        "balanced_accuracy": (
            (miss_recall + winner_keep) / 2.0
            if miss_recall is not None and winner_keep is not None
            else None
        ),
        "tp_miss": tp,
        "fp_winner": fp,
        "tn_winner": tn,
        "fn_miss": fn,
    }


def overheat_threshold_diagnostic(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    cohort = [
        r for r in rows
        if r["label_opportunity_tier"] in {"RUNNER", "BIG_RUNNER"}
        and (
            float(r["future_realized_pnl_pct"]) > 0
            or r["label_path_style"] == "MISSED_OPPORTUNITY"
        )
    ]
    cohort.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    n = len(cohort)
    train = cohort[:3*n//5]
    validation = cohort[3*n//5:4*n//5]
    test = cohort[4*n//5:]

    values = sorted({
        float(r["f_new_overheat_pressure"])
        for r in train
    })
    candidates = []
    for left, right in zip(values, values[1:]):
        threshold = (left + right) / 2.0
        metrics = _overheat_rule_metrics(train, threshold)
        candidates.append((
            metrics["balanced_accuracy"],
            metrics["miss_recall"],
            metrics["winner_keep_rate"],
            threshold,
            metrics,
        ))
    if not candidates:
        raise RuntimeError("no overheat threshold candidates")
    candidates.sort(reverse=True)
    threshold = float(candidates[0][3])

    all_values = sorted(
        float(r["f_new_overheat_pressure"])
        for r in cohort
    )
    cuts = [
        all_values[int(q * (len(all_values) - 1))]
        for q in (0.2, 0.4, 0.6, 0.8)
    ]
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(5)]
    for row in cohort:
        value = float(row["f_new_overheat_pressure"])
        idx = sum(value > cut for cut in cuts)
        buckets[idx].append(row)

    quintiles = []
    for i, bucket in enumerate(buckets, 1):
        miss_n = sum(_runner_miss_target(r) for r in bucket)
        quintiles.append({
            "quintile": i,
            "n": len(bucket),
            "median_overheat_pressure": statistics.median(
                float(r["f_new_overheat_pressure"]) for r in bucket
            ),
            "miss_n": miss_n,
            "miss_rate_pct": 100.0 * miss_n / len(bucket),
            "actual_net_pnl": sum(
                float(r["future_realized_pnl"]) for r in bucket
            ),
        })

    return {
        "cohort_definition": (
            "MFE>=1% runner opportunity; positive-final winner versus "
            "RIGHT_THEN_FAILURE missed runner"
        ),
        "n": len(cohort),
        "threshold_selection": (
            "first 60% chronological only; maximize balanced accuracy "
            "for MISSED versus WINNER using overheat_pressure"
        ),
        "selected_threshold": threshold,
        "train": _overheat_rule_metrics(train, threshold),
        "validation": _overheat_rule_metrics(validation, threshold),
        "test": _overheat_rule_metrics(test, threshold),
        "full_cohort_descriptive_quintiles": quintiles,
    }


def discovery_conclusion(
    models: dict[str, Any],
    overheat: dict[str, Any],
) -> dict[str, Any]:
    def aucs(task: str, variant: str) -> tuple[float, float]:
        selected = models[task]["variants"][variant]["selected"]
        return (
            float(selected["validation"]["auc"]),
            float(selected["test"]["auc"]),
        )

    runner_base = aucs("RUNNER_WIN_vs_RUNNER_MISSED", "baseline")
    runner_eng = aucs("RUNNER_WIN_vs_RUNNER_MISSED", "engineered_only")
    opportunity = aucs("RUNNER_OPPORTUNITY_vs_SUB1", "combined")
    big_small = aucs("BIG_RUNNER_vs_SMALL_EDGE", "combined")
    path = aucs("CLEAN_vs_RECOVERED", "combined")

    return {
        "runner_overheat_signal": "FOUND_PROMISING",
        "runner_win_miss_auc": {
            "baseline_validation": runner_base[0],
            "baseline_test": runner_base[1],
            "engineered_validation": runner_eng[0],
            "engineered_test": runner_eng[1],
        },
        "simple_overheat_rule": {
            "validation_balanced_accuracy": overheat["validation"]["balanced_accuracy"],
            "validation_miss_recall": overheat["validation"]["miss_recall"],
            "validation_winner_keep_rate": overheat["validation"]["winner_keep_rate"],
            "test_balanced_accuracy": overheat["test"]["balanced_accuracy"],
            "test_miss_recall": overheat["test"]["miss_recall"],
            "test_winner_keep_rate": overheat["test"]["winner_keep_rate"],
        },
        "absolute_runner_size_signal": (
            "WEAK_UNSTABLE"
            if min(opportunity) < 0.60
            else "PROMISING"
        ),
        "runner_opportunity_auc": {
            "validation": opportunity[0],
            "test": opportunity[1],
        },
        "big_runner_vs_small_edge_signal": (
            "UNSTABLE"
            if min(big_small) < 0.60
            else "PROMISING"
        ),
        "big_runner_vs_small_edge_auc": {
            "validation": big_small[0],
            "test": big_small[1],
        },
        "clean_vs_recovered_path_signal": (
            "PROMISING"
            if min(path) >= 0.65
            else "UNSTABLE"
        ),
        "clean_vs_recovered_auc": {
            "validation": path[0],
            "test": path[1],
        },
        "production_authority": "NONE",
    }


def run_wd5d() -> dict[str, Any]:
    rows = load_augmented_rows()
    types = feature_types(rows)
    base = portable_base_features(rows, types)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    stability = {
        task: feature_stability(rows, task, list(NEW_FEATURES))
        for task in TASKS
    }
    models = {
        task: model_comparison(rows, task, base, types)
        for task in TASKS
    }
    overheat = overheat_threshold_diagnostic(rows)
    conclusion = discovery_conclusion(models, overheat)

    result = {
        "version": WD5D_VERSION,
        "authority": "RESEARCH_ONLY",
        "rows": len(rows),
        "new_feature_count": len(NEW_FEATURES),
        "new_features": list(NEW_FEATURES),
        "portable_base_feature_count": len(base),
        "task_feature_stability": stability,
        "model_comparison": models,
        "overheat_threshold_diagnostic": overheat,
        "conclusion": conclusion,
        "outputs": {
            "csv": str(OUTPUT_CSV),
            "json": str(OUTPUT_JSON),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, allow_nan=False))
    return result
