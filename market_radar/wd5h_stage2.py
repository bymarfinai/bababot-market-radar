from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from .wd5b_discovery import Encoder, LogisticModel, auc_score, binary_metrics


WD5H2_VERSION = "wd5h-stage2-hierarchical-win-gate-v1"
INPUT_PATH = Path("/app/data/wd5h1_thesis_labeled_features.csv")
OUTPUT_ROWS = Path("/app/data/wd5h2_selective_gate_predictions.csv")
OUTPUT_JSON = Path("/app/data/wd5h2_selective_gate_results.json")

WIN = "VALID_WINNER"
REJECT_CLASSES = (
    "TRUE_WRONG_DIRECTION",
    "RIGHT_THEN_FAILURE",
    "STALL_NO_EDGE",
)

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


def load_rows() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(INPUT_PATH.open()))
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    if len(rows) != 2175:
        raise RuntimeError(f"expected 2175 rows, got {len(rows)}")
    return rows


def chronological_split(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    n = len(rows)
    train = rows[:3*n//5]
    validation = rows[3*n//5:4*n//5]
    test = rows[4*n//5:]
    return train, validation, test


def portable_feature_types(
    rows: list[dict[str, Any]],
) -> dict[str, str]:
    out = {}
    for key in rows[0]:
        if not key.startswith("f_"):
            continue
        if key in TIME_FEATURES or key in SCALE_PROXY_FEATURES:
            continue
        if key.startswith("f_latency_"):
            continue
        values = {str(r.get(key, "")) for r in rows}
        if len(values) <= 1:
            continue
        numeric = True
        for row in rows[:250]:
            try:
                value = float(row[key])
                if not math.isfinite(value):
                    numeric = False
                    break
            except (TypeError, ValueError):
                numeric = False
                break
        out[key] = "numeric" if numeric else "categorical"
    return out


def _categorical_separation(
    rows: list[dict[str, Any]],
    feature: str,
    target_key: str,
) -> float:
    y = [int(r[target_key]) for r in rows]
    base = sum(y) / len(y)
    groups: dict[str, list[int]] = {}
    for row in rows:
        groups.setdefault(str(row[feature]), []).append(int(row[target_key]))
    weighted = 0.0
    for ys in groups.values():
        rate = sum(ys) / len(ys)
        weighted += len(ys) / len(rows) * abs(rate - base)
    return min(1.0, 2.0 * weighted)


def _numeric_separation(
    rows: list[dict[str, Any]],
    feature: str,
    target_key: str,
) -> float:
    y = [int(r[target_key]) for r in rows]
    p = [float(r[feature]) for r in rows]
    auc = auc_score(y, p)
    return 0.0 if auc is None else abs(float(auc) - 0.5) * 2.0


def rank_features_train_only(
    rows: list[dict[str, Any]],
    features: list[str],
    types: dict[str, str],
    target_key: str,
) -> list[str]:
    ranked = []
    for feature in features:
        sep = (
            _numeric_separation(rows, feature, target_key)
            if types[feature] == "numeric"
            else _categorical_separation(rows, feature, target_key)
        )
        ranked.append((sep, feature))
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [feature for _, feature in ranked]


def add_pair_target(
    rows: list[dict[str, Any]],
    reject_label: str,
) -> list[dict[str, Any]]:
    out = []
    for source in rows:
        label = source["label_thesis_class"]
        if label not in {WIN, reject_label}:
            continue
        row = dict(source)
        row["target_pair_win"] = 1 if label == WIN else 0
        out.append(row)
    return out


def _inner_split(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    n = len(rows)
    cut = max(1, int(n * 0.75))
    return rows[:cut], rows[cut:]


def fit_pairwise_head(
    full_train: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
    reject_label: str,
    features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    cohort = add_pair_target(full_train, reject_label)
    inner_train, inner_val = _inner_split(cohort)
    ordered = rank_features_train_only(
        inner_train, features, types, "target_pair_win"
    )
    y_inner_train = [int(r["target_pair_win"]) for r in inner_train]
    y_inner_val = [int(r["target_pair_win"]) for r in inner_val]

    grid = []
    for k in (5, 10, 20, 40, 60, 80):
        if k > len(ordered):
            continue
        chosen = ordered[:k]
        for l2 in (0.1, 1.0, 4.0):
            encoder = Encoder(chosen, types).fit(inner_train)
            model = LogisticModel(
                l2=l2,
                epochs=700,
                lr=0.12,
            ).fit(
                encoder.transform(inner_train),
                y_inner_train,
            )
            p = model.predict_proba(encoder.transform(inner_val))
            metrics = binary_metrics(y_inner_val, p)
            grid.append({
                "top_k": len(chosen),
                "l2": l2,
                "features": chosen,
                "inner_validation": metrics,
            })
    grid.sort(
        key=lambda x: (
            x["inner_validation"]["auc"]
            if x["inner_validation"]["auc"] is not None else -1.0,
            x["inner_validation"]["balanced_accuracy"]
            if x["inner_validation"]["balanced_accuracy"] is not None
            else -1.0,
            -x["top_k"],
        ),
        reverse=True,
    )
    selected = grid[0]

    # Re-rank strictly on full training data using only the chosen top-k count.
    full_cohort = add_pair_target(full_train, reject_label)
    full_ordered = rank_features_train_only(
        full_cohort, features, types, "target_pair_win"
    )
    chosen = full_ordered[:selected["top_k"]]
    encoder = Encoder(chosen, types).fit(full_cohort)
    model = LogisticModel(
        l2=float(selected["l2"]),
        epochs=700,
        lr=0.12,
    ).fit(
        encoder.transform(full_cohort),
        [int(r["target_pair_win"]) for r in full_cohort],
    )

    return {
        "reject_label": reject_label,
        "train_pair_n": len(full_cohort),
        "train_pair_classes": dict(Counter(
            r["label_thesis_class"] for r in full_cohort
        )),
        "inner_train_n": len(inner_train),
        "inner_validation_n": len(inner_val),
        "selected_top_k": len(chosen),
        "selected_l2": float(selected["l2"]),
        "selected_features": chosen,
        "inner_validation": selected["inner_validation"],
        "_encoder": encoder,
        "_model": model,
    }


def fit_flat_baseline(
    full_train: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
    features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    train = []
    for source in full_train:
        row = dict(source)
        row["target_flat_win"] = int(
            row["label_thesis_class"] == WIN
        )
        train.append(row)
    inner_train, inner_val = _inner_split(train)
    ordered = rank_features_train_only(
        inner_train, features, types, "target_flat_win"
    )
    grid = []
    for k in (5, 10, 20, 40, 60, 80):
        if k > len(ordered):
            continue
        chosen = ordered[:k]
        for l2 in (0.1, 1.0, 4.0):
            encoder = Encoder(chosen, types).fit(inner_train)
            model = LogisticModel(
                l2=l2, epochs=700, lr=0.12
            ).fit(
                encoder.transform(inner_train),
                [int(r["target_flat_win"]) for r in inner_train],
            )
            p = model.predict_proba(encoder.transform(inner_val))
            metrics = binary_metrics(
                [int(r["target_flat_win"]) for r in inner_val],
                p,
            )
            grid.append({
                "top_k": len(chosen),
                "l2": l2,
                "features": chosen,
                "inner_validation": metrics,
            })
    grid.sort(
        key=lambda x: (
            x["inner_validation"]["auc"]
            if x["inner_validation"]["auc"] is not None else -1.0,
            x["inner_validation"]["balanced_accuracy"]
            if x["inner_validation"]["balanced_accuracy"] is not None
            else -1.0,
            -x["top_k"],
        ),
        reverse=True,
    )
    selected = grid[0]

    full_ordered = rank_features_train_only(
        train, features, types, "target_flat_win"
    )
    chosen = full_ordered[:selected["top_k"]]
    encoder = Encoder(chosen, types).fit(train)
    model = LogisticModel(
        l2=float(selected["l2"]),
        epochs=700,
        lr=0.12,
    ).fit(
        encoder.transform(train),
        [int(r["target_flat_win"]) for r in train],
    )
    return {
        "selected_top_k": len(chosen),
        "selected_l2": float(selected["l2"]),
        "selected_features": chosen,
        "inner_validation": selected["inner_validation"],
        "_encoder": encoder,
        "_model": model,
    }


def score_rows(
    rows: list[dict[str, Any]],
    heads: dict[str, dict[str, Any]],
    flat: dict[str, Any],
) -> list[dict[str, Any]]:
    scored = []
    flat_scores = flat["_model"].predict_proba(
        flat["_encoder"].transform(rows)
    )
    head_scores = {
        label: head["_model"].predict_proba(
            head["_encoder"].transform(rows)
        )
        for label, head in heads.items()
    }
    for i, source in enumerate(rows):
        row = dict(source)
        for label in REJECT_CLASSES:
            row[f"score_win_vs_{label.lower()}"] = head_scores[label][i]
        row["score_hierarchical_min"] = min(
            head_scores[label][i] for label in REJECT_CLASSES
        )
        row["score_flat_win"] = flat_scores[i]
        scored.append(row)
    return scored


def gate_metrics(
    rows: list[dict[str, Any]],
    take_mask: list[bool],
) -> dict[str, Any]:
    taken = [r for r, take in zip(rows, take_mask) if take]
    take_n = len(taken)
    winner_n = sum(r["label_thesis_class"] == WIN for r in taken)
    realized_win_n = sum(
        float(r["future_realized_pnl"]) > 0 for r in taken
    )
    pnl = sum(float(r["future_realized_pnl"]) for r in taken)
    duration_days = None
    if rows:
        span_ms = (
            int(rows[-1]["meta_opened_at_ms"])
            - int(rows[0]["meta_opened_at_ms"])
        )
        duration_days = max(span_ms / 86_400_000.0, 1.0 / 24.0)

    runner_rows = [
        r for r in rows
        if r["label_opportunity_tier"] in {"RUNNER", "BIG_RUNNER"}
        and r["label_thesis_class"] == WIN
    ]
    runner_ids = {r["meta_position_id"] for r in runner_rows}
    runner_taken = sum(
        r["meta_position_id"] in runner_ids for r in taken
    )

    big_rows = [
        r for r in rows
        if r["label_opportunity_tier"] == "BIG_RUNNER"
        and r["label_thesis_class"] == WIN
    ]
    big_ids = {r["meta_position_id"] for r in big_rows}
    big_taken = sum(
        r["meta_position_id"] in big_ids for r in taken
    )

    return {
        "candidate_n": len(rows),
        "take_n": take_n,
        "coverage_pct": 100.0 * take_n / len(rows) if rows else None,
        "thesis_winner_n": winner_n,
        "thesis_win_precision_pct": (
            100.0 * winner_n / take_n if take_n else None
        ),
        "realized_positive_n": realized_win_n,
        "realized_win_rate_pct": (
            100.0 * realized_win_n / take_n if take_n else None
        ),
        "net_pnl": pnl,
        "avg_pnl_per_trade": pnl / take_n if take_n else None,
        "trade_per_day": (
            take_n / duration_days if duration_days else None
        ),
        "class_counts": dict(Counter(
            r["label_thesis_class"] for r in taken
        )),
        "runner_valid_n": len(runner_rows),
        "runner_valid_taken_n": runner_taken,
        "runner_valid_retention_pct": (
            100.0 * runner_taken / len(runner_rows)
            if runner_rows else None
        ),
        "big_runner_valid_n": len(big_rows),
        "big_runner_valid_taken_n": big_taken,
        "big_runner_valid_retention_pct": (
            100.0 * big_taken / len(big_rows)
            if big_rows else None
        ),
    }


def _quantile_values(
    values: list[float],
    quantiles: list[float],
) -> list[float]:
    xs = sorted(values)
    out = set()
    for q in quantiles:
        idx = int(q * (len(xs) - 1))
        out.add(xs[idx])
    out.add(min(xs))
    out.add(max(xs))
    return sorted(out)


def search_hierarchical_frontier(
    validation: list[dict[str, Any]],
) -> dict[str, Any]:
    quantiles = [
        0.20, 0.30, 0.40, 0.50, 0.60,
        0.70, 0.75, 0.80, 0.85, 0.90,
        0.925, 0.95,
    ]
    candidates = {
        label: _quantile_values(
            [
                float(r[f"score_win_vs_{label.lower()}"])
                for r in validation
            ],
            quantiles,
        )
        for label in REJECT_CLASSES
    }
    min_take = max(10, math.ceil(0.05 * len(validation)))
    evaluated = []
    for t_tw in candidates["TRUE_WRONG_DIRECTION"]:
        for t_rtf in candidates["RIGHT_THEN_FAILURE"]:
            for t_stall in candidates["STALL_NO_EDGE"]:
                thresholds = {
                    "TRUE_WRONG_DIRECTION": t_tw,
                    "RIGHT_THEN_FAILURE": t_rtf,
                    "STALL_NO_EDGE": t_stall,
                }
                mask = [
                    all(
                        float(r[f"score_win_vs_{label.lower()}"])
                        >= thresholds[label]
                        for label in REJECT_CLASSES
                    )
                    for r in validation
                ]
                metrics = gate_metrics(validation, mask)
                if metrics["take_n"] < min_take:
                    continue
                evaluated.append({
                    "thresholds": thresholds,
                    "metrics": metrics,
                })

    floors = [60, 65, 70, 75, 80, 85, 90]
    frontier = {}
    for floor in floors:
        eligible = [
            x for x in evaluated
            if x["metrics"]["thesis_win_precision_pct"] is not None
            and x["metrics"]["thesis_win_precision_pct"] >= floor
        ]
        if not eligible:
            frontier[str(floor)] = None
            continue
        eligible.sort(
            key=lambda x: (
                x["metrics"]["take_n"],
                x["metrics"]["net_pnl"],
                x["metrics"]["thesis_win_precision_pct"],
            ),
            reverse=True,
        )
        frontier[str(floor)] = eligible[0]

    feasible_floors = [
        floor for floor in floors
        if frontier[str(floor)] is not None
    ]
    if feasible_floors:
        selected_floor = max(feasible_floors)
        selected = frontier[str(selected_floor)]
    else:
        evaluated.sort(
            key=lambda x: (
                x["metrics"]["thesis_win_precision_pct"]
                if x["metrics"]["thesis_win_precision_pct"] is not None
                else -1.0,
                x["metrics"]["take_n"],
                x["metrics"]["net_pnl"],
            ),
            reverse=True,
        )
        selected_floor = None
        selected = evaluated[0]

    return {
        "min_validation_take_n": min_take,
        "candidate_threshold_count": len(evaluated),
        "precision_frontier": frontier,
        "selected_precision_floor": selected_floor,
        "selected": selected,
    }


def search_flat_frontier(
    validation: list[dict[str, Any]],
) -> dict[str, Any]:
    scores = [float(r["score_flat_win"]) for r in validation]
    thresholds = _quantile_values(
        scores,
        [
            0.20, 0.30, 0.40, 0.50, 0.60,
            0.70, 0.75, 0.80, 0.85, 0.90,
            0.925, 0.95, 0.97,
        ],
    )
    min_take = max(10, math.ceil(0.05 * len(validation)))
    evaluated = []
    for threshold in thresholds:
        mask = [
            float(r["score_flat_win"]) >= threshold
            for r in validation
        ]
        metrics = gate_metrics(validation, mask)
        if metrics["take_n"] >= min_take:
            evaluated.append({
                "threshold": threshold,
                "metrics": metrics,
            })

    floors = [60, 65, 70, 75, 80, 85, 90]
    frontier = {}
    for floor in floors:
        eligible = [
            x for x in evaluated
            if x["metrics"]["thesis_win_precision_pct"] is not None
            and x["metrics"]["thesis_win_precision_pct"] >= floor
        ]
        if not eligible:
            frontier[str(floor)] = None
            continue
        eligible.sort(
            key=lambda x: (
                x["metrics"]["take_n"],
                x["metrics"]["net_pnl"],
                x["metrics"]["thesis_win_precision_pct"],
            ),
            reverse=True,
        )
        frontier[str(floor)] = eligible[0]

    feasible = [
        floor for floor in floors
        if frontier[str(floor)] is not None
    ]
    if feasible:
        floor = max(feasible)
        selected = frontier[str(floor)]
    else:
        evaluated.sort(
            key=lambda x: (
                x["metrics"]["thesis_win_precision_pct"]
                if x["metrics"]["thesis_win_precision_pct"] is not None
                else -1.0,
                x["metrics"]["take_n"],
            ),
            reverse=True,
        )
        floor = None
        selected = evaluated[0]

    return {
        "min_validation_take_n": min_take,
        "selected_precision_floor": floor,
        "precision_frontier": frontier,
        "selected": selected,
    }


def apply_hierarchical_thresholds(
    rows: list[dict[str, Any]],
    thresholds: dict[str, float],
) -> list[bool]:
    return [
        all(
            float(r[f"score_win_vs_{label.lower()}"])
            >= float(thresholds[label])
            for label in REJECT_CLASSES
        )
        for r in rows
    ]


def apply_flat_threshold(
    rows: list[dict[str, Any]],
    threshold: float,
) -> list[bool]:
    return [
        float(r["score_flat_win"]) >= threshold
        for r in rows
    ]


def pairwise_diagnostics(
    rows: list[dict[str, Any]],
    heads: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    out = {}
    for reject_label in REJECT_CLASSES:
        cohort = [
            r for r in rows
            if r["label_thesis_class"] in {WIN, reject_label}
        ]
        y = [
            int(r["label_thesis_class"] == WIN)
            for r in cohort
        ]
        p = [
            float(r[f"score_win_vs_{reject_label.lower()}"])
            for r in cohort
        ]
        out[reject_label] = {
            "n": len(cohort),
            "class_counts": dict(Counter(
                r["label_thesis_class"] for r in cohort
            )),
            "metrics": binary_metrics(y, p),
        }
    return out


def novel_symbol_metrics(
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    test: list[dict[str, Any]],
    mask: list[bool],
) -> dict[str, Any]:
    seen = {
        r["meta_symbol"] for r in train + validation
    }
    idx = [
        i for i, r in enumerate(test)
        if r["meta_symbol"] not in seen
    ]
    rows = [test[i] for i in idx]
    take = [mask[i] for i in idx]
    return {
        "n": len(rows),
        "unique_symbols": len({r["meta_symbol"] for r in rows}),
        "metrics": gate_metrics(rows, take) if rows else None,
    }


def assessment(
    validation_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    flat_test: dict[str, Any],
) -> dict[str, Any]:
    requirements = {
        "validation_precision_ge_70": (
            validation_metrics["thesis_win_precision_pct"] is not None
            and validation_metrics["thesis_win_precision_pct"] >= 70.0
        ),
        "test_precision_ge_65": (
            test_metrics["thesis_win_precision_pct"] is not None
            and test_metrics["thesis_win_precision_pct"] >= 65.0
        ),
        "test_take_n_ge_10": test_metrics["take_n"] >= 10,
        "test_net_pnl_positive": test_metrics["net_pnl"] > 0,
        "test_precision_not_worse_than_flat": (
            flat_test["thesis_win_precision_pct"] is None
            or test_metrics["thesis_win_precision_pct"]
            >= flat_test["thesis_win_precision_pct"]
        ),
    }
    return {
        "status": (
            "HIGH_PRECISION_WIN_GATE_CANDIDATE"
            if all(requirements.values())
            else "HIGH_PRECISION_WIN_GATE_NOT_READY"
        ),
        "requirements": requirements,
        "production_authority": "NONE",
    }


def run_wd5h_stage2() -> dict[str, Any]:
    rows = load_rows()
    train, validation, test = chronological_split(rows)
    types = portable_feature_types(train)
    features = sorted(types)

    heads = {
        reject_label: fit_pairwise_head(
            train,
            rows,
            reject_label,
            features,
            types,
        )
        for reject_label in REJECT_CLASSES
    }
    flat = fit_flat_baseline(
        train, rows, features, types
    )

    scored_train = score_rows(train, heads, flat)
    scored_val = score_rows(validation, heads, flat)
    scored_test = score_rows(test, heads, flat)

    hierarchy_search = search_hierarchical_frontier(scored_val)
    thresholds = hierarchy_search["selected"]["thresholds"]
    val_mask = apply_hierarchical_thresholds(
        scored_val, thresholds
    )
    test_mask = apply_hierarchical_thresholds(
        scored_test, thresholds
    )
    validation_metrics = gate_metrics(scored_val, val_mask)
    test_metrics = gate_metrics(scored_test, test_mask)

    flat_search = search_flat_frontier(scored_val)
    flat_threshold = float(flat_search["selected"]["threshold"])
    flat_val_mask = apply_flat_threshold(scored_val, flat_threshold)
    flat_test_mask = apply_flat_threshold(scored_test, flat_threshold)
    flat_val_metrics = gate_metrics(scored_val, flat_val_mask)
    flat_test_metrics = gate_metrics(scored_test, flat_test_mask)

    # Persist scores + actions for all three chronological partitions.
    output = []
    for split_name, split_rows, hmask, fmask in (
        ("TRAIN", scored_train, [False] * len(scored_train), [False] * len(scored_train)),
        ("VALIDATION", scored_val, val_mask, flat_val_mask),
        ("TEST", scored_test, test_mask, flat_test_mask),
    ):
        for i, row in enumerate(split_rows):
            record = {
                "split": split_name,
                "position_id": row["meta_position_id"],
                "symbol": row["meta_symbol"],
                "opened_at_ms": row["meta_opened_at_ms"],
                "thesis_class": row["label_thesis_class"],
                "opportunity_tier": row["label_opportunity_tier"],
                "realized_pnl": row["future_realized_pnl"],
                "score_win_vs_true_wrong": row[
                    "score_win_vs_true_wrong_direction"
                ],
                "score_win_vs_rtf": row[
                    "score_win_vs_right_then_failure"
                ],
                "score_win_vs_stall": row[
                    "score_win_vs_stall_no_edge"
                ],
                "score_hierarchical_min": row[
                    "score_hierarchical_min"
                ],
                "score_flat_win": row["score_flat_win"],
                "hierarchical_take": (
                    hmask[i] if split_name != "TRAIN" else ""
                ),
                "flat_take": (
                    fmask[i] if split_name != "TRAIN" else ""
                ),
            }
            output.append(record)

    OUTPUT_ROWS.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_ROWS.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(output[0].keys())
        )
        writer.writeheader()
        writer.writerows(output)

    head_summary = {}
    for label, head in heads.items():
        head_summary[label] = {
            k: v for k, v in head.items()
            if not k.startswith("_")
        }

    novel = novel_symbol_metrics(
        train, validation, test, test_mask
    )

    result = {
        "version": WD5H2_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "split": {
            "train_n": len(train),
            "validation_n": len(validation),
            "test_n": len(test),
            "train_classes": dict(Counter(
                r["label_thesis_class"] for r in train
            )),
            "validation_classes": dict(Counter(
                r["label_thesis_class"] for r in validation
            )),
            "test_classes": dict(Counter(
                r["label_thesis_class"] for r in test
            )),
        },
        "feature_count": len(features),
        "heads": head_summary,
        "pairwise_validation": pairwise_diagnostics(
            scored_val, heads
        ),
        "pairwise_test": pairwise_diagnostics(
            scored_test, heads
        ),
        "hierarchical_gate": {
            "threshold_search": hierarchy_search,
            "selected_thresholds": thresholds,
            "validation": validation_metrics,
            "test": test_metrics,
            "novel_symbol_test": novel,
        },
        "flat_baseline": {
            "model": {
                k: v for k, v in flat.items()
                if not k.startswith("_")
            },
            "threshold_search": flat_search,
            "selected_threshold": flat_threshold,
            "validation": flat_val_metrics,
            "test": flat_test_metrics,
        },
        "assessment": assessment(
            validation_metrics,
            test_metrics,
            flat_test_metrics,
        ),
        "outputs": {
            "predictions": str(OUTPUT_ROWS),
            "json": str(OUTPUT_JSON),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(
        result, indent=2, allow_nan=False
    ))
    return result
