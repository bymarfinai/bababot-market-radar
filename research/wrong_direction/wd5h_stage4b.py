from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .wd5b_discovery import auc_score
from .wd5h_stage3b import Encoder, WeightedLogisticModel

WD5H4B_VERSION = "wd5h-stage4b-temporal-pattern-discovery-v1"

TEMPORAL_PATH = Path("/app/data/wd5h4a_temporal_features.csv")
STATIC_PATH = Path("/app/data/wd5h1_thesis_labeled_features.csv")
OUTPUT_JSON = Path("/app/data/wd5h4b_temporal_pattern_results.json")
OUTPUT_CSV = Path("/app/data/wd5h4b_feature_audit.csv")

HORIZONS = (1, 2, 3)
LABEL_WIN = "META_WIN"
LABEL_LOSS = "META_LOSS"

MIN_NONMISSING_RATE = 0.95
MIN_UNIQUE = 5
ROBUST_MIN_SEPARATION = 0.05
STRONG_MIN_SEPARATION = 0.10
DIAGNOSTIC_TOP_K = 12
DIAGNOSTIC_L2 = 1.0


def _f(x: Any) -> float | None:
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def load_rows() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = list(csv.DictReader(TEMPORAL_PATH.open()))
    static = {
        r["meta_position_id"]: r
        for r in csv.DictReader(STATIC_PATH.open())
    }
    rows.sort(key=lambda r: int(r["gate_checked_at_ms"]))
    if len(rows) != 2175 or len(static) != 2175:
        raise RuntimeError(
            f"coverage mismatch temporal={len(rows)} static={len(static)}"
        )
    return rows, static


def resolved(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r for r in rows
        if r["primary_meta_label"] in {LABEL_WIN, LABEL_LOSS}
    ]


def survivor_rows(
    rows: list[dict[str, Any]],
    horizon: int,
) -> list[dict[str, Any]]:
    target_key = f"t{horizon}_target_ms"
    return [
        r for r in rows
        if r["primary_meta_label"] in {LABEL_WIN, LABEL_LOSS}
        and int(r["primary_label_end_ms"]) > int(r[target_key])
    ]


def early_resolution_summary(
    rows: list[dict[str, Any]],
    horizon: int,
) -> dict[str, Any]:
    resolved_rows = resolved(rows)
    target_key = f"t{horizon}_target_ms"
    early = [
        r for r in resolved_rows
        if int(r["primary_label_end_ms"]) <= int(r[target_key])
    ]
    survivors = [
        r for r in resolved_rows
        if int(r["primary_label_end_ms"]) > int(r[target_key])
    ]
    ec = Counter(r["primary_meta_label"] for r in early)
    sc = Counter(r["primary_meta_label"] for r in survivors)
    return {
        "resolved_population_n": len(resolved_rows),
        "early_resolved_n": len(early),
        "early_resolved_pct": (
            100.0 * len(early) / len(resolved_rows)
            if resolved_rows else None
        ),
        "early_meta_win_n": ec[LABEL_WIN],
        "early_meta_loss_n": ec[LABEL_LOSS],
        "survivor_n": len(survivors),
        "survivor_meta_win_n": sc[LABEL_WIN],
        "survivor_meta_loss_n": sc[LABEL_LOSS],
        "survivor_meta_win_prevalence_pct": (
            100.0 * sc[LABEL_WIN] / len(survivors)
            if survivors else None
        ),
    }


def y(row: dict[str, Any]) -> int:
    return int(row["primary_meta_label"] == LABEL_WIN)


