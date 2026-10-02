from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from .wd5b_discovery import Encoder
from .wd5h_stage3b import WeightedLogisticModel
from .wd5h_stage4b import (
    LABEL_LOSS,
    LABEL_WIN,
    chronological_splits,
    load_rows,
    survivor_rows,
    y,
)

WD5H4C_VERSION = "wd5h-stage4c-high-precision-temporal-gate-v1"

STAGE4B_JSON = Path("/app/data/wd5h4b_temporal_pattern_results.json")
OUTPUT_JSON = Path("/app/data/wd5h4c_temporal_gate_results.json")
OUTPUT_CSV = Path("/app/data/wd5h4c_temporal_gate_predictions.csv")

HORIZONS = (1, 2, 3)
TIMEOUT = "TIMEOUT"
PRECISION_FLOORS = (0.60, 0.65, 0.70, 0.75, 0.80)
MIN_RESOLVED_TAKES = 10
MODEL_L2 = 1.0


def eligible_all(
    rows: list[dict[str, Any]],
    horizon: int,
) -> list[dict[str, Any]]:
    target_key = f"t{horizon}_target_ms"
    return [
        r for r in rows
        if int(r["primary_label_end_ms"]) > int(r[target_key])
    ]


def elapsed_days(rows: list[dict[str, Any]]) -> float:
    if len(rows) < 2:
        return 1.0 / 1440.0
    start = min(int(r["gate_checked_at_ms"]) for r in rows)
    end = max(int(r["gate_checked_at_ms"]) for r in rows)
    return max(1.0 / 1440.0, (end - start) / 86_400_000.0)


def build_fixed_model(
    train_rows: list[dict[str, Any]],
    features: list[str],
) -> tuple[WeightedLogisticModel, Encoder]:
    train = train_rows
    types = {f: "numeric" for f in features}
    enc = Encoder(features, types).fit(train)
    model = WeightedLogisticModel(
        l2=MODEL_L2,
        epochs=700,
        lr=0.12,
    ).fit(
        enc.transform(train),
        [y(r) for r in train],
        None,
    )
    return model, enc


def threshold_metrics(
    rows: list[dict[str, Any]],
    probs: list[float],
    threshold: float,
) -> dict[str, Any]:
    chosen = [(r, p) for r, p in zip(rows, probs) if p >= threshold]
    wins = sum(r["primary_meta_label"] == LABEL_WIN for r, _ in chosen)
    losses = sum(r["primary_meta_label"] == LABEL_LOSS for r, _ in chosen)
    timeouts = sum(r["primary_meta_label"] == TIMEOUT for r, _ in chosen)
    resolved_n = wins + losses
    precision = wins / resolved_n if resolved_n else None
    all_win_rate = wins / len(chosen) if chosen else None
    timeout_rate = timeouts / len(chosen) if chosen else None
    days = elapsed_days(rows)

    return {
        "threshold": threshold,
        "eligible_n": len(rows),
        "take_n": len(chosen),
        "resolved_take_n": resolved_n,
        "meta_win_n": wins,
        "meta_loss_n": losses,
        "timeout_n": timeouts,
        "resolved_precision_pct": (
            100.0 * precision if precision is not None else None
        ),
        "all_take_win_rate_pct": (
            100.0 * all_win_rate if all_win_rate is not None else None
        ),
        "timeout_rate_pct": (
            100.0 * timeout_rate if timeout_rate is not None else None
        ),
        "coverage_pct": (
            100.0 * len(chosen) / len(rows) if rows else None
        ),
        "take_per_24h_window": (
            len(chosen) / days if days else None
        ),
        "resolved_take_per_24h_window": (
            resolved_n / days if days else None
        ),
        "score_min_taken": min((p for _, p in chosen), default=None),
        "score_max_taken": max((p for _, p in chosen), default=None),
    }


def frontier(
    rows: list[dict[str, Any]],
    probs: list[float],
) -> list[dict[str, Any]]:
    thresholds = sorted({float(p) for p in probs}, reverse=True)
    out = []
    for t in thresholds:
        m = threshold_metrics(rows, probs, t)
        if m["resolved_take_n"] < MIN_RESOLVED_TAKES:
            continue
        out.append(m)
    return out


