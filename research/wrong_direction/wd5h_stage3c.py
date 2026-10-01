from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from research.wrong_direction.wd5h_stage3b import (
    ARCHITECTURES,
    LABEL_PATH,
    TIMEOUT,
    WIN,
    LOSS,
    architecture_is_weighted,
    fit_model,
    load_joined_rows,
    population_splits,
    portable_feature_types,
    rank_features,
    resolved,
    target,
    architecture_train_rows,
)

WD5H3C_VERSION = "wd5h-stage3c-high-precision-abstention-v1"
STAGE3B_JSON = Path("/app/data/wd5h3b_meta_model_results.json")
OUTPUT_CSV = Path("/app/data/wd5h3c_take_abstain_predictions.csv")
OUTPUT_JSON = Path("/app/data/wd5h3c_take_abstain_results.json")

PRIMARY_ARCHITECTURE = "BASELINE_UNPURGED_UNWEIGHTED"
DIAGNOSTIC_ARCHITECTURE = "PURGED_UNIQUENESS_WEIGHTED"
PRECISION_FLOORS = (0.50, 0.60, 0.65, 0.70, 0.75, 0.80)
MIN_USABLE_RESOLVED_TAKES = 10
MIN_DIAGNOSTIC_RESOLVED_TAKES = 3


def score_model_from_outer_train(
    architecture: str,
    rows: list[dict[str, Any]],
    stage3b: dict[str, Any],
) -> dict[str, Any]:
    splits = population_splits(rows)
    inner_selected = stage3b["hyperparameters"][architecture]["selected"]
    top_k = int(inner_selected["top_k"])
    l2 = float(inner_selected["l2"])

    all_resolved_train = resolved(splits["outer_train_pool"])
    feature_types = portable_feature_types(
        resolved(splits["inner_train_pool"])
    )
    features = sorted(feature_types)

    train_rows, purge_info = architecture_train_rows(
        architecture,
        splits["outer_train_pool"],
        splits["outer_val_pool"],
    )
    ranking = rank_features(train_rows, features, feature_types)
    selected_features = ranking[:top_k]

    model, encoder, val_probs_resolved = fit_model(
        train_rows,
        resolved(splits["outer_val_pool"]),
        selected_features,
        feature_types,
        l2,
        weighted=architecture_is_weighted(architecture),
    )

    val_all = splits["outer_val_pool"]
    test_all = splits["test_pool"]
    val_all_probs = model.predict_proba(encoder.transform(val_all))
    test_all_probs = model.predict_proba(encoder.transform(test_all))

    return {
        "architecture": architecture,
        "top_k": top_k,
        "l2": l2,
        "features": selected_features,
        "train_n": len(train_rows),
        "unpurged_train_resolved_n": len(all_resolved_train),
        "purge": purge_info,
        "validation_rows": val_all,
        "validation_probs": val_all_probs,
        "test_rows": test_all,
        "test_probs": test_all_probs,
    }


def elapsed_days(rows: list[dict[str, Any]]) -> float:
    if len(rows) < 2:
        return 0.0
    start = min(int(r["meta_opened_at_ms"]) for r in rows)
    end = max(int(r["meta_opened_at_ms"]) for r in rows)
    return max(1.0 / 1440.0, (end - start) / 86_400_000.0)


def threshold_metrics(
    rows: list[dict[str, Any]],
    probs: list[float],
    threshold: float,
) -> dict[str, Any]:
    chosen = [
        (r, p) for r, p in zip(rows, probs)
        if p >= threshold
    ]
    resolved_chosen = [
        (r, p) for r, p in chosen
        if r["primary_meta_label"] in {WIN, LOSS}
    ]
    wins = sum(
        r["primary_meta_label"] == WIN
        for r, _ in resolved_chosen
    )
    losses = sum(
        r["primary_meta_label"] == LOSS
        for r, _ in resolved_chosen
    )
    timeouts = sum(
        r["primary_meta_label"] == TIMEOUT
        for r, _ in chosen
    )
    resolved_n = wins + losses
    precision = wins / resolved_n if resolved_n else None
    days = elapsed_days(rows)
    # Symmetric +0.5/-0.5 barrier-unit expectancy on resolved labels.
    barrier_unit_net = wins - losses
    timeout_30m_net = sum(
        float(r["primary_final_net_usdt"])
        for r, _ in chosen
        if r["primary_meta_label"] == TIMEOUT
    )
    standardized_net_usdt = (
        barrier_unit_net * 2.5 + timeout_30m_net
    )
    return {
        "threshold": threshold,
        "candidate_n": len(rows),
        "take_all_n": len(chosen),
        "take_resolved_n": resolved_n,
        "meta_win_n": wins,
        "meta_loss_n": losses,
        "timeout_n": timeouts,
        "resolved_precision_pct": (
            100.0 * precision if precision is not None else None
        ),
        "coverage_all_pct": (
            100.0 * len(chosen) / len(rows) if rows else None
        ),
        "coverage_resolved_pct": (
            100.0 * resolved_n /
            sum(r["primary_meta_label"] in {WIN, LOSS} for r in rows)
            if rows else None
        ),
        "take_per_24h_window": (
            len(chosen) / days if days else None
        ),
        "resolved_take_per_24h_window": (
            resolved_n / days if days else None
        ),
        "standardized_barrier_net_usdt": standardized_net_usdt,
        "standardized_barrier_net_per_take_usdt": (
            standardized_net_usdt / len(chosen)
            if chosen else None
        ),
        "score_min_taken": min(
            (p for _, p in chosen), default=None
        ),
        "score_max_taken": max(
            (p for _, p in chosen), default=None
        ),
    }


