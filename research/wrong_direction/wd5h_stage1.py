from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from market_radar.binance import BinancePublicClient
from .wd5b_discovery import auc_score
from .wd5e_multihead import (
    MICRO_FEATURES,
    derive_micro_features,
    load_gate_times,
)
from .wd5f_conditional_reversal import (
    ALL_NEW_FEATURES as WD5F_NEW_FEATURES,
    BENCHMARKS,
    FLOW_STRUCTURE_FEATURES,
    MARKET_FEATURES,
    OI_FEATURES,
    _fetch_klines_range,
    derive_flow_structure_features,
    derive_market_features,
    derive_oi_features,
)


WD5H1_VERSION = "wd5h-stage1-thesis-label-audit-v1"
BASE_PATH = Path("/app/data/wd5d_opportunity_exhaustion_features.csv")
PREENTRY_CACHE = Path("/app/data/wd5h1_preentry_1m_cache.jsonl")
BENCHMARK_CACHE = Path("/app/data/wd5h1_benchmark_1m_cache.json")
OI_CACHE = Path("/app/data/wd5h1_oi_5m_cache.jsonl")
OUTPUT_DATASET = Path("/app/data/wd5h1_thesis_labeled_features.csv")
OUTPUT_JSON = Path("/app/data/wd5h1_feature_audit_results.json")

SEED_PREENTRY = (
    Path("/app/data/wd5e_preentry_1m_cache.jsonl"),
    Path("/app/data/wd5g_preentry_1m_cache.jsonl"),
)
SEED_OI = (
    Path("/app/data/wd5f_oi_5m_cache.jsonl"),
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

LABEL_MAP = {
    "CORRECT_RUNNER": "VALID_WINNER",
    "RECOVERED_DRAWDOWN": "VALID_WINNER",
    "RIGHT_THEN_FAILURE": "RIGHT_THEN_FAILURE",
    "TRUE_WRONG_DIRECTION": "TRUE_WRONG_DIRECTION",
    "STALL_NO_EDGE": "STALL_NO_EDGE",
}


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def load_base_rows() -> list[dict[str, Any]]:
    rows = list(csv.DictReader(BASE_PATH.open()))
    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    if len(rows) != 2175:
        raise RuntimeError(f"expected 2175 rows, got {len(rows)}")
    return rows


def _load_jsonl_rows(
    paths: tuple[Path, ...],
) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            out[str(obj["position_id"])] = obj.get("rows") or []
    return out


def _fetch_preentry_one(
    meta: dict[str, Any],
) -> tuple[str, list[list[Any]]]:
    client = BinancePublicClient(timeout=8.0, retries=3)
    gate = int(meta["gate_checked_at_ms"])
    rows = client.get(
        "/fapi/v1/klines",
        {
            "symbol": str(meta["symbol"]),
            "interval": "1m",
            "startTime": gate - 40 * 60_000,
            "endTime": gate,
            "limit": 60,
        },
    )
    rows = [
        row for row in rows
        if len(row) >= 7 and int(row[6]) <= gate
    ]
    return str(meta["position_id"]), rows


def ensure_preentry_cache(
    gate_meta: dict[str, dict[str, Any]],
    workers: int = 6,
) -> dict[str, list[list[Any]]]:
    cache = _load_jsonl_rows(
        (PREENTRY_CACHE,) + SEED_PREENTRY
    )
    missing = [
        meta for pid, meta in gate_meta.items()
        if pid not in cache
    ]
    if missing:
        errors = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_fetch_preentry_one, meta): meta
                for meta in missing
            }
            for i, future in enumerate(as_completed(futures), 1):
                meta = futures[future]
                try:
                    pid, rows = future.result()
                    cache[pid] = rows
                except Exception as exc:
                    errors.append(f"{meta['position_id']}: {exc}")
                if i % 100 == 0:
                    time.sleep(0.2)
        if errors:
            raise RuntimeError(
                f"preentry fetch failed {len(errors)} sample={errors[:5]}"
            )

    PREENTRY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with PREENTRY_CACHE.open("w") as fh:
        for pid in sorted(
            gate_meta,
            key=lambda x: int(gate_meta[x]["gate_checked_at_ms"]),
        ):
            fh.write(json.dumps(
                {"position_id": pid, "rows": cache[pid]},
                separators=(",", ":"),
            ) + "\n")
    return {pid: cache[pid] for pid in gate_meta}