def choose_for_floor(
    points: list[dict[str, Any]],
    floor: float,
) -> dict[str, Any] | None:
    eligible = [
        m for m in points
        if m["resolved_precision_pct"] is not None
        and m["resolved_precision_pct"] >= 100.0 * floor
    ]
    if not eligible:
        return None
    eligible.sort(
        key=lambda m: (
            m["resolved_take_n"],
            -m["timeout_rate_pct"] if m["timeout_rate_pct"] is not None else -100.0,
            m["all_take_win_rate_pct"] if m["all_take_win_rate_pct"] is not None else -1.0,
            -m["threshold"],
        ),
        reverse=True,
    )
    return eligible[0]


def fit_score_horizon(
    rows: list[dict[str, Any]],
    stage4b: dict[str, Any],
    horizon: int,
) -> dict[str, Any]:
    splits = chronological_splits(rows)
    train = survivor_rows(splits["train"], horizon)
    val_all = eligible_all(splits["validation"], horizon)
    test_all = eligible_all(splits["test"], horizon)

    features = stage4b["diagnostic_models"][str(horizon)][
        "features_selected_train_only"
    ]
    model, enc = build_fixed_model(train, features)

    val_probs = model.predict_proba(enc.transform(val_all))
    test_probs = model.predict_proba(enc.transform(test_all))

    val_frontier = frontier(val_all, val_probs)
    floors = {}
    for floor in PRECISION_FLOORS:
        pick = choose_for_floor(val_frontier, floor)
        floors[str(int(100 * floor))] = {
            "validation": pick,
            "test": (
                threshold_metrics(test_all, test_probs, pick["threshold"])
                if pick else None
            ),
        }

    return {
        "horizon_min": horizon,
        "features": features,
        "train_resolved_n": len(train),
        "validation_eligible_n": len(val_all),
        "test_eligible_n": len(test_all),
        "validation_frontier_n": len(val_frontier),
        "precision_floors": floors,
        "_model": model,
        "_encoder": enc,
        "_validation_rows": val_all,
        "_validation_probs": val_probs,
        "_test_rows": test_all,
        "_test_probs": test_probs,
    }


def highest_feasible_floor(result: dict[str, Any]) -> int | None:
    feasible = [
        int(k)
        for k, v in result["precision_floors"].items()
        if v["validation"] is not None
    ]
    return max(feasible) if feasible else None


def choose_formal_rule(
    horizon_results: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = []
    for h in HORIZONS:
        r = horizon_results[str(h)]
        floor = highest_feasible_floor(r)
        if floor is None:
            continue
        val = r["precision_floors"][str(floor)]["validation"]
        candidates.append({
            "horizon_min": h,
            "precision_floor_pct": floor,
            "validation": val,
        })
    if not candidates:
        return None
    candidates.sort(
        key=lambda c: (
            c["precision_floor_pct"],
            c["validation"]["resolved_take_n"],
            -(
                c["validation"]["timeout_rate_pct"]
                if c["validation"]["timeout_rate_pct"] is not None
                else 100.0
            ),
            -c["horizon_min"],
        ),
        reverse=True,
    )
    return candidates[0]


def clean_result(r: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in r.items() if not k.startswith("_")}


def write_predictions(
    horizon_results: dict[str, dict[str, Any]],
    formal: dict[str, Any] | None,
) -> None:
    fields = [
        "horizon_min", "split", "position_id", "symbol", "side",
        "gate_checked_at_ms", "primary_meta_label", "score_meta_win",
        "formal_selected_horizon", "formal_threshold", "take",
    ]
    out = []
    for h in HORIZONS:
        r = horizon_results[str(h)]
        formal_selected = bool(
            formal is not None and formal["horizon_min"] == h
        )
        formal_threshold = (
            formal["validation"]["threshold"] if formal_selected else None
        )
        for split, rows_key, probs_key in (
            ("validation", "_validation_rows", "_validation_probs"),
            ("test", "_test_rows", "_test_probs"),
        ):
            for row, p in zip(r[rows_key], r[probs_key]):
                out.append({
                    "horizon_min": h,
                    "split": split,
                    "position_id": row["position_id"],
                    "symbol": row["symbol"],
                    "side": row["side"],
                    "gate_checked_at_ms": row["gate_checked_at_ms"],
                    "primary_meta_label": row["primary_meta_label"],
                    "score_meta_win": p,
                    "formal_selected_horizon": formal_selected,
                    "formal_threshold": formal_threshold,
                    "take": bool(
                        formal_selected
                        and formal_threshold is not None
                        and p >= formal_threshold
                    ),
                })
    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)


