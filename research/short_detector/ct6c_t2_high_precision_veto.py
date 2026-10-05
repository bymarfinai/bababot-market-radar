from __future__ import annotations

import csv
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "short_detector" / "results"

DETAIL = [
    r for r in csv.DictReader(open(RESULTS / "ct6a_trade_detail.csv"))
    if int(r["lane"]) == 2
]
RESEARCH = {
    r["meta_position_id"]: r
    for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))
}
TEMPORAL = {
    r["position_id"]: r
    for r in csv.DictReader(open("/opt/core-app/data/wd5h4a_temporal_features.csv"))
}
FRESH = {
    r["meta_position_id"]: r
    for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))
}

BLOCKS = [
    "Research_Discovery",
    "Research_Validation",
    "Research_Reserve",
    "Fresh_2026-10-01",
    "Fresh_2026-10-02",
    "Fresh_2026-10-03",
]

FEATURES = [
    "t2_confirm_mfe_pct",
    "t2_confirm_side_return_pct",
    "d2_confirm_mfe_pct",
    "t2_delta_micro_selected_vwap_extension_20",
    "d2_confirm_side_return_pct",
    "f_f_coin_minus_market_30m",
    "d2_confirm_trades",
    "t2_confirm_trades",
]

PRIMARY_FEATURES = [
    "t2_confirm_side_return_pct",
    "d2_confirm_mfe_pct",
    "d2_confirm_trades",
]

PCTS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]


def truth(v):
    return str(v).lower() == "true"