def validation_frontier(
    rows: list[dict[str, Any]],
    probs: list[float],
    min_resolved_takes: int,
) -> list[dict[str, Any]]:
    thresholds = sorted(
        {float(p) for p in probs},
        reverse=True,
    )
    out = []
    for t in thresholds:
        m = threshold_metrics(rows, probs, t)
        if m["take_resolved_n"] < min_resolved_takes:
            continue
        out.append(m)
    return out


def choose_for_floor(
    frontier: list[dict[str, Any]],
    floor: float,
) -> dict[str, Any] | None:
    eligible = [
        m for m in frontier
        if m["resolved_precision_pct"] is not None
        and m["resolved_precision_pct"] >= 100.0 * floor
    ]
    if not eligible:
        return None
    eligible.sort(
        key=lambda m: (
            m["take_resolved_n"],
            m["resolved_precision_pct"],
            m["threshold"],
        ),
        reverse=True,
    )
    return eligible[0]


def best_precision(
    frontier: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not frontier:
        return None
    return max(
        frontier,
        key=lambda m: (
            m["resolved_precision_pct"]
            if m["resolved_precision_pct"] is not None
            else -1.0,
            m["take_resolved_n"],
        ),
    )


def apply_selected_thresholds(
    validation_rows: list[dict[str, Any]],
    validation_probs: list[float],
    test_rows: list[dict[str, Any]],
    test_probs: list[float],
) -> dict[str, Any]:
    usable_frontier = validation_frontier(
        validation_rows,
        validation_probs,
        MIN_USABLE_RESOLVED_TAKES,
    )
    diagnostic_frontier = validation_frontier(
        validation_rows,
        validation_probs,
        MIN_DIAGNOSTIC_RESOLVED_TAKES,
    )

    floors = {}
    for floor in PRECISION_FLOORS:
        val_pick = choose_for_floor(usable_frontier, floor)
        floors[str(int(100 * floor))] = {
            "validation": val_pick,
            "test": (
                threshold_metrics(
                    test_rows, test_probs, val_pick["threshold"]
                )
                if val_pick else None
            ),
        }

    best_usable = best_precision(usable_frontier)
    best_diag = best_precision(diagnostic_frontier)

    return {
        "precision_floors": floors,
        "best_usable_validation": best_usable,
        "best_usable_test": (
            threshold_metrics(
                test_rows,
                test_probs,
                best_usable["threshold"],
            )
            if best_usable else None
        ),
        "best_ultraselective_validation": best_diag,
        "best_ultraselective_test": (
            threshold_metrics(
                test_rows,
                test_probs,
                best_diag["threshold"],
            )
            if best_diag else None
        ),
        "usable_frontier_n": len(usable_frontier),
        "diagnostic_frontier_n": len(diagnostic_frontier),
    }


def prediction_rows(
    model_bundle: dict[str, Any],
    selected_threshold: float | None,
    kind: str,
) -> list[dict[str, Any]]:
    out = []
    for split, rows_key, probs_key in (
        ("validation", "validation_rows", "validation_probs"),
        ("test", "test_rows", "test_probs"),
    ):
        rows = model_bundle[rows_key]
        probs = model_bundle[probs_key]
        for row, p in zip(rows, probs):
            out.append({
                "kind": kind,
                "architecture": model_bundle["architecture"],
                "split": split,
                "position_id": row["meta_position_id"],
                "symbol": row["meta_symbol"],
                "side": row["meta_original_side"],
                "opened_at_ms": row["meta_opened_at_ms"],
                "primary_meta_label": row["primary_meta_label"],
                "score_meta_win": p,
                "selected_threshold": selected_threshold,
                "take": (
                    bool(
                        selected_threshold is not None
                        and p >= selected_threshold
                    )
                ),
            })
    return out


def run_wd5h_stage3c() -> dict[str, Any]:
    stage3b = json.loads(STAGE3B_JSON.read_text())
    if stage3b["selected_architecture"] != PRIMARY_ARCHITECTURE:
        raise RuntimeError(
            "Stage3B selected architecture changed; "
            "Stage3C primary freeze invalid"
        )

    rows = load_joined_rows()
    label_rows = {
        r["position_id"]: r
        for r in csv.DictReader(LABEL_PATH.open())
    }
    for row in rows:
        lab = label_rows[row["meta_position_id"]]
        row["primary_final_net_usdt"] = float(
            lab["primary_final_net_usdt"]
        )

    primary = score_model_from_outer_train(
        PRIMARY_ARCHITECTURE,
        rows,
        stage3b,
    )
    sensitivity = score_model_from_outer_train(
        DIAGNOSTIC_ARCHITECTURE,
        rows,
        stage3b,
    )

    primary_result = apply_selected_thresholds(
        primary["validation_rows"],
        primary["validation_probs"],
        primary["test_rows"],
        primary["test_probs"],
    )
    sensitivity_result = apply_selected_thresholds(
        sensitivity["validation_rows"],
        sensitivity["validation_probs"],
        sensitivity["test_rows"],
        sensitivity["test_probs"],
    )

    feasible_70 = primary_result["precision_floors"]["70"][
        "validation"
    ]
    best_usable = primary_result["best_usable_validation"]
    best_test = primary_result["best_usable_test"]

    status = "STATIC_HIGH_PRECISION_GATE_NOT_READY"
    if (
        feasible_70 is not None
        and primary_result["precision_floors"]["70"]["test"] is not None
        and primary_result["precision_floors"]["70"]["test"][
            "resolved_precision_pct"
        ] is not None
        and primary_result["precision_floors"]["70"]["test"][
            "resolved_precision_pct"
        ] >= 65.0
        and primary_result["precision_floors"]["70"]["test"][
            "take_resolved_n"
        ] >= MIN_USABLE_RESOLVED_TAKES
    ):
        status = "STATIC_HIGH_PRECISION_GATE_PROMISING"

    primary_threshold = (
        best_usable["threshold"]
        if best_usable is not None else None
    )
    pred = (
        prediction_rows(
            primary, primary_threshold, "PRIMARY"
        )
        + prediction_rows(
            sensitivity,
            sensitivity_result["best_usable_validation"][
                "threshold"
            ]
            if sensitivity_result["best_usable_validation"]
            else None,
            "DIAGNOSTIC_SENSITIVITY",
        )
    )
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(pred[0].keys())
        )
        writer.writeheader()
        writer.writerows(pred)

    result = {
        "version": WD5H3C_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "method": {
            "primary_architecture": PRIMARY_ARCHITECTURE,
            "diagnostic_architecture": DIAGNOSTIC_ARCHITECTURE,
            "model_training_window": (
                "Stage3B outer-train first 60%; "
                "same frozen inner-selected top-k/L2"
            ),
            "threshold_selection_window": (
                "Stage3B outer-validation 60-80%"
            ),
            "test_window": "final 20%",
            "precision_floors_pct": [
                int(100 * x) for x in PRECISION_FLOORS
            ],
            "minimum_usable_resolved_takes": (
                MIN_USABLE_RESOLVED_TAKES
            ),
            "minimum_ultraselective_resolved_takes": (
                MIN_DIAGNOSTIC_RESOLVED_TAKES
            ),
            "important_limitation": (
                "Stage3B aggregate final-test performance was already "
                "observed before Stage3C. Stage3C does not use final-test "
                "labels to choose thresholds, but this is historical "
                "robustness evidence rather than a pristine promotion test."
            ),
        },
        "primary_model": {
            "architecture": primary["architecture"],
            "top_k": primary["top_k"],
            "l2": primary["l2"],
            "features": primary["features"],
            "train_n": primary["train_n"],
            "purge": primary["purge"],
            "frontier": primary_result,
        },
        "diagnostic_weighted_sensitivity": {
            "architecture": sensitivity["architecture"],
            "top_k": sensitivity["top_k"],
            "l2": sensitivity["l2"],
            "features": sensitivity["features"],
            "train_n": sensitivity["train_n"],
            "purge": sensitivity["purge"],
            "frontier": sensitivity_result,
            "promotion_eligible": False,
        },
        "assessment": {
            "status": status,
            "validation_70pct_floor_feasible": (
                feasible_70 is not None
            ),
            "best_usable_validation_precision_pct": (
                best_usable["resolved_precision_pct"]
                if best_usable else None
            ),
            "best_usable_validation_resolved_takes": (
                best_usable["take_resolved_n"]
                if best_usable else 0
            ),
            "same_threshold_test_precision_pct": (
                best_test["resolved_precision_pct"]
                if best_test else None
            ),
            "same_threshold_test_resolved_takes": (
                best_test["take_resolved_n"]
                if best_test else 0
            ),
            "production_authority": "NONE",
            "next_if_fail": (
                "Stop static pre-entry meta-label path and move to "
                "causal 1-3 minute confirmation window."
            ),
        },
        "outputs": {
            "predictions": str(OUTPUT_CSV),
            "json": str(OUTPUT_JSON),
        },
    }

    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, allow_nan=False)
    )
    return result