def run_wd5h_stage4c() -> dict[str, Any]:
    rows, _ = load_rows()
    stage4b = json.loads(STAGE4B_JSON.read_text())

    horizon_results = {
        str(h): fit_score_horizon(rows, stage4b, h)
        for h in HORIZONS
    }
    formal = choose_formal_rule(horizon_results)

    formal_test = None
    if formal is not None:
        h = str(formal["horizon_min"])
        floor = str(formal["precision_floor_pct"])
        formal_test = horizon_results[h]["precision_floors"][floor]["test"]

    write_predictions(horizon_results, formal)

    test_precision = (
        formal_test["resolved_precision_pct"]
        if formal_test else None
    )
    test_all_win = (
        formal_test["all_take_win_rate_pct"]
        if formal_test else None
    )
    test_resolved_n = (
        formal_test["resolved_take_n"] if formal_test else 0
    )

    status = "TEMPORAL_HIGH_PRECISION_GATE_NOT_READY"
    if (
        formal is not None
        and formal["precision_floor_pct"] >= 70
        and test_precision is not None
        and test_precision >= 65.0
        and test_resolved_n >= MIN_RESOLVED_TAKES
        and test_all_win is not None
        and test_all_win >= 55.0
    ):
        status = "TEMPORAL_HIGH_PRECISION_GATE_PROMISING"

    result = {
        "version": WD5H4C_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "method": {
            "model": (
                "fixed Stage4B diagnostic logistic per horizon; "
                "train-only top-12 temporal features; L2=1"
            ),
            "survivor_guard": (
                "candidate eligible only if primary label_end_ms "
                "> T0+horizon"
            ),
            "precision_floors_pct": [
                int(100 * x) for x in PRECISION_FLOORS
            ],
            "minimum_resolved_validation_takes": MIN_RESOLVED_TAKES,
            "horizon_selection": (
                "validation only: highest feasible precision floor, "
                "then largest resolved TAKE count, then lower timeout "
                "rate, then shorter delay"
            ),
            "test_role": (
                "historical robustness only; Stage4B already inspected "
                "historical test behavior, so not promotion-grade"
            ),
            "delayed_entry_economics": (
                "NOT evaluated here; deferred to Stage4D"
            ),
        },
        "horizons": {
            h: clean_result(r)
            for h, r in horizon_results.items()
        },
        "formal_selected_rule": formal,
        "formal_test_result": formal_test,
        "assessment": {
            "status": status,
            "formal_horizon_min": (
                formal["horizon_min"] if formal else None
            ),
            "formal_validation_precision_floor_pct": (
                formal["precision_floor_pct"] if formal else None
            ),
            "formal_validation_resolved_precision_pct": (
                formal["validation"]["resolved_precision_pct"]
                if formal else None
            ),
            "formal_validation_resolved_take_n": (
                formal["validation"]["resolved_take_n"]
                if formal else 0
            ),
            "formal_test_resolved_precision_pct": test_precision,
            "formal_test_all_take_win_rate_pct": test_all_win,
            "formal_test_resolved_take_n": test_resolved_n,
            "production_authority": "NONE",
            "next_stage": (
                "WD-5H Stage 4D — Delayed-Entry Replay"
                if status == "TEMPORAL_HIGH_PRECISION_GATE_PROMISING"
                else "Reassess temporal gate design before replay"
            ),
        },
        "outputs": {
            "json": str(OUTPUT_JSON),
            "predictions_csv": str(OUTPUT_CSV),
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, allow_nan=False)
    )
    return result