def chronological_splits(
    rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    n = len(rows)
    p60 = 3 * n // 5
    p80 = 4 * n // 5
    return {
        "train": rows[:p60],
        "validation": rows[p60:p80],
        "test": rows[p80:],
    }


def feature_family(feature: str) -> str:
    # strip tN_ prefix
    rest = feature.split("_", 1)[1]
    if rest.startswith("confirm_"):
        return "CONFIRMATION_PATH"
    if rest.startswith("delta_"):
        return "DELTA_VS_T0"
    if rest.startswith("f_micro_"):
        return "MICRO"
    if (
        rest.startswith("f_f_market_")
        or rest.startswith("f_f_coin_")
        or rest.startswith("f_f_btc_")
        or rest.startswith("f_f_eth_")
        or rest.startswith("f_f_relative_")
    ):
        return "MARKET_RELATIVE"
    if rest.startswith("f_f_oi_") or rest.startswith("oi_"):
        return "OI"
    if (
        rest.startswith("f_f_taker_")
        or "flow" in rest
        or "taker" in rest
    ):
        return "FLOW"
    return "OTHER"


def temporal_features(
    rows: list[dict[str, Any]],
    horizon: int,
) -> list[str]:
    prefix = f"t{horizon}_"
    blocked_suffixes = (
        "_target_ms",
        "_latest_closed_ms",
        "_oi_latest_timestamp_ms",
    )
    out = []
    for key in rows[0]:
        if not key.startswith(prefix):
            continue
        if key.endswith(blocked_suffixes):
            continue
        vals = [_f(r.get(key)) for r in rows]
        nonmissing = [v for v in vals if v is not None]
        if len(nonmissing) / len(rows) < MIN_NONMISSING_RATE:
            continue
        if len(set(round(v, 12) for v in nonmissing)) < MIN_UNIQUE:
            continue
        out.append(key)
    return out


def auc_for(
    rows: list[dict[str, Any]],
    feature: str,
) -> dict[str, Any]:
    pairs = [
        (y(r), _f(r.get(feature)))
        for r in rows
    ]
    pairs = [(yy, v) for yy, v in pairs if v is not None]
    if not pairs:
        return {
            "n": 0,
            "auc": None,
            "direction": None,
            "separation": None,
        }
    ys = [a for a, _ in pairs]
    vs = [b for _, b in pairs]
    auc = auc_score(ys, vs)
    if auc is None:
        return {
            "n": len(pairs),
            "auc": None,
            "direction": None,
            "separation": None,
        }
    return {
        "n": len(pairs),
        "auc": float(auc),
        "direction": "HIGHER_IN_WIN" if auc >= 0.5 else "LOWER_IN_WIN",
        "separation": 2.0 * abs(float(auc) - 0.5),
    }


def median_by_class(
    rows: list[dict[str, Any]],
    feature: str,
) -> dict[str, float | None]:
    out = {}
    for label in (LABEL_WIN, LABEL_LOSS):
        vals = [
            _f(r.get(feature))
            for r in rows
            if r["primary_meta_label"] == label
        ]
        vals = [v for v in vals if v is not None]
        out[label] = statistics.median(vals) if vals else None
    return out


def static_key_for_temporal(feature: str) -> str | None:
    rest = feature.split("_", 1)[1]
    if rest.startswith("delta_") or rest.startswith("confirm_"):
        return None
    if rest.startswith("oi_"):
        return None
    if rest.startswith("f_"):
        return rest
    return None


def static_auc(
    split_rows: list[dict[str, Any]],
    static: dict[str, dict[str, Any]],
    static_feature: str,
) -> dict[str, Any]:
    ys = []
    vals = []
    for row in split_rows:
        s = static[row["position_id"]]
        v = _f(s.get(static_feature))
        if v is None:
            continue
        ys.append(y(row))
        vals.append(v)
    auc = auc_score(ys, vals) if ys else None
    return {
        "n": len(ys),
        "auc": float(auc) if auc is not None else None,
        "separation": (
            2.0 * abs(float(auc) - 0.5)
            if auc is not None else None
        ),
    }


def audit_horizon(
    all_rows: list[dict[str, Any]],
    static: dict[str, dict[str, Any]],
    horizon: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    population_splits = chronological_splits(all_rows)
    split_resolved = {
        name: survivor_rows(rows, horizon)
        for name, rows in population_splits.items()
    }
    survivor_all = survivor_rows(all_rows, horizon)
    features = temporal_features(survivor_all, horizon)
    records = []

    for feature in features:
        parts = {
            name: auc_for(rows, feature)
            for name, rows in split_resolved.items()
        }
        dirs = [
            p["direction"]
            for p in parts.values()
            if p["direction"] is not None
        ]
        stable_direction = len(dirs) == 3 and len(set(dirs)) == 1
        min_sep = min(
            p["separation"] for p in parts.values()
            if p["separation"] is not None
        )
        median_sep = statistics.median(
            p["separation"] for p in parts.values()
            if p["separation"] is not None
        )
        robust = stable_direction and min_sep >= ROBUST_MIN_SEPARATION
        strong = stable_direction and min_sep >= STRONG_MIN_SEPARATION

        medians = {
            name: median_by_class(rows, feature)
            for name, rows in split_resolved.items()
        }

        static_feature = static_key_for_temporal(feature)
        static_parts = None
        gain_vs_t0 = None
        if static_feature is not None and static_feature in next(iter(static.values())):
            static_parts = {
                name: static_auc(rows, static, static_feature)
                for name, rows in split_resolved.items()
            }
            temporal_mean_sep = statistics.mean(
                p["separation"] for p in parts.values()
                if p["separation"] is not None
            )
            static_mean_sep = statistics.mean(
                p["separation"] for p in static_parts.values()
                if p["separation"] is not None
            )
            gain_vs_t0 = temporal_mean_sep - static_mean_sep

        records.append({
            "horizon_min": horizon,
            "feature": feature,
            "family": feature_family(feature),
            "stable_direction": stable_direction,
            "robust": robust,
            "strong": strong,
            "stable_direction_value": dirs[0] if stable_direction else None,
            "min_separation": min_sep,
            "median_separation": median_sep,
            "mean_separation": statistics.mean(
                p["separation"] for p in parts.values()
                if p["separation"] is not None
            ),
            "gain_vs_t0_mean_separation": gain_vs_t0,
            "train_auc": parts["train"]["auc"],
            "validation_auc": parts["validation"]["auc"],
            "test_auc": parts["test"]["auc"],
            "train_sep": parts["train"]["separation"],
            "validation_sep": parts["validation"]["separation"],
            "test_sep": parts["test"]["separation"],
            "train_win_median": medians["train"][LABEL_WIN],
            "train_loss_median": medians["train"][LABEL_LOSS],
            "validation_win_median": medians["validation"][LABEL_WIN],
            "validation_loss_median": medians["validation"][LABEL_LOSS],
            "test_win_median": medians["test"][LABEL_WIN],
            "test_loss_median": medians["test"][LABEL_LOSS],
            "static_feature": static_feature,
            "static_train_auc": (
                static_parts["train"]["auc"] if static_parts else None
            ),
            "static_validation_auc": (
                static_parts["validation"]["auc"] if static_parts else None
            ),
            "static_test_auc": (
                static_parts["test"]["auc"] if static_parts else None
            ),
        })

    records.sort(
        key=lambda r: (
            r["strong"],
            r["robust"],
            r["stable_direction"],
            r["min_separation"],
            r["median_separation"],
        ),
        reverse=True,
    )

    family = {}
    for fam in sorted({r["family"] for r in records}):
        items = [r for r in records if r["family"] == fam]
        stable = [r for r in items if r["stable_direction"]]
        robust = [r for r in items if r["robust"]]
        strong = [r for r in items if r["strong"]]
        family[fam] = {
            "n": len(items),
            "stable_direction_n": len(stable),
            "robust_n": len(robust),
            "strong_n": len(strong),
            "best_feature": items[0]["feature"] if items else None,
            "best_min_separation": (
                items[0]["min_separation"] if items else None
            ),
            "top_5": [
                {
                    "feature": x["feature"],
                    "min_separation": x["min_separation"],
                    "median_separation": x["median_separation"],
                    "direction": x["stable_direction_value"],
                    "gain_vs_t0": x["gain_vs_t0_mean_separation"],
                }
                for x in items[:5]
            ],
        }

    return records, {
        "horizon_min": horizon,
        "eligible_feature_n": len(features),
        "stable_direction_n": sum(r["stable_direction"] for r in records),
        "robust_n": sum(r["robust"] for r in records),
        "strong_n": sum(r["strong"] for r in records),
        "families": family,
        "top_20": records[:20],
    }


def numeric_types(features: list[str]) -> dict[str, str]:
    return {f: "numeric" for f in features}


def diagnostic_model(
    all_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    horizon: int,
) -> dict[str, Any]:
    splits = chronological_splits(all_rows)
    train = survivor_rows(splits["train"], horizon)
    val = survivor_rows(splits["validation"], horizon)
    test = survivor_rows(splits["test"], horizon)

    # Feature selection strictly from training-only separation, but restricted
    # to temporal features at this horizon and no OI temporal-age/update flags.
    candidates = [
        r["feature"] for r in records
        if r["family"] != "OI"
        and not r["feature"].endswith("_confirm_closed_bars")
        and all(
            _f(x.get(r["feature"])) is not None
            for x in (train + val + test)
        )
    ]
    train_rank = []
    for feature in candidates:
        m = auc_for(train, feature)
        if m["auc"] is None:
            continue
        train_rank.append((m["separation"], feature))
    train_rank.sort(reverse=True)
    chosen = [f for _, f in train_rank[:DIAGNOSTIC_TOP_K]]

    enc = Encoder(chosen, numeric_types(chosen)).fit(train)
    model = WeightedLogisticModel(
        l2=DIAGNOSTIC_L2,
        epochs=700,
        lr=0.12,
    ).fit(
        enc.transform(train),
        [y(r) for r in train],
        None,
    )

    def score(rows):
        probs = model.predict_proba(enc.transform(rows))
        yy = [y(r) for r in rows]
        auc = auc_score(yy, probs)
        return {
            "n": len(rows),
            "win_n": sum(yy),
            "auc": float(auc) if auc is not None else None,
        }

    return {
        "horizon_min": horizon,
        "top_k": DIAGNOSTIC_TOP_K,
        "l2": DIAGNOSTIC_L2,
        "features_selected_train_only": chosen,
        "train": score(train),
        "validation": score(val),
        "test": score(test),
        "note": (
            "Diagnostic ranking only; no hyperparameter or threshold "
            "selection and no production authority."
        ),
    }


def direct_confirmation_summary(
    rows: list[dict[str, Any]],
    horizon: int,
) -> dict[str, Any]:
    splits = chronological_splits(rows)
    keys = [
        f"t{horizon}_confirm_side_return_pct",
        f"t{horizon}_confirm_mfe_pct",
        f"t{horizon}_confirm_mae_pct",
        f"t{horizon}_confirm_selected_taker_share",
        f"t{horizon}_confirm_last_clv_selected",
        f"t{horizon}_confirm_last_body_selected",
        f"t{horizon}_confirm_last_rejection_wick",
    ]
    out = {}
    for key in keys:
        out[key] = {}
        for name, pop in splits.items():
            rr = survivor_rows(pop, horizon)
            a = auc_for(rr, key)
            med = median_by_class(rr, key)
            out[key][name] = {
                "auc": a["auc"],
                "separation": a["separation"],
                "win_median": med[LABEL_WIN],
                "loss_median": med[LABEL_LOSS],
            }
    return out


def run_wd5h_stage4b() -> dict[str, Any]:
    rows, static = load_rows()
    all_records = []
    horizon_summaries = {}
    diagnostics = {}
    direct = {}
    early_resolution = {}

    for h in HORIZONS:
        early_resolution[str(h)] = early_resolution_summary(rows, h)
        records, summary = audit_horizon(rows, static, h)
        all_records.extend(records)
        horizon_summaries[str(h)] = summary
        diagnostics[str(h)] = diagnostic_model(rows, records, h)
        direct[str(h)] = direct_confirmation_summary(rows, h)

    # Determine descriptive best horizon without thresholding:
    # prioritize robust feature count, then strong count, then median of the
    # best 10 stable min-separations.
    horizon_score = {}
    for h in HORIZONS:
        recs = [r for r in all_records if r["horizon_min"] == h]
        stable = [r for r in recs if r["stable_direction"]]
        top = sorted(
            [r["min_separation"] for r in stable],
            reverse=True,
        )[:10]
        horizon_score[str(h)] = {
            "robust_n": sum(r["robust"] for r in recs),
            "strong_n": sum(r["strong"] for r in recs),
            "top10_stable_min_sep_median": (
                statistics.median(top) if top else 0.0
            ),
            "diagnostic_validation_auc": diagnostics[str(h)][
                "validation"
            ]["auc"],
            "diagnostic_test_auc": diagnostics[str(h)]["test"]["auc"],
        }

    best_h = max(
        HORIZONS,
        key=lambda h: (
            horizon_score[str(h)]["robust_n"],
            horizon_score[str(h)]["strong_n"],
            horizon_score[str(h)]["top10_stable_min_sep_median"],
        ),
    )

    # CSV audit.
    fields = list(all_records[0].keys())
    with OUTPUT_CSV.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_records)

    split_counts = {}
    for name, pop in chronological_splits(rows).items():
        c = Counter(r["primary_meta_label"] for r in pop)
        split_counts[name] = {
            "n": len(pop),
            "labels": dict(c),
            "resolved_n": c[LABEL_WIN] + c[LABEL_LOSS],
        }

    result = {
        "version": WD5H4B_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "method": {
            "target": "META_WIN vs META_LOSS among trades not yet barrier-resolved at the evaluated horizon",
            "timeouts": "excluded from discrimination audit",
            "survivor_guard": "exclude any META_WIN/META_LOSS whose Stage3A label_end_ms <= T0+horizon to prevent reading an outcome already resolved before the confirmation decision",
            "chronological_split": "60% train / 20% validation / 20% test",
            "stable_direction": (
                "feature AUC direction must agree in all three chronological splits"
            ),
            "robust_feature": (
                f"stable direction and min split separation >= {ROBUST_MIN_SEPARATION}"
            ),
            "strong_feature": (
                f"stable direction and min split separation >= {STRONG_MIN_SEPARATION}"
            ),
            "separation_definition": "2 * abs(AUC - 0.5)",
            "no_threshold_selection": True,
            "diagnostic_model": (
                "fixed logistic, top 12 temporal features ranked on train only, "
                "L2=1; ranking diagnostic only"
            ),
        },
        "split_counts": split_counts,
        "horizons": horizon_summaries,
        "early_resolution_by_horizon": early_resolution,
        "horizon_comparison": horizon_score,
        "descriptive_best_horizon": best_h,
        "diagnostic_models": diagnostics,
        "direct_confirmation_features": direct,
        "stage_conclusion": {
            "status": "TEMPORAL_PATTERN_DISCOVERY_COMPLETE_SURVIVOR_GUARDED",
            "next_stage": "WD-5H Stage 4C — High-Precision Temporal Confirmation Gate",
            "production_authority": "NONE",
        },
        "outputs": {
            "json": str(OUTPUT_JSON),
            "feature_audit_csv": str(OUTPUT_CSV),
        },
    }

    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, allow_nan=False)
    )
    return result
