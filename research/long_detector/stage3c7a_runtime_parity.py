"""Offline parity gate for PT-L1.

Usage on the research VPS:
  python research/long_detector/stage3c7a_runtime_parity.py \
    --data-dir /opt/core-app/data

The oracle is used only for regression comparison, never runtime inference.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from market_radar.long_detector_stage3c7a import (
    TEMPORAL_THRESHOLD_PCT,
    counterflow_veto,
    route_t0,
)

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "research/long_detector/results/stage3c7a_454_oracle.csv"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def causal_temporal_pass(row: dict[str, str], horizon: int) -> bool:
    value = row.get(f"t{horizon}_confirm_side_return_pct")
    target = row.get(f"t{horizon}_target_ms")
    end = row.get("primary_label_end_ms")
    if value in (None, "") or target in (None, "") or end in (None, ""):
        return False
    return (
        float(end) > float(target)
        and float(value) >= TEMPORAL_THRESHOLD_PCT
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    args = ap.parse_args()
    data = Path(args.data_dir)

    features = {
        r["meta_position_id"]: r
        for r in rows(data / "wd5h1_thesis_labeled_features.csv")
    }
    universe = [
        r for r in rows(data / "wd5h4a_temporal_features.csv")
        if r["side"] == "LONG"
        and r["primary_meta_label"] in {"META_WIN", "META_LOSS"}
    ]
    universe.sort(key=lambda r: (int(r["opened_at_ms"]), r["position_id"]))
    oracle = {r["position_id"]: r for r in rows(ORACLE)}

    selected: list[dict[str, str]] = []
    route_counts: Counter[str] = Counter()
    route_mismatch: list[str] = []
    for row in universe:
        pid = row["position_id"]
        f = features[pid]
        route, _ = route_t0(f)
        if route == "COUNTERFLOW":
            accept = not counterflow_veto(f)
        else:
            accept = any(causal_temporal_pass(row, h) for h in (1, 2, 3))
        if accept:
            selected.append(row)
            route_counts[route] += 1
            if pid in oracle and oracle[pid]["route"] != route:
                route_mismatch.append(pid)

    selected_ids = {r["position_id"] for r in selected}
    oracle_ids = set(oracle)
    strong = [
        r for r in selected
        if r["primary_meta_label"] == "META_WIN"
        and float(features[r["position_id"]]["future_max_mfe_pct"]) >= 1.0
    ]
    profitable_non_target = sum(
        1
        for r in selected
        if r not in strong
        and float(features[r["position_id"]]["future_realized_pnl"]) > 0
    )

    print(f"universe={len(universe)}")
    print(f"selected={len(selected)} strong={len(strong)} non_target={len(selected)-len(strong)}")
    print(f"profitable_non_target={profitable_non_target}")
    print(f"routes={dict(route_counts)}")
    print(f"extra={len(selected_ids-oracle_ids)} missing={len(oracle_ids-selected_ids)} route_mismatch={len(route_mismatch)}")

    assert len(universe) == 1236
    assert len(selected) == 454
    assert len(strong) == 150
    assert len(selected) - len(strong) == 304
    assert profitable_non_target == 39
    assert route_counts == Counter({"FLOW_ALIGNED": 297, "COUNTERFLOW": 157})
    assert selected_ids == oracle_ids
    assert not route_mismatch
    print("PTL1_RUNTIME_PARITY=PASS")


if __name__ == "__main__":
    main()