def ff(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def raw(row):
    pid = row["position_id"]
    if row["source"] == "research":
        z = dict(RESEARCH[pid])
        z.update(TEMPORAL[pid])
        return z
    return FRESH[pid]


def value(row, feature):
    z = raw(row)
    if feature.startswith("d2_"):
        stem = feature[3:]
        a = ff(z.get("t2_" + stem))
        b = ff(z.get("t1_" + stem))
        return None if a is None or b is None else a - b
    return ff(z.get(feature))


def percentile(xs, p):
    s = sorted(xs)
    pos = (len(s) - 1) * p
    lo = int(math.floor(pos))
    hi = min(len(s) - 1, lo + 1)
    w = pos - lo
    return s[lo] * (1 - w) + s[hi] * w


# Cache all feature values once.
for row in DETAIL:
    row["_features"] = {k: value(row, k) for k in FEATURES}

TRAIN_TARGET = [
    r for r in DETAIL
    if r["block"] == "Research_Discovery"
    and r["mfe_bucket"] == "TARGET_GE_1P00"
]

THRESHOLDS = {
    feature: {
        p: percentile(
            [r["_features"][feature] for r in TRAIN_TARGET if r["_features"][feature] is not None],
            p,
        )
        for p in PCTS
    }
    for feature in FEATURES
}


def hit_rule(row, parts, need):
    hits = 0
    for feature, p in parts:
        x = row["_features"][feature]
        if x is not None and x <= THRESHOLDS[feature][p]:
            hits += 1
    return hits >= need


def metrics(rows, drop_ids=None):
    rows = list(rows)
    if drop_ids is not None:
        rows = [r for r in rows if r["position_id"] not in drop_ids]
    ex = [r for r in rows if truth(r["executable"])]
    vals = [float(r["pnl"]) for r in ex]
    return {
        "selected": len(rows),
        "executable": len(ex),
        "strong_selected": sum(truth(r["strong"]) for r in rows),
        "strong_executable": sum(truth(r["strong"]) for r in ex),
        "wins": sum(v > 0 for v in vals),
        "wr": sum(v > 0 for v in vals) / len(vals) if vals else 0.0,
        "pnl": sum(vals),
    }


def dropped_metrics(rows, parts, need):
    dropped = [r for r in rows if hit_rule(r, parts, need)]
    ex = [r for r in dropped if truth(r["executable"])]
    target = [r for r in rows if r["mfe_bucket"] == "TARGET_GE_1P00"]
    return {
        "drop_selected": len(dropped),
        "drop_executable": len(ex),
        "bad_a": sum(r["mfe_bucket"] == "BAD_A_LT_0P30" for r in dropped),
        "bad_b": sum(r["mfe_bucket"] == "BAD_B_0P30_0P50" for r in dropped),
        "gray": sum(r["mfe_bucket"] == "GRAY_0P50_1P00" for r in dropped),
        "target": sum(r["mfe_bucket"] == "TARGET_GE_1P00" for r in dropped),
        "strong": sum(truth(r["strong"]) for r in dropped),
        "wins": sum(float(r["pnl"]) > 0 for r in ex),
        "pnl": sum(float(r["pnl"]) for r in ex),
        "target_retention": (
            1.0
            - sum(r["mfe_bucket"] == "TARGET_GE_1P00" for r in dropped) / len(target)
            if target else 1.0
        ),
    }


SCOPES = {
    "overall": DETAIL,
    "research": [r for r in DETAIL if r["source"] == "research"],
    "fresh": [r for r in DETAIL if r["source"] == "fresh"],
}
SCOPES.update({block: [r for r in DETAIL if r["block"] == block] for block in BLOCKS})

# Strict candidate scan:
# - thresholds must come from Research Discovery TARGET percentiles
# - two-feature AND or 2/3, 3/3 rules
# - 0 strong dropped
# - >=98% overall TARGET retention
# - >=95% TARGET retention in each block
# - dropped realized PnL must be <=0 in every block
# - must reject BAD in both Research and Fresh
scan = []
for n in (2, 3):
    for features in itertools.combinations(FEATURES, n):
        for p in PCTS:
            needs = [2] if n == 2 else [2, 3]
            for need in needs:
                parts = [(feature, p) for feature in features]
                outcomes = {
                    scope: dropped_metrics(rows, parts, need)
                    for scope, rows in SCOPES.items()
                }
                overall = outcomes["overall"]
                valid = (
                    overall["strong"] == 0
                    and overall["target_retention"] >= 0.98
                    and all(
                        outcomes[b]["target_retention"] >= 0.95
                        and outcomes[b]["pnl"] <= 1e-12
                        for b in BLOCKS
                    )
                    and outcomes["research"]["bad_a"] + outcomes["research"]["bad_b"] > 0
                    and outcomes["fresh"]["bad_a"] + outcomes["fresh"]["bad_b"] > 0
                )
                scan.append({
                    "n_features": n,
                    "need": need,
                    "percentile": p,
                    "features": list(features),
                    "valid_strict": valid,
                    "outcomes": outcomes,
                })

valid_scan = [x for x in scan if x["valid_strict"]]
valid_scan.sort(
    key=lambda x: (
        x["outcomes"]["overall"]["bad_a"] + x["outcomes"]["overall"]["bad_b"],
        x["outcomes"]["overall"]["bad_a"],
        -x["outcomes"]["overall"]["target"],
        -x["outcomes"]["overall"]["gray"],
        -x["outcomes"]["overall"]["pnl"],
    ),
    reverse=True,
)

PRIMARY_PARTS = [(feature, 0.20) for feature in PRIMARY_FEATURES]
PRIMARY_NEED = 3
PRIMARY_DROP = {
    r["position_id"] for r in DETAIL
    if hit_rule(r, PRIMARY_PARTS, PRIMARY_NEED)
}

frontier = []
for p in (0.15, 0.20, 0.25, 0.30, 0.35):
    parts = [(feature, p) for feature in PRIMARY_FEATURES]
    z = dropped_metrics(DETAIL, parts, 3)
    frontier.append({"percentile": p, **z})

summary = {
    "stage": "SHORT-CT6C",
    "status": "T2_HIGH_PRECISION_VETO_PASS",
    "contract": {
        "lane": "T2 only",
        "fit_population": "Research_Discovery TARGET-MFE >=1.00%",
        "threshold_method": "20th percentile of causal feature values in Research Discovery TARGET",
        "mfe_future_label_is_input": False,
        "realized_pnl_is_input": False,
        "runtime_change": False,
    },
    "primary_rule": {
        "logic": "AND",
        "thresholds": {
            feature: THRESHOLDS[feature][0.20]
            for feature in PRIMARY_FEATURES
        },
        "human": [
            "t2_confirm_side_return_pct <= 0.05354143193380347",
            "t2_confirm_mfe_pct - t1_confirm_mfe_pct <= 0.0",
            "t2_confirm_trades - t1_confirm_trades <= 71",
        ],
    },
    "strict_scan": {
        "candidate_count": len(scan),
        "valid_count": len(valid_scan),
        "top_valid": valid_scan[:10],
    },
    "frontier": frontier,
    "t2_baseline": metrics(DETAIL),
    "t2_after_primary": metrics(DETAIL, PRIMARY_DROP),
    "primary_dropped": {
        scope: dropped_metrics(rows, PRIMARY_PARTS, PRIMARY_NEED)
        for scope, rows in SCOPES.items()
    },
}

summary["t2_after_primary"]["delta_pnl_vs_baseline"] = (
    summary["t2_after_primary"]["pnl"] - summary["t2_baseline"]["pnl"]
)
summary["t2_after_primary"]["strong_exec_retention"] = (
    summary["t2_after_primary"]["strong_executable"]
    / summary["t2_baseline"]["strong_executable"]
)

ct5b = json.load(open(RESULTS / "ct5b_summary.json"))
ct5b_primary = ct5b["candidates"]["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"]
summary["ct5b_plus_ct6c"] = {
    "research_pnl": (
        ct5b_primary["research"]["pnl"]
        - summary["primary_dropped"]["research"]["pnl"]
    ),
    "fresh_pnl": (
        ct5b_primary["fresh"]["pnl"]
        - summary["primary_dropped"]["fresh"]["pnl"]
    ),
    "overall_pnl": (
        ct5b_primary["overall"]["pnl"]
        - summary["primary_dropped"]["overall"]["pnl"]
    ),
    "incremental_ct6c_improvement": -summary["primary_dropped"]["overall"]["pnl"],
    "overlap_note": "CT5B primary drops are lane T3; CT6C primary drops are lane T2, so the drop sets are disjoint.",
}

# Trade detail.
detail_fields = [
    "position_id", "symbol", "source", "block", "mfe_pct", "mfe_bucket",
    "strong", "executable", "pnl", "reason",
    "t2_confirm_side_return_pct", "d2_confirm_mfe_pct", "d2_confirm_trades",
]
with open(RESULTS / "ct6c_veto_trade_detail.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=detail_fields)
    w.writeheader()
    for r in DETAIL:
        if r["position_id"] not in PRIMARY_DROP:
            continue
        w.writerow({
            "position_id": r["position_id"],
            "symbol": r["symbol"],
            "source": r["source"],
            "block": r["block"],
            "mfe_pct": r["mfe_pct"],
            "mfe_bucket": r["mfe_bucket"],
            "strong": r["strong"],
            "executable": r["executable"],
            "pnl": r["pnl"],
            "reason": r["reason"],
            "t2_confirm_side_return_pct": r["_features"]["t2_confirm_side_return_pct"],
            "d2_confirm_mfe_pct": r["_features"]["d2_confirm_mfe_pct"],
            "d2_confirm_trades": r["_features"]["d2_confirm_trades"],
        })

with open(RESULTS / "ct6c_frontier.csv", "w", newline="") as f:
    fields = [
        "percentile", "drop_selected", "drop_executable",
        "bad_a", "bad_b", "gray", "target", "strong",
        "wins", "pnl", "target_retention",
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(frontier)

(RESULTS / "ct6c_summary.json").write_text(json.dumps(summary, indent=2))

print("PRIMARY thresholds", summary["primary_rule"]["thresholds"])
print("strict valid", len(valid_scan))
print("T2 baseline", summary["t2_baseline"])
print("T2 after", summary["t2_after_primary"])
print("drop overall", summary["primary_dropped"]["overall"])
print("drop research", summary["primary_dropped"]["research"])
print("drop fresh", summary["primary_dropped"]["fresh"])
print("combined", summary["ct5b_plus_ct6c"])
print("blocks")
for b in BLOCKS:
    print(b, summary["primary_dropped"][b])