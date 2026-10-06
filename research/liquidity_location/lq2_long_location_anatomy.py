from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Callable


LQ2_VERSION = "lq2-long-location-anatomy-v1"
EXPECTED_LONG_UNIVERSE = 1236


def _f(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _pct(num: int, den: int) -> float | None:
    return (100.0 * num / den) if den else None


def _round(v: Any, nd: int = 4) -> Any:
    if isinstance(v, float) and math.isfinite(v):
        return round(v, nd)
    return v


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    return ranks


def _pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 3:
        return None
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    den = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if den <= 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / den


def _spearman(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    x = [a for a, _ in pairs]
    y = [b for _, b in pairs]
    return _pearson(_rank(x), _rank(y))


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "n": 0,
            "median_mfe_pct": None,
            "mfe_lt_0p5_pct": None,
            "mfe_ge_1_pct": None,
            "mfe_ge_2_pct": None,
            "realized_win_pct": None,
            "sum_realized_pnl": None,
        }
    mfes = [float(r["future_max_mfe_pct"]) for r in rows]
    pnls = [float(r["future_realized_pnl"]) for r in rows]
    return {
        "n": len(rows),
        "median_mfe_pct": _round(statistics.median(mfes)),
        "mfe_lt_0p5_pct": _round(_pct(sum(v < 0.5 for v in mfes), len(mfes)), 2),
        "mfe_ge_1_pct": _round(_pct(sum(v >= 1.0 for v in mfes), len(mfes)), 2),
        "mfe_ge_2_pct": _round(_pct(sum(v >= 2.0 for v in mfes), len(mfes)), 2),
        "realized_win_pct": _round(_pct(sum(v > 0.0 for v in pnls), len(pnls)), 2),
        "sum_realized_pnl": _round(sum(pnls), 2),
    }


def _class_mix(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(r["future_outcome_label"]) for r in rows))


def _mfe_bucket(v: float) -> str:
    if v < 0.30:
        return "MFE<0.30"
    if v < 0.50:
        return "0.30-0.50"
    if v < 1.00:
        return "0.50-1.00"
    if v < 2.00:
        return "1.00-2.00"
    return ">=2.00"


def _supply_bucket(v: float | None) -> str:
    if v is None:
        return "MISSING"
    if v == 0:
        return "INSIDE_SUPPLY"
    if v <= 0.20:
        return "0-0.20%"
    if v <= 0.40:
        return "0.20-0.40%"
    if v <= 0.70:
        return "0.40-0.70%"
    if v <= 1.00:
        return "0.70-1.00%"
    return ">1.00%"


def _demand_bucket(v: float | None) -> str:
    if v is None:
        return "MISSING"
    if v == 0:
        return "INSIDE_DEMAND"
    if v <= 0.25:
        return "0-0.25%"
    if v <= 0.50:
        return "0.25-0.50%"
    if v <= 1.00:
        return "0.50-1.00%"
    if v <= 2.00:
        return "1.00-2.00%"
    return ">2.00%"


