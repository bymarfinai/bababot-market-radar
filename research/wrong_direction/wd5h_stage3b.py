from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from research.wrong_direction.wd5b_discovery import (
    Encoder,
    auc_score,
    binary_metrics,
)


WD5H3B_VERSION = "wd5h-stage3b-purged-meta-model-v1"

FEATURE_PATH = Path("/app/data/wd5h1_thesis_labeled_features.csv")
LABEL_PATH = Path("/app/data/wd5h3a_triple_barrier_labels.csv")
OUTPUT_PREDICTIONS = Path("/app/data/wd5h3b_meta_model_predictions.csv")
OUTPUT_JSON = Path("/app/data/wd5h3b_meta_model_results.json")

WIN = "META_WIN"
LOSS = "META_LOSS"
TIMEOUT = "TIMEOUT"
EMBARGO_MIN = 30

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

ARCHITECTURES = (
    "BASELINE_UNPURGED_UNWEIGHTED",
    "PURGED_UNWEIGHTED",
    "PURGED_UNIQUENESS_WEIGHTED",
)


def load_joined_rows() -> list[dict[str, Any]]:
    features = list(csv.DictReader(FEATURE_PATH.open()))
    labels = {
        r["position_id"]: r
        for r in csv.DictReader(LABEL_PATH.open())
    }
    rows: list[dict[str, Any]] = []
    for source in features:
        pid = source["meta_position_id"]
        lab = labels.get(pid)
        if lab is None:
            raise RuntimeError(f"missing Stage3A label for {pid}")
        row = dict(source)
        row["primary_meta_label"] = lab["primary_meta_label"]
        row["primary_label_end_ms"] = int(lab["primary_label_end_ms"])
        row["primary_uniqueness_weight"] = float(
            lab["primary_uniqueness_weight"]
        )
        row["primary_avg_concurrency"] = float(
            lab["primary_avg_concurrency"]
        )
        rows.append(row)
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    if len(rows) != 2175:
        raise RuntimeError(f"expected 2175 joined rows, got {len(rows)}")
    return rows


def resolved(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r for r in rows
        if r["primary_meta_label"] in {WIN, LOSS}
    ]


def target(row: dict[str, Any]) -> int:
    return 1 if row["primary_meta_label"] == WIN else 0