def ensure_benchmark_cache(
    min_gate_ms: int,
    max_gate_ms: int,
) -> dict[str, list[list[Any]]]:
    if BENCHMARK_CACHE.exists():
        payload = json.loads(BENCHMARK_CACHE.read_text())
        if (
            int(payload.get("start_ms", 0)) <= min_gate_ms - 45 * 60_000
            and int(payload.get("end_ms", 0)) >= max_gate_ms
            and all(
                symbol in payload.get("symbols", {})
                for symbol in BENCHMARKS
            )
        ):
            return payload["symbols"]

    client = BinancePublicClient(timeout=10.0, retries=3)
    start = min_gate_ms - 45 * 60_000
    symbols = {}
    for symbol in BENCHMARKS:
        symbols[symbol] = _fetch_klines_range(
            client, symbol, start, max_gate_ms
        )
    payload = {
        "start_ms": start,
        "end_ms": max_gate_ms,
        "symbols": symbols,
    }
    BENCHMARK_CACHE.write_text(json.dumps(
        payload, separators=(",", ":")
    ))
    return symbols


def _fetch_oi_one(
    meta: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    client = BinancePublicClient(timeout=8.0, retries=3)
    gate = int(meta["gate_checked_at_ms"])
    rows = client.get(
        "/futures/data/openInterestHist",
        {
            "symbol": str(meta["symbol"]),
            "period": "5m",
            "startTime": gate - 45 * 60_000,
            "endTime": gate,
            "limit": 20,
        },
    )
    rows = [
        row for row in rows
        if int(row.get("timestamp", 0)) <= gate
    ]
    return str(meta["position_id"]), rows


def ensure_oi_cache(
    gate_meta: dict[str, dict[str, Any]],
    workers: int = 6,
) -> dict[str, list[dict[str, Any]]]:
    cache: dict[str, list[dict[str, Any]]] = {}
    for path in (OI_CACHE,) + SEED_OI:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            cache[str(obj["position_id"])] = obj.get("rows") or []

    missing = [
        meta for pid, meta in gate_meta.items()
        if pid not in cache
    ]
    if missing:
        errors = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_fetch_oi_one, meta): meta
                for meta in missing
            }
            for i, future in enumerate(as_completed(futures), 1):
                meta = futures[future]
                try:
                    pid, rows = future.result()
                    cache[pid] = rows
                except Exception as exc:
                    errors.append(f"{meta['position_id']}: {exc}")
                if i % 100 == 0:
                    time.sleep(0.2)
        if errors:
            raise RuntimeError(
                f"OI fetch failed {len(errors)} sample={errors[:5]}"
            )

    with OI_CACHE.open("w") as fh:
        for pid in sorted(
            gate_meta,
            key=lambda x: int(gate_meta[x]["gate_checked_at_ms"]),
        ):
            fh.write(json.dumps(
                {"position_id": pid, "rows": cache[pid]},
                separators=(",", ":"),
            ) + "\n")
    return {pid: cache[pid] for pid in gate_meta}


def thesis_label(row: dict[str, Any]) -> str:
    source = str(row["future_outcome_label"])
    if source not in LABEL_MAP:
        raise KeyError(source)
    return LABEL_MAP[source]