def _location_category(s: float | None, d: float | None) -> str:
    ins = s == 0
    ind = d == 0
    if ins and ind:
        return "BOTH_SUPPLY_AND_DEMAND"
    if ins:
        return "SUPPLY_ONLY"
    if ind:
        return "DEMAND_ONLY"
    return "NEITHER"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lq1-csv", default="research/liquidity_location/results/lq1_entry_zone_features.csv")
    ap.add_argument("--feature-csv", default="/opt/core-app/data/wd5h1_thesis_labeled_features.csv")
    ap.add_argument("--output-dir", default="research/liquidity_location/results")
    args = ap.parse_args()

    lq1 = _rows(Path(args.lq1_csv))
    features = {r["meta_position_id"]: r for r in _rows(Path(args.feature_csv))}
    if len(lq1) != EXPECTED_LONG_UNIVERSE:
        raise RuntimeError(f"expected LQ1 rows={EXPECTED_LONG_UNIVERSE}, got {len(lq1)}")

    joined: list[dict[str, Any]] = []
    missing: list[str] = []
    for z in lq1:
        pid = z["position_id"]
        f = features.get(pid)
        if f is None:
            missing.append(pid)
            continue
        mfe = _f(f.get("future_max_mfe_pct"))
        pnl = _f(f.get("future_realized_pnl"))
        if mfe is None or pnl is None:
            missing.append(pid)
            continue
        s = _f(z.get("nearest_supply_distance_pct"))
        d = _f(z.get("nearest_demand_distance_pct"))
        row: dict[str, Any] = dict(z)
        row.update(
            {
                "future_max_mfe_pct": mfe,
                "future_min_mae_pct": _f(f.get("future_min_mae_pct")),
                "future_realized_pnl": pnl,
                "future_realized_pnl_pct": _f(f.get("future_realized_pnl_pct")),
                "future_outcome_label": f.get("future_outcome_label"),
                "label_path_style": f.get("label_path_style"),
                "label_thesis_class": f.get("label_thesis_class"),
                "mfe_bucket": _mfe_bucket(mfe),
                "supply_distance_bucket": _supply_bucket(s),
                "demand_distance_bucket": _demand_bucket(d),
                "location_category": _location_category(s, d),
                "flag_inside_fresh_15m_supply": (
                    _f(z.get("15m_supply_distance_pct")) == 0
                    and z.get("15m_supply_state") == "FRESH"
                ),
                "flag_inside_fresh_5m_or_15m_supply": (
                    (_f(z.get("5m_supply_distance_pct")) == 0 and z.get("5m_supply_state") == "FRESH")
                    or (_f(z.get("15m_supply_distance_pct")) == 0 and z.get("15m_supply_state") == "FRESH")
                ),
            }
        )
        joined.append(row)

    if missing or len(joined) != EXPECTED_LONG_UNIVERSE:
        raise RuntimeError(f"join coverage={len(joined)}/{EXPECTED_LONG_UNIVERSE}; missing={missing[:5]}")

    joined.sort(key=lambda r: (int(r["opened_at_ms"]), r["position_id"]))
    for i, row in enumerate(joined):
        row["chrono_split"] = "TRAIN" if i < 741 else "VALIDATION" if i < 988 else "RESERVE"

    mfe_anatomy: list[dict[str, Any]] = []
    mfe_order = ["MFE<0.30", "0.30-0.50", "0.50-1.00", "1.00-2.00", ">=2.00"]
    for bucket in mfe_order:
        rr = [r for r in joined if r["mfe_bucket"] == bucket]
        sd = [_f(r.get("nearest_supply_distance_pct")) for r in rr]
        dd = [_f(r.get("nearest_demand_distance_pct")) for r in rr]
        sdv = [v for v in sd if v is not None]
        ddv = [v for v in dd if v is not None]
        mfe_anatomy.append(
            {
                "mfe_bucket": bucket,
                "n": len(rr),
                "median_supply_distance_pct": _round(_median(sdv)),
                "inside_supply_pct": _round(_pct(sum(v == 0 for v in sdv), len(rr)), 2),
                "inside_fresh_15m_supply_pct": _round(
                    _pct(sum(bool(r["flag_inside_fresh_15m_supply"]) for r in rr), len(rr)), 2
                ),
                "median_demand_distance_pct": _round(_median(ddv)),
                "realized_win_pct": _metrics(rr)["realized_win_pct"],
            }
        )

    supply_anatomy: list[dict[str, Any]] = []
    for bucket in ["INSIDE_SUPPLY", "0-0.20%", "0.20-0.40%", "0.40-0.70%", "0.70-1.00%", ">1.00%", "MISSING"]:
        rr = [r for r in joined if r["supply_distance_bucket"] == bucket]
        if not rr:
            continue
        item = {"supply_bucket": bucket, **_metrics(rr), "class_mix": _class_mix(rr)}
        supply_anatomy.append(item)

    demand_anatomy: list[dict[str, Any]] = []
    for bucket in ["INSIDE_DEMAND", "0-0.25%", "0.25-0.50%", "0.50-1.00%", "1.00-2.00%", ">2.00%", "MISSING"]:
        rr = [r for r in joined if r["demand_distance_bucket"] == bucket]
        if not rr:
            continue
        demand_anatomy.append({"demand_bucket": bucket, **_metrics(rr), "class_mix": _class_mix(rr)})

    outcome_anatomy: list[dict[str, Any]] = []
    class_order = ["TRUE_WRONG_DIRECTION", "STALL_NO_EDGE", "RIGHT_THEN_FAILURE", "RECOVERED_DRAWDOWN", "CORRECT_RUNNER"]
    for cls in class_order:
        rr = [r for r in joined if r["future_outcome_label"] == cls]
        sd = [_f(r.get("nearest_supply_distance_pct")) for r in rr]
        dd = [_f(r.get("nearest_demand_distance_pct")) for r in rr]
        sdv = [v for v in sd if v is not None]
        ddv = [v for v in dd if v is not None]
        outcome_anatomy.append(
            {
                "class": cls,
                "n": len(rr),
                "median_supply_distance_pct": _round(_median(sdv)),
                "inside_supply_pct": _round(_pct(sum(v == 0 for v in sdv), len(rr)), 2),
                "inside_fresh_15m_supply_pct": _round(
                    _pct(sum(bool(r["flag_inside_fresh_15m_supply"]) for r in rr), len(rr)), 2
                ),
                "median_demand_distance_pct": _round(_median(ddv)),
                **_metrics(rr),
            }
        )

    location_comparison: list[dict[str, Any]] = []
    for cat in ["SUPPLY_ONLY", "DEMAND_ONLY", "BOTH_SUPPLY_AND_DEMAND", "NEITHER"]:
        rr = [r for r in joined if r["location_category"] == cat]
        location_comparison.append({"location": cat, **_metrics(rr), "class_mix": _class_mix(rr)})

    timeframe_supply: list[dict[str, Any]] = []
    for tf in ("5m", "15m", "1h"):
        key = f"{tf}_supply_distance_pct"
        eligible = [r for r in joined if _f(r.get(key)) is not None]
        for inside in (True, False):
            rr = [r for r in eligible if ((_f(r.get(key)) == 0) == inside)]
            timeframe_supply.append(
                {
                    "timeframe": tf,
                    "group": "INSIDE" if inside else "OUTSIDE",
                    **_metrics(rr),
                }
            )

    state_supply: list[dict[str, Any]] = []
    for tf in ("5m", "15m", "1h"):
        for state in ("FRESH", "TESTED"):
            rr = [r for r in joined if r.get(f"{tf}_supply_state") == state]
            state_supply.append({"timeframe": tf, "state": state, **_metrics(rr)})

    fresh_15m_split: list[dict[str, Any]] = []
    for split in ("ALL", "TRAIN", "VALIDATION", "RESERVE"):
        base = joined if split == "ALL" else [r for r in joined if r["chrono_split"] == split]
        hit = [r for r in base if r["flag_inside_fresh_15m_supply"]]
        comp = [r for r in base if not r["flag_inside_fresh_15m_supply"]]
        fresh_15m_split.append(
            {"split": split, "group": "INSIDE_FRESH_15M_SUPPLY", **_metrics(hit), "class_mix": _class_mix(hit)}
        )
        fresh_15m_split.append(
            {"split": split, "group": "COMPLEMENT", **_metrics(comp), "class_mix": _class_mix(comp)}
        )

    demand_vs_supply: list[dict[str, Any]] = []
    definitions: list[tuple[str, Callable[[dict[str, Any]], bool]]] = [
        ("INSIDE_SUPPLY_ONLY", lambda r: r["location_category"] == "SUPPLY_ONLY"),
        ("INSIDE_DEMAND_ONLY", lambda r: r["location_category"] == "DEMAND_ONLY"),
        (
            "DEMAND_WITHIN_0P5_AND_SUPPLY_GT_0P25",
            lambda r: (
                (_f(r.get("nearest_demand_distance_pct")) is not None)
                and _f(r.get("nearest_demand_distance_pct")) <= 0.5
                and (
                    _f(r.get("nearest_supply_distance_pct")) is None
                    or _f(r.get("nearest_supply_distance_pct")) > 0.25
                )
            ),
        ),
        (
            "SUPPLY_WITHIN_0P25_AND_DEMAND_GT_1",
            lambda r: (
                (_f(r.get("nearest_supply_distance_pct")) is not None)
                and _f(r.get("nearest_supply_distance_pct")) <= 0.25
                and (_f(r.get("nearest_demand_distance_pct")) is not None)
                and _f(r.get("nearest_demand_distance_pct")) > 1.0
            ),
        ),
    ]
    for name, fn in definitions:
        rr = [r for r in joined if fn(r)]
        demand_vs_supply.append({"definition": name, **_metrics(rr), "class_mix": _class_mix(rr)})

    corr_pairs = {
        "nearest_supply_vs_mfe": [
            (_f(r.get("nearest_supply_distance_pct")), float(r["future_max_mfe_pct"])) for r in joined
        ],
        "5m_supply_vs_mfe": [
            (_f(r.get("5m_supply_distance_pct")), float(r["future_max_mfe_pct"])) for r in joined
        ],
        "15m_supply_vs_mfe": [
            (_f(r.get("15m_supply_distance_pct")), float(r["future_max_mfe_pct"])) for r in joined
        ],
        "1h_supply_vs_mfe": [
            (_f(r.get("1h_supply_distance_pct")), float(r["future_max_mfe_pct"])) for r in joined
        ],
        "nearest_demand_vs_mfe": [
            (_f(r.get("nearest_demand_distance_pct")), float(r["future_max_mfe_pct"])) for r in joined
        ],
    }
    correlations = {}
    for name, pairs in corr_pairs.items():
        clean = [(a, b) for a, b in pairs if a is not None]
        correlations[name] = {"n": len(clean), "spearman_rho": _round(_spearman(clean), 4)}

    fresh_hit = [r for r in joined if r["flag_inside_fresh_15m_supply"]]
    fresh_class_mix = _class_mix(fresh_hit)

    summary = {
        "version": LQ2_VERSION,
        "contract": {
            "rows": len(joined),
            "expected_rows": EXPECTED_LONG_UNIVERSE,
            "chronological_split": {"TRAIN": 741, "VALIDATION": 247, "RESERVE": 248},
            "threshold_optimization": False,
        },
        "correlations": correlations,
        "mfe_anatomy": mfe_anatomy,
        "supply_distance_anatomy": supply_anatomy,
        "demand_distance_anatomy": demand_anatomy,
        "outcome_anatomy": outcome_anatomy,
        "location_comparison": location_comparison,
        "timeframe_supply": timeframe_supply,
        "state_supply": state_supply,
        "fresh_15m_supply_chrono": fresh_15m_split,
        "demand_vs_supply": demand_vs_supply,
        "key_candidate": {
            "name": "INSIDE_FRESH_15M_SUPPLY",
            "all": _metrics(fresh_hit),
            "class_mix": fresh_class_mix,
            "interpretation": "research candidate only; no production blocking authority",
        },
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "lq2_trade_level.csv", joined)
    (out_dir / "lq2_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()