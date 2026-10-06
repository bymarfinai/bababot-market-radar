from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


VERSION = "lq3a-fresh15m-supply-anatomy-v1"
EXPECTED_COHORT = 102


GOOD_CLASSES = {"RECOVERED_DRAWDOWN", "CORRECT_RUNNER"}
BAD_CLASSES = {"TRUE_WRONG_DIRECTION", "STALL_NO_EDGE"}
AMBIGUOUS_CLASSES = {"RIGHT_THEN_FAILURE"}


def f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def pct(n: int, d: int) -> float | None:
    return 100.0 * n / d if d else None


def med(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def r(v: Any, nd: int = 4) -> Any:
    if isinstance(v, float) and math.isfinite(v):
        return round(v, nd)
    return v


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def outcome_group(label: str) -> str:
    if label in GOOD_CLASSES:
        return "GOOD"
    if label in BAD_CLASSES:
        return "BAD"
    if label in AMBIGUOUS_CLASSES:
        return "RTF"
    return "OTHER"


def auc(pairs: list[tuple[float | None, int]]) -> float | None:
    clean = [(x, y) for x, y in pairs if x is not None]
    pos = [float(x) for x, y in clean if y == 1]
    neg = [float(x) for x, y in clean if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def state_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    groups = Counter(str(x["outcome_group"]) for x in rows)
    classes = Counter(str(x["future_outcome_label"]) for x in rows)
    pnls = [float(x["future_realized_pnl"]) for x in rows]
    mfes = [float(x["future_max_mfe_pct"]) for x in rows]
    classified = groups["GOOD"] + groups["BAD"]
    return {
        "n": len(rows),
        "group_mix": dict(groups),
        "class_mix": dict(classes),
        "good_pct_among_good_bad": r(pct(groups["GOOD"], classified), 2),
        "bad_pct_among_good_bad": r(pct(groups["BAD"], classified), 2),
        "realized_win_pct": r(pct(sum(v > 0 for v in pnls), len(rows)), 2),
        "mfe_ge_1_pct": r(pct(sum(v >= 1 for v in mfes), len(rows)), 2),
        "median_mfe_pct": r(med(mfes)),
        "sum_realized_pnl": r(sum(pnls), 2),
    }


def checkpoint_state(
    gate_price: float,
    side_return_pct: float,
    lower: float,
    upper: float,
) -> tuple[float, str, float, float]:
    price = gate_price * (1.0 + side_return_pct / 100.0)
    if price > upper:
        state = "ABOVE"
    elif price < lower:
        state = "BELOW"
    else:
        state = "INSIDE"
    above_upper_pct = (price / upper - 1.0) * 100.0
    above_lower_pct = (price / lower - 1.0) * 100.0
    return price, state, above_upper_pct, above_lower_pct


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--lq2-csv",
        default="research/liquidity_location/results/lq2_trade_level.csv",
    )
    ap.add_argument(
        "--t0-csv",
        default="/opt/core-app/data/wd5h1_thesis_labeled_features.csv",
    )
    ap.add_argument(
        "--temporal-csv",
        default="/opt/core-app/data/wd5h4a_temporal_features.csv",
    )
    ap.add_argument(
        "--output-dir",
        default="research/liquidity_location/results",
    )
    args = ap.parse_args()

    lq2 = load_csv(Path(args.lq2_csv))
    t0 = {x["meta_position_id"]: x for x in load_csv(Path(args.t0_csv))}
    temporal = {x["position_id"]: x for x in load_csv(Path(args.temporal_csv))}

    cohort = [
        x
        for x in lq2
        if str(x.get("flag_inside_fresh_15m_supply") or "").lower() == "true"
    ]
    if len(cohort) != EXPECTED_COHORT:
        raise RuntimeError(f"expected cohort={EXPECTED_COHORT}, got={len(cohort)}")

    out: list[dict[str, Any]] = []
    for row in cohort:
        pid = row["position_id"]
        a = t0[pid]
        b = temporal[pid]
        entry = float(row["entry_price"])
        lower = float(row["15m_supply_lower"])
        upper = float(row["15m_supply_upper"])
        width = upper - lower
        group = outcome_group(str(row["future_outcome_label"]))

        item: dict[str, Any] = {
            "position_id": pid,
            "symbol": row["symbol"],
            "opened_at_ms": int(row["opened_at_ms"]),
            "chrono_split": row["chrono_split"],
            "future_outcome_label": row["future_outcome_label"],
            "outcome_group": group,
            "future_max_mfe_pct": float(row["future_max_mfe_pct"]),
            "future_realized_pnl": float(row["future_realized_pnl"]),
            "entry_price": entry,
            "supply_lower": lower,
            "supply_upper": upper,
            "zone_departure_atr": f(row["15m_supply_departure_atr"]),
            "zone_volume_ratio": f(row["15m_supply_volume_ratio"]),
            "zone_width_atr": f(row["15m_supply_width_atr"]),
            "zone_age_min": (
                int(row["opened_at_ms"]) - int(float(row["15m_supply_born_ms"]))
            )
            / 60_000.0,
            "penetration_frac": (entry - lower) / width if width > 0 else None,
            "room_to_upper_pct": (upper / entry - 1.0) * 100.0,
            "depth_from_lower_pct": (entry / lower - 1.0) * 100.0,
            "nearest_demand_pct": f(row["nearest_demand_distance_pct"]),
            "inside_5m_supply": f(row["5m_supply_distance_pct"]) == 0.0,
            "inside_1h_supply": f(row["1h_supply_distance_pct"]) == 0.0,
            "gate_price": f(b["gate_current_price"]),
            "fill_latency_ms": f(b["fill_latency_ms"]),
            "t0_gate_side_ret_3m_pct": f(a["f_gate_side_ret_3m_pct"]),
            "t0_gate_taker_share": f(a["f_gate_taker_share_for_selected"]),
            "t0_selected_slope5_norm": f(a["f_f_selected_slope5_norm"]),
            "t0_vwap_extension20": f(a["f_micro_selected_vwap_extension_20"]),
            "t0_coin_minus_market_15m": f(a["f_f_coin_minus_market_15m"]),
            "t0_micro_accel_1_vs_3": f(a["f_new_micro_accel_1_vs_3"]),
        }

        gate = item["gate_price"]
        if gate is None:
            raise RuntimeError(f"missing gate price for {pid}")
        for horizon in (1, 2, 3):
            side_ret = f(b[f"t{horizon}_confirm_side_return_pct"])
            if side_ret is None:
                raise RuntimeError(f"missing T+{horizon} return for {pid}")
            cp, state, above_upper, above_lower = checkpoint_state(
                float(gate),
                side_ret,
                lower,
                upper,
            )
            item.update(
                {
                    f"t{horizon}_side_return_pct": side_ret,
                    f"t{horizon}_price": cp,
                    f"t{horizon}_zone_state": state,
                    f"t{horizon}_vs_upper_pct": above_upper,
                    f"t{horizon}_vs_lower_pct": above_lower,
                    f"t{horizon}_taker_share": f(
                        b[f"t{horizon}_confirm_selected_taker_share"]
                    ),
                    f"t{horizon}_last_clv_selected": f(
                        b[f"t{horizon}_confirm_last_clv_selected"]
                    ),
                    f"t{horizon}_last_body_selected": f(
                        b[f"t{horizon}_confirm_last_body_selected"]
                    ),
                    f"t{horizon}_last_rejection_wick": f(
                        b[f"t{horizon}_confirm_last_rejection_wick"]
                    ),
                    f"t{horizon}_selected_slope5_norm": f(
                        b[f"t{horizon}_f_f_selected_slope5_norm"]
                    ),
                    f"t{horizon}_reversal_pressure": f(
                        b[f"t{horizon}_f_micro_reversal_pressure"]
                    ),
                }
            )

        out.append(item)

    out.sort(key=lambda x: (int(x["opened_at_ms"]), str(x["position_id"])))

    cohort_mix = Counter(x["future_outcome_label"] for x in out)
    group_mix = Counter(x["outcome_group"] for x in out)
    split_mix = Counter(x["chrono_split"] for x in out)

    geometry: dict[str, Any] = {}
    geometry_fields = [
        "zone_departure_atr",
        "zone_volume_ratio",
        "zone_width_atr",
        "zone_age_min",
        "penetration_frac",
        "room_to_upper_pct",
        "depth_from_lower_pct",
        "nearest_demand_pct",
    ]
    for field in geometry_fields:
        geometry[field] = {}
        for group in ("GOOD", "BAD", "RTF"):
            values = [
                float(x[field])
                for x in out
                if x["outcome_group"] == group and x[field] is not None
            ]
            geometry[field][group] = {
                "n": len(values),
                "median": r(med(values)),
            }

    state_tables: dict[str, Any] = {}
    for horizon in (1, 2, 3):
        key = f"t{horizon}_zone_state"
        state_tables[f"T+{horizon}"] = {}
        for state in ("BELOW", "INSIDE", "ABOVE"):
            rows = [x for x in out if x[key] == state]
            state_tables[f"T+{horizon}"][state] = {
                "ALL": state_metrics(rows),
                "TRAIN": state_metrics(
                    [x for x in rows if x["chrono_split"] == "TRAIN"]
                ),
                "VALIDATION": state_metrics(
                    [x for x in rows if x["chrono_split"] == "VALIDATION"]
                ),
                "RESERVE": state_metrics(
                    [x for x in rows if x["chrono_split"] == "RESERVE"]
                ),
            }

    auc_fields = [
        "penetration_frac",
        "room_to_upper_pct",
        "zone_departure_atr",
        "zone_volume_ratio",
        "zone_width_atr",
        "zone_age_min",
        "t0_gate_side_ret_3m_pct",
        "t0_gate_taker_share",
        "t0_selected_slope5_norm",
        "t0_vwap_extension20",
        "t0_coin_minus_market_15m",
        "t0_micro_accel_1_vs_3",
        "t1_side_return_pct",
        "t1_taker_share",
        "t1_selected_slope5_norm",
        "t2_side_return_pct",
        "t2_taker_share",
        "t2_last_clv_selected",
        "t2_last_body_selected",
        "t2_selected_slope5_norm",
        "t3_side_return_pct",
        "t3_taker_share",
        "t3_last_body_selected",
        "t3_selected_slope5_norm",
        "t3_reversal_pressure",
    ]
    auc_screen: list[dict[str, Any]] = []
    classified = [x for x in out if x["outcome_group"] in {"GOOD", "BAD"}]
    for field in auc_fields:
        pairs = [
            (
                f(x[field]),
                1 if x["outcome_group"] == "GOOD" else 0,
            )
            for x in classified
        ]
        raw_auc = auc(pairs)
        if raw_auc is None:
            continue
        auc_screen.append(
            {
                "feature": field,
                "raw_auc_good_high": r(raw_auc, 4),
                "separation_auc": r(max(raw_auc, 1.0 - raw_auc), 4),
                "direction": "HIGHER_GOOD" if raw_auc >= 0.5 else "LOWER_GOOD",
            }
        )
    auc_screen.sort(key=lambda x: float(x["separation_auc"]), reverse=True)

    rejection_t2 = [x for x in out if x["t2_zone_state"] == "BELOW"]
    rejection_t3 = [x for x in out if x["t3_zone_state"] == "BELOW"]
    acceptance_t3 = [x for x in out if x["t3_zone_state"] == "ABOVE"]

    latency_values = [
        float(x["fill_latency_ms"])
        for x in out
        if x["fill_latency_ms"] is not None
    ]
    latency_values.sort()

    summary = {
        "version": VERSION,
        "contract": {
            "cohort": "inside FRESH 15m supply at actual entry",
            "rows": len(out),
            "good_definition": sorted(GOOD_CLASSES),
            "bad_definition": sorted(BAD_CLASSES),
            "ambiguous_held_out": sorted(AMBIGUOUS_CLASSES),
            "threshold_optimization": False,
            "production_authority": "NONE",
        },
        "cohort_mix": dict(cohort_mix),
        "group_mix": dict(group_mix),
        "split_mix": dict(split_mix),
        "timing": {
            "fill_latency_median_ms": r(med(latency_values), 1),
            "fill_latency_p90_ms": r(
                latency_values[int(0.90 * (len(latency_values) - 1))], 1
            ),
            "fill_latency_max_ms": r(max(latency_values), 1),
            "checkpoint_anchor": "Stage11C gate_current_price",
        },
        "geometry": geometry,
        "univariate_screen": auc_screen,
        "checkpoint_states": state_tables,
        "key_findings": {
            "T2_BELOW_LOWER": state_metrics(rejection_t2),
            "T3_BELOW_LOWER": state_metrics(rejection_t3),
            "T3_ABOVE_UPPER": state_metrics(acceptance_t3),
        },
        "interpretation": {
            "entry": (
                "Fresh 15m supply remains a WAIT/REQUIRE_PROOF context, "
                "not an unconditional production block."
            ),
            "rejection": (
                "Falling below the lower boundary by T+2/T+3 is a strong "
                "causal rejection state and candidate abort/early-exit signal."
            ),
            "acceptance": (
                "Trading above the upper boundary by T+3 enriches winners, "
                "but sample size and reserve transport are insufficient for "
                "immediate-entry authority; test breakout acceptance plus retest."
            ),
        },
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "lq3a_fresh15m_trade_level.csv"
    keys: list[str] = []
    seen: set[str] = set()
    for row in out:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(out)

    (output_dir / "lq3a_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()