def population_splits(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    n = len(rows)
    p45 = 45 * n // 100
    p60 = 3 * n // 5
    p80 = 4 * n // 5
    return {
        "inner_train_pool": rows[:p45],
        "inner_val_pool": rows[p45:p60],
        "outer_train_pool": rows[:p60],
        "outer_val_pool": rows[p60:p80],
        "dev_plus_val_pool": rows[:p80],
        "test_pool": rows[p80:],
    }


def purge_for_holdout(
    train_pool: list[dict[str, Any]],
    holdout_pool: list[dict[str, Any]],
    *,
    embargo_min: int = EMBARGO_MIN,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not holdout_pool:
        return list(train_pool), {
            "before_n": len(train_pool),
            "after_n": len(train_pool),
            "removed_n": 0,
            "holdout_start_ms": None,
            "embargo_min": embargo_min,
        }
    holdout_start = min(int(r["meta_opened_at_ms"]) for r in holdout_pool)
    embargo_start = holdout_start - embargo_min * 60_000
    kept = []
    removed_overlap = 0
    removed_embargo = 0
    for row in train_pool:
        opened = int(row["meta_opened_at_ms"])
        label_end = int(row["primary_label_end_ms"])
        overlap = label_end >= holdout_start
        embargo = opened >= embargo_start
        if overlap or embargo:
            if overlap:
                removed_overlap += 1
            if embargo:
                removed_embargo += 1
            continue
        kept.append(row)
    return kept, {
        "before_n": len(train_pool),
        "after_n": len(kept),
        "removed_n": len(train_pool) - len(kept),
        "removed_overlap_n": removed_overlap,
        "removed_embargo_n": removed_embargo,
        "holdout_start_ms": holdout_start,
        "embargo_start_ms": embargo_start,
        "embargo_min": embargo_min,
    }


def portable_feature_types(
    train_rows: list[dict[str, Any]],
) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in train_rows[0]:
        if not key.startswith("f_"):
            continue
        if key in TIME_FEATURES or key in SCALE_PROXY_FEATURES:
            continue
        if key.startswith("f_latency_"):
            continue
        values = {str(r.get(key, "")) for r in train_rows}
        if len(values) <= 1:
            continue
        numeric = True
        for row in train_rows[: min(300, len(train_rows))]:
            try:
                v = float(row[key])
                if not math.isfinite(v):
                    numeric = False
                    break
            except (TypeError, ValueError):
                numeric = False
                break
        out[key] = "numeric" if numeric else "categorical"
    return out


def categorical_separation(
    rows: list[dict[str, Any]],
    feature: str,
) -> float:
    y = [target(r) for r in rows]
    base = sum(y) / len(y)
    groups: dict[str, list[int]] = {}
    for row in rows:
        groups.setdefault(str(row[feature]), []).append(target(row))
    weighted = 0.0
    for ys in groups.values():
        rate = sum(ys) / len(ys)
        weighted += len(ys) / len(rows) * abs(rate - base)
    return min(1.0, 2.0 * weighted)


def numeric_separation(
    rows: list[dict[str, Any]],
    feature: str,
) -> float:
    y = [target(r) for r in rows]
    p = [float(r[feature]) for r in rows]
    auc = auc_score(y, p)
    return 0.0 if auc is None else abs(float(auc) - 0.5) * 2.0


def rank_features(
    rows: list[dict[str, Any]],
    features: list[str],
    types: dict[str, str],
) -> list[str]:
    ranked = []
    for feature in features:
        score = (
            numeric_separation(rows, feature)
            if types[feature] == "numeric"
            else categorical_separation(rows, feature)
        )
        ranked.append((score, feature))
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [f for _, f in ranked]


class WeightedLogisticModel:
    def __init__(
        self,
        l2: float = 0.1,
        epochs: int = 700,
        lr: float = 0.12,
    ) -> None:
        self.l2 = l2
        self.epochs = epochs
        self.lr = lr
        self.weights: list[float] = []
        self.epochs_run = 0

    @staticmethod
    def _sigmoid(z: float) -> float:
        if z >= 0:
            e = math.exp(-min(z, 50.0))
            return 1.0 / (1.0 + e)
        e = math.exp(max(z, -50.0))
        return e / (1.0 + e)

    def fit(
        self,
        x: list[list[float]],
        y: list[int],
        sample_weight: list[float] | None = None,
    ) -> "WeightedLogisticModel":
        if not x or not y:
            raise ValueError("empty training set")
        n = len(y)
        weights = (
            [1.0] * n
            if sample_weight is None
            else [max(0.0, float(w)) for w in sample_weight]
        )
        total_w = sum(weights)
        if total_w <= 0:
            raise ValueError("non-positive total sample weight")
        weighted_pos = sum(w * t for w, t in zip(weights, y))
        prevalence = min(
            0.999,
            max(0.001, weighted_pos / total_w),
        )
        d = len(x[0])
        coef = [
            math.log(prevalence / (1.0 - prevalence))
        ] + [0.0] * d
        for epoch in range(self.epochs):
            grad = [0.0] * (d + 1)
            for row, yy, sw in zip(x, y, weights):
                z = coef[0]
                for j, value in enumerate(row, 1):
                    z += coef[j] * value
                err = (self._sigmoid(z) - yy) * sw
                grad[0] += err
                for j, value in enumerate(row, 1):
                    grad[j] += err * value
            grad[0] /= total_w
            for j in range(1, d + 1):
                grad[j] = (
                    grad[j] / total_w
                    + self.l2 * coef[j] / max(1, d)
                )
            rate = self.lr / (1.0 + 0.004 * epoch)
            max_step = 0.0
            for j in range(d + 1):
                step = rate * grad[j]
                coef[j] -= step
                max_step = max(max_step, abs(step))
            self.epochs_run = epoch + 1
            if max_step < 1e-7:
                break
        self.weights = coef
        return self

    def predict_proba(
        self,
        x: list[list[float]],
    ) -> list[float]:
        out = []
        for row in x:
            z = self.weights[0]
            for j, value in enumerate(row, 1):
                z += self.weights[j] * value
            out.append(self._sigmoid(z))
        return out


def normalized_uniqueness_weights(
    rows: list[dict[str, Any]],
) -> list[float]:
    raw = [float(r["primary_uniqueness_weight"]) for r in rows]
    mean = sum(raw) / len(raw)
    if mean <= 0:
        return [1.0] * len(raw)
    return [w / mean for w in raw]


def average_precision(
    y: list[int],
    p: list[float],
) -> float | None:
    positives = sum(y)
    if positives == 0:
        return None
    ranked = sorted(
        zip(p, y),
        key=lambda x: x[0],
        reverse=True,
    )
    tp = 0
    acc = 0.0
    for i, (_, yy) in enumerate(ranked, 1):
        if yy == 1:
            tp += 1
            acc += tp / i
    return acc / positives


def brier_score(
    y: list[int],
    p: list[float],
) -> float | None:
    if not y:
        return None
    return sum((yy - pp) ** 2 for yy, pp in zip(y, p)) / len(y)


def top_fraction_metrics(
    rows: list[dict[str, Any]],
    probs: list[float],
    fraction: float,
) -> dict[str, Any]:
    if not rows:
        return {"n": 0, "precision_pct": None}
    k = max(1, math.ceil(fraction * len(rows)))
    pairs = sorted(
        zip(probs, rows),
        key=lambda x: x[0],
        reverse=True,
    )[:k]
    wins = sum(target(r) == 1 for _, r in pairs)
    return {
        "n": k,
        "wins": wins,
        "precision_pct": 100.0 * wins / k,
        "score_min": min(p for p, _ in pairs),
        "score_max": max(p for p, _ in pairs),
    }


def evaluation(
    rows: list[dict[str, Any]],
    probs: list[float],
) -> dict[str, Any]:
    y = [target(r) for r in rows]
    base = 100.0 * sum(y) / len(y) if y else None
    metrics = binary_metrics(y, probs)
    return {
        "n": len(rows),
        "win_n": sum(y),
        "loss_n": len(y) - sum(y),
        "prevalence_pct": base,
        "auc": metrics["auc"],
        "average_precision": average_precision(y, probs),
        "brier": brier_score(y, probs),
        "balanced_accuracy_0p5": metrics["balanced_accuracy"],
        "accuracy_0p5": metrics["accuracy"],
        "top_5pct": top_fraction_metrics(rows, probs, 0.05),
        "top_10pct": top_fraction_metrics(rows, probs, 0.10),
        "top_20pct": top_fraction_metrics(rows, probs, 0.20),
        "top_30pct": top_fraction_metrics(rows, probs, 0.30),
    }


def timeout_score_summary(
    rows: list[dict[str, Any]],
    probs: list[float],
) -> dict[str, Any]:
    pairs = [
        (r, p)
        for r, p in zip(rows, probs)
        if r["primary_meta_label"] == TIMEOUT
    ]
    if not pairs:
        return {"n": 0}
    xs = sorted(p for _, p in pairs)
    return {
        "n": len(xs),
        "mean_score": sum(xs) / len(xs),
        "median_score": statistics.median(xs),
        "p10": xs[int(0.10 * (len(xs) - 1))],
        "p90": xs[int(0.90 * (len(xs) - 1))],
    }


def fit_model(
    train_rows: list[dict[str, Any]],
    eval_rows: list[dict[str, Any]],
    features: list[str],
    types: dict[str, str],
    l2: float,
    *,
    weighted: bool,
) -> tuple[WeightedLogisticModel, Encoder, list[float]]:
    encoder = Encoder(features, types).fit(train_rows)
    model = WeightedLogisticModel(
        l2=l2,
        epochs=700,
        lr=0.12,
    )
    sw = (
        normalized_uniqueness_weights(train_rows)
        if weighted
        else None
    )
    model.fit(
        encoder.transform(train_rows),
        [target(r) for r in train_rows],
        sw,
    )
    return (
        model,
        encoder,
        model.predict_proba(encoder.transform(eval_rows)),
    )


def architecture_train_rows(
    architecture: str,
    train_pool: list[dict[str, Any]],
    holdout_pool: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    train_resolved = resolved(train_pool)
    if architecture == "BASELINE_UNPURGED_UNWEIGHTED":
        return train_resolved, {
            "before_n": len(train_resolved),
            "after_n": len(train_resolved),
            "removed_n": 0,
            "embargo_min": 0,
        }
    purged, info = purge_for_holdout(
        train_resolved,
        holdout_pool,
        embargo_min=EMBARGO_MIN,
    )
    return purged, info


def architecture_is_weighted(architecture: str) -> bool:
    return architecture == "PURGED_UNIQUENESS_WEIGHTED"


def select_hyperparams(
    architecture: str,
    inner_train_pool: list[dict[str, Any]],
    inner_val_pool: list[dict[str, Any]],
    features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    train_rows, purge_info = architecture_train_rows(
        architecture,
        inner_train_pool,
        inner_val_pool,
    )
    val_rows = resolved(inner_val_pool)
    ranking = rank_features(train_rows, features, types)
    grid = []
    for k in (5, 10, 20, 40, 60, 80):
        if k > len(ranking):
            continue
        selected = ranking[:k]
        for l2 in (0.1, 1.0, 4.0):
            model, encoder, probs = fit_model(
                train_rows,
                val_rows,
                selected,
                types,
                l2,
                weighted=architecture_is_weighted(architecture),
            )
            m = evaluation(val_rows, probs)
            grid.append({
                "top_k": k,
                "l2": l2,
                "features": selected,
                "encoded_feature_count": len(encoder.encoded_names),
                "epochs_run": model.epochs_run,
                "metrics": m,
            })
    grid.sort(
        key=lambda x: (
            x["metrics"]["average_precision"]
            if x["metrics"]["average_precision"] is not None
            else -1.0,
            x["metrics"]["auc"]
            if x["metrics"]["auc"] is not None
            else -1.0,
            x["metrics"]["top_10pct"]["precision_pct"]
            if x["metrics"]["top_10pct"]["precision_pct"] is not None
            else -1.0,
            -x["top_k"],
        ),
        reverse=True,
    )
    return {
        "purge": purge_info,
        "inner_train_n": len(train_rows),
        "inner_val_n": len(val_rows),
        "selected": grid[0],
        "grid": grid,
    }


def refit_and_evaluate(
    architecture: str,
    train_pool: list[dict[str, Any]],
    eval_pool: list[dict[str, Any]],
    *,
    top_k: int,
    l2: float,
    features: list[str],
    types: dict[str, str],
) -> dict[str, Any]:
    train_rows, purge_info = architecture_train_rows(
        architecture,
        train_pool,
        eval_pool,
    )
    eval_rows = resolved(eval_pool)
    ranking = rank_features(train_rows, features, types)
    chosen = ranking[:top_k]
    model, encoder, probs = fit_model(
        train_rows,
        eval_rows,
        chosen,
        types,
        l2,
        weighted=architecture_is_weighted(architecture),
    )

    all_eval_encoder = encoder.transform(eval_pool)
    all_eval_probs = model.predict_proba(all_eval_encoder)

    return {
        "train_n": len(train_rows),
        "eval_resolved_n": len(eval_rows),
        "purge": purge_info,
        "features": chosen,
        "encoded_feature_count": len(encoder.encoded_names),
        "metrics": evaluation(eval_rows, probs),
        "timeout_scores": timeout_score_summary(
            eval_pool,
            all_eval_probs,
        ),
        "_model": model,
        "_encoder": encoder,
        "_resolved_probs": probs,
        "_all_eval_probs": all_eval_probs,
    }


def strip_runtime(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v for k, v in obj.items()
        if not k.startswith("_")
    }


def architecture_selection_key(
    result: dict[str, Any],
) -> tuple[float, float, float]:
    m = result["metrics"]
    return (
        m["average_precision"]
        if m["average_precision"] is not None else -1.0,
        m["auc"] if m["auc"] is not None else -1.0,
        m["top_10pct"]["precision_pct"]
        if m["top_10pct"]["precision_pct"] is not None else -1.0,
    )


def run_wd5h_stage3b() -> dict[str, Any]:
    rows = load_joined_rows()
    splits = population_splits(rows)

    feature_types = portable_feature_types(
        resolved(splits["inner_train_pool"])
    )
    features = sorted(feature_types)

    hyperparams = {}
    outer_results = {}

    for architecture in ARCHITECTURES:
        hp = select_hyperparams(
            architecture,
            splits["inner_train_pool"],
            splits["inner_val_pool"],
            features,
            feature_types,
        )
        hyperparams[architecture] = hp
        selected = hp["selected"]
        outer_results[architecture] = refit_and_evaluate(
            architecture,
            splits["outer_train_pool"],
            splits["outer_val_pool"],
            top_k=int(selected["top_k"]),
            l2=float(selected["l2"]),
            features=features,
            types=feature_types,
        )

    selected_architecture = max(
        ARCHITECTURES,
        key=lambda name: architecture_selection_key(
            outer_results[name]
        ),
    )

    # Final refit/evaluation is performed only after architecture selection.
    final_results = {}
    for architecture in ARCHITECTURES:
        selected = hyperparams[architecture]["selected"]
        final_results[architecture] = refit_and_evaluate(
            architecture,
            splits["dev_plus_val_pool"],
            splits["test_pool"],
            top_k=int(selected["top_k"]),
            l2=float(selected["l2"]),
            features=features,
            types=feature_types,
        )

    # Persist final-test scores for audit. Architecture choice was already
    # frozen above using outer validation only.
    pred_rows = []
    for architecture in ARCHITECTURES:
        final = final_results[architecture]
        encoder = final["_encoder"]
        model = final["_model"]
        probs = model.predict_proba(
            encoder.transform(splits["test_pool"])
        )
        for row, prob in zip(splits["test_pool"], probs):
            pred_rows.append({
                "architecture": architecture,
                "selected_architecture": (
                    architecture == selected_architecture
                ),
                "position_id": row["meta_position_id"],
                "symbol": row["meta_symbol"],
                "side": row["meta_original_side"],
                "opened_at_ms": row["meta_opened_at_ms"],
                "primary_meta_label": row["primary_meta_label"],
                "score_meta_win": prob,
                "uniqueness_weight": row[
                    "primary_uniqueness_weight"
                ],
                "avg_concurrency": row[
                    "primary_avg_concurrency"
                ],
            })

    OUTPUT_PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PREDICTIONS.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=list(pred_rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(pred_rows)

    split_summary = {}
    for name, pool in splits.items():
        counts = Counter(
            r["primary_meta_label"] for r in pool
        )
        split_summary[name] = {
            "n": len(pool),
            "classes": dict(counts),
            "resolved_n": counts[WIN] + counts[LOSS],
        }

    clean_hyperparams = {}
    for name, hp in hyperparams.items():
        clean_hyperparams[name] = {
            "purge": hp["purge"],
            "inner_train_n": hp["inner_train_n"],
            "inner_val_n": hp["inner_val_n"],
            "selected": hp["selected"],
        }

    clean_outer = {
        k: strip_runtime(v)
        for k, v in outer_results.items()
    }
    clean_final = {
        k: strip_runtime(v)
        for k, v in final_results.items()
    }

    baseline_test = clean_final[
        "BASELINE_UNPURGED_UNWEIGHTED"
    ]["metrics"]
    selected_test = clean_final[
        selected_architecture
    ]["metrics"]
    test_prevalence = selected_test["prevalence_pct"] or 0.0
    ap_pct = 100.0 * (
        selected_test["average_precision"] or 0.0
    )

    assessment = {
        "selected_architecture": selected_architecture,
        "selection_basis": (
            "outer-validation average precision, then AUC, "
            "then top-10% precision"
        ),
        "selected_test_auc": selected_test["auc"],
        "selected_test_average_precision": selected_test[
            "average_precision"
        ],
        "selected_test_top10_precision_pct": selected_test[
            "top_10pct"
        ]["precision_pct"],
        "test_prevalence_pct": test_prevalence,
        "ap_lift_over_prevalence_pp": ap_pct - test_prevalence,
        "selected_vs_baseline_test_auc_delta": (
            (selected_test["auc"] or 0.0)
            - (baseline_test["auc"] or 0.0)
        ),
        "selected_vs_baseline_test_ap_delta": (
            (selected_test["average_precision"] or 0.0)
            - (baseline_test["average_precision"] or 0.0)
        ),
        "status": (
            "META_RANKING_SIGNAL_PROMISING"
            if (
                (selected_test["auc"] or 0.0) >= 0.60
                and ap_pct >= test_prevalence + 5.0
            )
            else "META_RANKING_SIGNAL_WEAK"
        ),
        "production_authority": "NONE",
    }

    result = {
        "version": WD5H3B_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "method": {
            "target": "META_WIN vs META_LOSS",
            "timeout_handling": "excluded from binary training/evaluation; score distribution reported separately",
            "population_split": "first 45% inner train, next 15% inner validation, next 20% outer validation, final 20% untouched test",
            "embargo_min": EMBARGO_MIN,
            "purge_rule": "remove training event if its primary label interval reaches holdout start; also remove training events opened within 30m before holdout start",
            "uniqueness_weighting": "Stage3A primary uniqueness weight normalized to mean 1 inside each training set",
            "architecture_selection": (
                "outer-validation AP -> AUC -> top-10% precision"
            ),
            "final_test_role": (
                "opened only after architecture selection; "
                "not used to choose architecture or hyperparameters"
            ),
        },
        "feature_count": len(features),
        "split_summary": split_summary,
        "hyperparameters": clean_hyperparams,
        "outer_validation": clean_outer,
        "selected_architecture": selected_architecture,
        "final_test": clean_final,
        "assessment": assessment,
        "outputs": {
            "predictions": str(OUTPUT_PREDICTIONS),
            "json": str(OUTPUT_JSON),
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, allow_nan=False)
    )
    return result
