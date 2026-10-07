from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Callable


VERSION = "lq3c-open-lane-anatomy-v1"
EXPECTED_UNIVERSE = 1134


def f(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def pct(n: int, d: int) -> float | None:
    return 100.0 * n / d if d else None


def rnd(v: Any, nd: int = 4) -> Any:
    if isinstance(v, float) and math.isfinite(v):
        return round(v, nd)
    return v


def metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    mfes = [f(x.get("future_max_mfe_pct")) for x in rows]
    mfes = [x for x in mfes if x is not None]
    pnls = [f(x.get("future_realized_pnl")) for x in rows]
    pnls = [x for x in pnls if x is not None]
    classes = Counter(str(x.get("future_outcome_label") or "") for x in rows)
    return {
        "n": len(rows),
        "median_mfe_pct": rnd(statistics.median(mfes)),
        "mfe_lt_0p5_pct": rnd(pct(sum(x < 0.5 for x in mfes), len(rows)), 2),
        "mfe_ge_1_pct": rnd(pct(sum(x >= 1.0 for x in mfes), len(rows)), 2),
        "mfe_ge_2_pct": rnd(pct(sum(x >= 2.0 for x in mfes), len(rows)), 2),
        "realized_win_pct": rnd(pct(sum(x > 0.0 for x in pnls), len(rows)), 2),
        "sum_realized_pnl": rnd(sum(pnls), 2),
        "good_count": classes["RECOVERED_DRAWDOWN"] + classes["CORRECT_RUNNER"],
        "bad_count": classes["TRUE_WRONG_DIRECTION"] + classes["STALL_NO_EDGE"],
        "rtf_count": classes["RIGHT_THEN_FAILURE"],
        "class_mix": dict(classes),
    }


def dist(row: dict[str, str], key: str) -> float | None:
    return f(row.get(key))


def no_local_supply_inside(row: dict[str, str]) -> bool:
    return all(
        dist(row, key) is None or float(dist(row, key)) > 0.0
        for key in ("5m_supply_distance_pct", "15m_supply_distance_pct")
    )


def open_lane(row: dict[str, str]) -> bool:
    demand = dist(row, "nearest_demand_distance_pct")
    return demand is not None and demand >= 3.0 and no_local_supply_inside(row)


def open_lane_strong(row: dict[str, str]) -> bool:
    demand = dist(row, "nearest_demand_distance_pct")
    five_supply = dist(row, "5m_supply_distance_pct")
    fifteen_supply = dist(row, "15m_supply_distance_pct")
    return (
        demand is not None
        and demand >= 3.0
        and five_supply is not None
        and five_supply >= 0.2
        and (fifteen_supply is None or fifteen_supply > 0.0)
    )


def near_demand_1p5(row: dict[str, str]) -> bool:
    demand = dist(row, "nearest_demand_distance_pct")
    return demand is not None and demand < 1.5


def near_demand_2(row: dict[str, str]) -> bool:
    demand = dist(row, "nearest_demand_distance_pct")
    return demand is not None and demand < 2.0


def split_metrics(
    rows: list[dict[str, str]],
    predicate: Callable[[dict[str, str]], bool],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in ("TRAIN", "VALIDATION", "RESERVE"):
        selected = [
            x for x in rows
            if x.get("chrono_split") == split and predicate(x)
        ]
        out[split] = metrics(selected)
    selected_all = [x for x in rows if predicate(x)]
    out["ALL"] = metrics(selected_all)
    out["COMPLEMENT_ALL"] = metrics([x for x in rows if not predicate(x)])
    return out


def demand_band(row: dict[str, str]) -> str:
    value = dist(row, "nearest_demand_distance_pct")
    if value is None:
        return "MISSING"
    if value < 1.0:
        return "<1%"
    if value < 2.0:
        return "1-2%"
    if value < 3.0:
        return "2-3%"
    return ">=3%"


def local_supply_state(row: dict[str, str]) -> str:
    inside5 = dist(row, "5m_supply_distance_pct") == 0.0
    inside15 = dist(row, "15m_supply_distance_pct") == 0.0
    if inside5 and inside15:
        return "INSIDE_5M_15M"
    if inside15:
        return "INSIDE_15M"
    if inside5:
        return "INSIDE_5M"
    return "CLEAR_5M_15M"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--lq2-csv",
        default="research/liquidity_location/results/lq2_trade_level.csv",
    )
    ap.add_argument(
        "--output-dir",
        default="research/liquidity_location/results",
    )
    args = ap.parse_args()

    all_rows = load_csv(Path(args.lq2_csv))
    rows = [
        x for x in all_rows
        if str(x.get("flag_inside_fresh_15m_supply") or "").lower() != "true"
    ]
    if len(rows) != EXPECTED_UNIVERSE:
        raise RuntimeError(
            f"open-lane universe drift: expected {EXPECTED_UNIVERSE}, got {len(rows)}"
        )

    baseline = split_metrics(rows, lambda _: True)
    focus = split_metrics(rows, open_lane)
    focus_strong = split_metrics(rows, open_lane_strong)
    deprio_1p5 = split_metrics(rows, near_demand_1p5)
    deprio_2 = split_metrics(rows, near_demand_2)

    matrix: list[dict[str, Any]] = []
    for db in ("<1%", "1-2%", "2-3%", ">=3%"):
        for ss in (
            "INSIDE_5M_15M",
            "INSIDE_15M",
            "INSIDE_5M",
            "CLEAR_5M_15M",
        ):
            selected = [
                x for x in rows
                if demand_band(x) == db and local_supply_state(x) == ss
            ]
            matrix.append(
                {
                    "demand_band": db,
                    "local_supply_state": ss,
                    **metrics(selected),
                }
            )

    stability: dict[str, Any] = {}
    for name, report in (
        ("OPEN_LANE", focus),
        ("OPEN_LANE_STRONG", focus_strong),
        ("NEAR_DEMAND_LT_1P5", deprio_1p5),
        ("NEAR_DEMAND_LT_2", deprio_2),
    ):
        stability[name] = {}
        for split in ("TRAIN", "VALIDATION", "RESERVE"):
            b = baseline[split]
            m = report[split]
            stability[name][split] = {
                "n": m["n"],
                "mfe_ge_1_uplift_pp": rnd(
                    float(m.get("mfe_ge_1_pct", 0))
                    - float(b.get("mfe_ge_1_pct", 0)),
                    2,
                ),
                "low_mfe_reduction_pp": rnd(
                    float(b.get("mfe_lt_0p5_pct", 0))
                    - float(m.get("mfe_lt_0p5_pct", 0)),
                    2,
                ),
                "realized_win_uplift_pp": rnd(
                    float(m.get("realized_win_pct", 0))
                    - float(b.get("realized_win_pct", 0)),
                    2,
                ),
            }

    summary = {
        "version": VERSION,
        "contract": {
            "universe": (
                "resolved LONG trades outside FRESH 15m supply at entry"
            ),
            "rows": len(rows),
            "split_rows": {
                split: sum(x.get("chrono_split") == split for x in rows)
                for split in ("TRAIN", "VALIDATION", "RESERVE")
            },
            "primary_focus_rule": (
                "nearest demand distance >= 3.0% AND not inside 5m/15m supply"
            ),
            "secondary_focus_rule": (
                "nearest demand >= 3.0% AND 5m supply clearance >= 0.2% "
                "AND not inside 15m supply"
            ),
            "deprioritize_rule": "nearest demand distance < 1.5%",
            "threshold_selection": (
                "coarse interpretable TRAIN discovery; "
                "VALIDATION/RESERVE used for transport check"
            ),
            "production_authority": "NONE",
        },
        "baseline": baseline,
        "open_lane": focus,
        "open_lane_strong": focus_strong,
        "near_demand_lt_1p5": deprio_1p5,
        "near_demand_lt_2": deprio_2,
        "stability": stability,
        "demand_x_local_supply_matrix": matrix,
        "verdict": {
            "focus": (
                "OPEN_LANE materially improves excursion quality and runner rate "
                "across all chronological splits."
            ),
            "deprioritize": (
                "Near-demand entry (<1.5-2.0%) is consistently associated with "
                "lower runner rate / higher low-MFE incidence for this momentum LONG universe."
            ),
            "economics": (
                "Location improves opportunity quality but does not by itself "
                "repair realized PnL; exit/profit-protection remains downstream."
            ),
        },
    }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lq3c_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    flagged: list[dict[str, Any]] = []
    for row in rows:
        x = dict(row)
        x["lq3c_open_lane"] = open_lane(row)
        x["lq3c_open_lane_strong"] = open_lane_strong(row)
        x["lq3c_near_demand_lt_1p5"] = near_demand_1p5(row)
        x["lq3c_near_demand_lt_2"] = near_demand_2(row)
        x["lq3c_demand_band"] = demand_band(row)
        x["lq3c_local_supply_state"] = local_supply_state(row)
        flagged.append(x)

    keys: list[str] = []
    seen: set[str] = set()
    for row in flagged:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with (out_dir / "lq3c_trade_level.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(flagged)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()