def build_dataset() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base = load_base_rows()
    ids = {str(r["meta_position_id"]) for r in base}
    gate_meta = load_gate_times(ids)

    preentry = ensure_preentry_cache(gate_meta)
    min_gate = min(
        int(meta["gate_checked_at_ms"])
        for meta in gate_meta.values()
    )
    max_gate = max(
        int(meta["gate_checked_at_ms"])
        for meta in gate_meta.values()
    )
    benchmarks = ensure_benchmark_cache(min_gate, max_gate)
    oi_cache = ensure_oi_cache(gate_meta)

    rows = []
    oi_lt3 = 0
    micro_lt16 = 0
    for source in base:
        pid = str(source["meta_position_id"])
        meta = gate_meta[pid]
        side = str(source["meta_original_side"])
        raw = preentry[pid]

        if len(raw) < 16:
            micro_lt16 += 1
            raise RuntimeError(f"insufficient micro rows {pid}: {len(raw)}")

        micro = derive_micro_features(
            raw,
            side,
            float(source["f_new_overheat_pressure"]),
        )
        market = derive_market_features(
            raw,
            benchmarks,
            int(meta["gate_checked_at_ms"]),
            side,
        )
        flow = derive_flow_structure_features(raw, side)
        oi_rows = oi_cache.get(pid) or []
        if len(oi_rows) < 3:
            oi_lt3 += 1
        oi = derive_oi_features(
            oi_rows,
            float(micro["f_micro_side_ret_5m"]),
            float(source["f_new_overheat_pressure"]),
        )

        row = dict(source)
        row.update({k: str(v) for k, v in micro.items()})
        row.update({k: str(v) for k, v in market.items()})
        row.update({k: str(v) for k, v in flow.items()})
        row.update({k: str(v) for k, v in oi.items()})
        label = thesis_label(source)
        row["label_thesis_class"] = label
        row["target_selective_win"] = int(label == "VALID_WINNER")
        row["target_true_wrong"] = int(
            label == "TRUE_WRONG_DIRECTION"
        )
        row["meta_gate_checked_at_ms"] = int(
            meta["gate_checked_at_ms"]
        )
        rows.append(row)

    rows.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    return rows, {
        "rows": len(rows),
        "labels": dict(Counter(
            r["label_thesis_class"] for r in rows
        )),
        "preentry_cache_n": len(preentry),
        "oi_cache_n": len(oi_cache),
        "oi_rows_lt3": oi_lt3,
        "micro_rows_lt16": micro_lt16,
        "gate_min_ms": min_gate,
        "gate_max_ms": max_gate,
    }


def feature_family(feature: str) -> str:
    if feature.startswith("f_micro_"):
        return "MICRO_PATH"
    if feature.startswith("f_f_market_") or feature.startswith(
        "f_f_btc_"
    ) or feature.startswith("f_f_eth_") or feature.startswith(
        "f_f_coin_"
    ) or feature.startswith("f_f_relative_"):
        return "MARKET_RELATIVE"
    if feature in FLOW_STRUCTURE_FEATURES:
        return "FLOW_STRUCTURE"
    if feature in OI_FEATURES:
        return "OI_DYNAMICS"
    if feature.startswith("f_new_"):
        return "WD5D_ENGINEERED"
    if feature.startswith("f_gate_"):
        return "STAGE11C"
    if feature.startswith("f_context_"):
        return "STAGE5_CONTEXT"
    if feature.startswith("f_score_") or feature in {
        "f_selected_score",
        "f_opposite_score",
        "f_score_edge",
    }:
        return "STAGE4_SCORE"
    if feature.startswith("f_ret_") or feature.startswith(
        "f_return_"
    ) or feature.startswith("f_volume_") or feature.startswith(
        "f_range_"
    ) or feature.startswith("f_trades_"):
        return "MOVEMENT"
    return "OTHER"


def feature_types(
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
        if len({str(r.get(key, "")) for r in rows}) <= 1:
            continue
        numeric = True
        for row in rows[:200]:
            try:
                x = float(row[key])
                if not math.isfinite(x):
                    numeric = False
                    break
            except (TypeError, ValueError):
                numeric = False
                break
        out[key] = "numeric" if numeric else "categorical"
    return out


def _numeric_sep(
    pos: list[dict[str, Any]],
    neg: list[dict[str, Any]],
    feature: str,
) -> dict[str, Any]:
    pv = [float(r[feature]) for r in pos]
    nv = [float(r[feature]) for r in neg]
    y = [1] * len(pv) + [0] * len(nv)
    score = pv + nv
    auc = auc_score(y, score)
    sep = 0.0 if auc is None else abs(float(auc) - 0.5) * 2.0
    pm = _median(pv)
    nm = _median(nv)
    direction = (
        1 if pm is not None and nm is not None and pm > nm
        else -1 if pm is not None and nm is not None and pm < nm
        else 0
    )
    return {
        "separation": sep,
        "auc_positive_higher": auc,
        "positive_median": pm,
        "negative_median": nm,
        "direction": direction,
    }


def _categorical_sep(
    pos: list[dict[str, Any]],
    neg: list[dict[str, Any]],
    feature: str,
) -> dict[str, Any]:
    rows = [(str(r[feature]), 1) for r in pos] + [
        (str(r[feature]), 0) for r in neg
    ]
    base = len(pos) / len(rows)
    groups: dict[str, list[int]] = defaultdict(list)
    for value, target in rows:
        groups[value].append(target)
    weighted = 0.0
    rates = {}
    for value, ys in groups.items():
        rate = sum(ys) / len(ys)
        weighted += len(ys) / len(rows) * abs(rate - base)
        rates[value] = {
            "n": len(ys),
            "positive_rate": rate,
        }
    return {
        "separation": min(1.0, 2.0 * weighted),
        "category_rates": rates,
    }


def comparison_audit(
    rows: list[dict[str, Any]],
    *,
    name: str,
    positive_labels: set[str],
    negative_labels: set[str],
    types: dict[str, str],
) -> dict[str, Any]:
    cohort = [
        r for r in rows
        if r["label_thesis_class"] in positive_labels | negative_labels
    ]
    pos = [
        r for r in cohort
        if r["label_thesis_class"] in positive_labels
    ]
    neg = [
        r for r in cohort
        if r["label_thesis_class"] in negative_labels
    ]
    cohort.sort(key=lambda r: int(r["meta_opened_at_ms"]))
    n = len(cohort)
    fifths = [
        cohort[i*n//5:(i+1)*n//5]
        for i in range(5)
    ]

    ranked = []
    for feature, kind in types.items():
        info = (
            _numeric_sep(pos, neg, feature)
            if kind == "numeric"
            else _categorical_sep(pos, neg, feature)
        )
        fifth_scores = []
        directions = []
        for block in fifths:
            bp = [
                r for r in block
                if r["label_thesis_class"] in positive_labels
            ]
            bn = [
                r for r in block
                if r["label_thesis_class"] in negative_labels
            ]
            if len(bp) < 5 or len(bn) < 5:
                continue
            bi = (
                _numeric_sep(bp, bn, feature)
                if kind == "numeric"
                else _categorical_sep(bp, bn, feature)
            )
            fifth_scores.append(bi["separation"])
            if kind == "numeric":
                directions.append(bi["direction"])
        nonzero = [d for d in directions if d]
        ranked.append({
            "feature": feature,
            "family": feature_family(feature),
            "type": kind,
            **info,
            "fifth_scores": fifth_scores,
            "median_fifth_separation": (
                statistics.median(fifth_scores)
                if fifth_scores else None
            ),
            "min_fifth_separation": (
                min(fifth_scores) if fifth_scores else None
            ),
            "numeric_direction_consistent": (
                len(set(nonzero)) <= 1
                if kind == "numeric" and nonzero
                else True if kind == "numeric"
                else None
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

    stable = [
        x for x in ranked
        if x["median_fifth_separation"] is not None
        and x["median_fifth_separation"] >= 0.08
        and x["min_fifth_separation"] is not None
        and x["min_fifth_separation"] >= 0.03
        and (
            x["type"] != "numeric"
            or x["numeric_direction_consistent"]
        )
    ]
    family_counts = Counter(x["family"] for x in stable)
    family_best = {}
    for family in sorted({
        x["family"] for x in ranked
    }):
        items = [x for x in ranked if x["family"] == family]
        if items:
            family_best[family] = items[0]

    return {
        "comparison": name,
        "positive_labels": sorted(positive_labels),
        "negative_labels": sorted(negative_labels),
        "positive_n": len(pos),
        "negative_n": len(neg),
        "top_features": ranked[:40],
        "stable_feature_count": len(stable),
        "stable_features": stable[:50],
        "stable_family_counts": dict(family_counts),
        "best_by_family": family_best,
    }


def label_summary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    out = {}
    for label in sorted({
        r["label_thesis_class"] for r in rows
    }):
        group = [
            r for r in rows
            if r["label_thesis_class"] == label
        ]
        out[label] = {
            "n": len(group),
            "share_pct": 100.0 * len(group) / len(rows),
            "net_pnl": sum(
                float(r["future_realized_pnl"]) for r in group
            ),
            "positive_final_n": sum(
                float(r["future_realized_pnl"]) > 0 for r in group
            ),
            "median_mfe_pct": _median([
                float(r["future_max_mfe_pct"]) for r in group
            ]),
            "median_mae_pct": _median([
                float(r["future_min_mae_pct"]) for r in group
            ]),
            "median_realized_pct": _median([
                float(r["future_realized_pnl_pct"]) for r in group
            ]),
            "side_counts": dict(Counter(
                r["meta_original_side"] for r in group
            )),
            "stage_counts": dict(Counter(
                r["f_stage"] for r in group
            )),
        }
    return out


def run_wd5h_stage1() -> dict[str, Any]:
    rows, coverage = build_dataset()
    types = feature_types(rows)

    comparisons = [
        comparison_audit(
            rows,
            name="VALID_WINNER_vs_ALL_NONWIN",
            positive_labels={"VALID_WINNER"},
            negative_labels={
                "RIGHT_THEN_FAILURE",
                "TRUE_WRONG_DIRECTION",
                "STALL_NO_EDGE",
            },
            types=types,
        ),
        comparison_audit(
            rows,
            name="VALID_WINNER_vs_TRUE_WRONG_DIRECTION",
            positive_labels={"VALID_WINNER"},
            negative_labels={"TRUE_WRONG_DIRECTION"},
            types=types,
        ),
        comparison_audit(
            rows,
            name="VALID_WINNER_vs_RIGHT_THEN_FAILURE",
            positive_labels={"VALID_WINNER"},
            negative_labels={"RIGHT_THEN_FAILURE"},
            types=types,
        ),
        comparison_audit(
            rows,
            name="VALID_WINNER_vs_STALL_NO_EDGE",
            positive_labels={"VALID_WINNER"},
            negative_labels={"STALL_NO_EDGE"},
            types=types,
        ),
        comparison_audit(
            rows,
            name="TRUE_WRONG_DIRECTION_vs_RIGHT_THEN_FAILURE",
            positive_labels={"TRUE_WRONG_DIRECTION"},
            negative_labels={"RIGHT_THEN_FAILURE"},
            types=types,
        ),
    ]

    primary = comparisons[0]
    by_name = {
        x["comparison"]: x
        for x in comparisons
    }
    conclusion = {
        "status": "DIRECT_BINARY_WEAK_PAIRWISE_STRONG",
        "direct_winner_vs_all_stable_feature_count": (
            primary["stable_feature_count"]
        ),
        "direct_winner_vs_all_stable_families": (
            primary["stable_family_counts"]
        ),
        "pairwise_stable_feature_counts": {
            name: audit["stable_feature_count"]
            for name, audit in by_name.items()
            if name != "VALID_WINNER_vs_ALL_NONWIN"
        },
        "architecture_implication": (
            "Do not force one flat WIN-vs-ALL classifier. Build a "
            "hierarchical selective gate that separately rejects "
            "TRUE_WRONG_DIRECTION, RIGHT_THEN_FAILURE, and STALL/NO_EDGE "
            "before issuing a high-confidence WIN action."
        ),
        "detector_authority": "NONE_STAGE1_AUDIT_ONLY",
        "next_stage": (
            "WD-5H Stage 2: chronological hierarchical thesis classifier "
            "+ high-precision WIN abstention gate; train-only feature "
            "selection and untouched temporal validation."
        ),
    }

    OUTPUT_DATASET.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_DATASET.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(rows[0].keys())
        )
        writer.writeheader()
        writer.writerows(rows)

    result = {
        "version": WD5H1_VERSION,
        "authority": "RESEARCH_ONLY",
        "production_rule_changes": False,
        "coverage": coverage,
        "label_definition": {
            "VALID_WINNER": [
                "CORRECT_RUNNER",
                "RECOVERED_DRAWDOWN",
            ],
            "RIGHT_THEN_FAILURE": ["RIGHT_THEN_FAILURE"],
            "TRUE_WRONG_DIRECTION": ["TRUE_WRONG_DIRECTION"],
            "STALL_NO_EDGE": ["STALL_NO_EDGE"],
        },
        "label_summary": label_summary(rows),
        "feature_count": len(types),
        "feature_type_counts": dict(Counter(types.values())),
        "feature_family_counts": dict(Counter(
            feature_family(f) for f in types
        )),
        "comparisons": comparisons,
        "conclusion": conclusion,
        "outputs": {
            "dataset": str(OUTPUT_DATASET),
            "json": str(OUTPUT_JSON),
            "preentry_cache": str(PREENTRY_CACHE),
            "benchmark_cache": str(BENCHMARK_CACHE),
            "oi_cache": str(OI_CACHE),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(
        result, indent=2, allow_nan=False
    ))
    return result
