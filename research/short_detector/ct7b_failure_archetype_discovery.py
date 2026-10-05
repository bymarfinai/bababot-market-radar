from __future__ import annotations

import csv
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "short_detector" / "results"

DETAIL = list(csv.DictReader(open(RESULTS / "ct6a_trade_detail.csv")))
RESEARCH = {
    r["meta_position_id"]: r
    for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))
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
    "f_micro_distance_selected_extreme_15m",
    "f_ret_1h_pct_for_selected",
    "f_f_relative_overextension_30m",
    "f_median_abs_ret_5m_pct",
    "f_context_quote_volume_5m",
    "f_gate_side_ret_3m_pct",
    "f_f_coin_residual_5m_vs_btc",
    "f_micro_selected_vwap_extension_20",
]

PCTS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45]

FROZEN_ARCHETYPES = {
    "A1_LOW_DISPLACEMENT": {
        "features": [
            "f_micro_distance_selected_extreme_15m",
            "f_ret_1h_pct_for_selected",
        ],
        "need": 2,
        "percentile": 0.45,
        "description": "close to the selected extreme AND weak 1h selected-side displacement",
    },
    "A2_WEAK_RELATIVE_EXPANSION": {
        "features": [
            "f_ret_1h_pct_for_selected",
            "f_f_relative_overextension_30m",
            "f_micro_selected_vwap_extension_20",
        ],
        "need": 3,
        "percentile": 0.45,
        "description": "weak 1h displacement AND weak relative 30m move AND weak VWAP extension",
    },
    "A3_LOW_ENERGY_RESIDUAL": {
        "features": [
            "f_micro_distance_selected_extreme_15m",
            "f_median_abs_ret_5m_pct",
            "f_f_coin_residual_5m_vs_btc",
        ],
        "need": 3,
        "percentile": 0.45,
        "description": "close to selected extreme AND low movement amplitude AND weak idiosyncratic move vs BTC",
    },
}


def truth(v):
    return str(v).lower() == "true"


def ff(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def raw(row):
    return RESEARCH[row["position_id"]] if row["source"] == "research" else FRESH[row["position_id"]]


def percentile(xs, p):
    s = sorted(xs)
    pos = (len(s) - 1) * p
    lo = int(math.floor(pos))
    hi = min(len(s) - 1, lo + 1)
    w = pos - lo
    return s[lo] * (1 - w) + s[hi] * w


for row in DETAIL:
    row["_v"] = {k: ff(raw(row).get(k)) for k in FEATURES}

TRAIN_TARGET = [
    r for r in DETAIL
    if r["block"] == "Research_Discovery"
    and r["mfe_bucket"] == "TARGET_GE_1P00"
]

THRESHOLDS = {
    feature: {
        p: percentile(
            [r["_v"][feature] for r in TRAIN_TARGET if r["_v"][feature] is not None],
            p,
        )
        for p in PCTS
    }
    for feature in FEATURES
}


def hit(row, features, need, p):
    return sum(
        row["_v"][feature] is not None
        and row["_v"][feature] <= THRESHOLDS[feature][p]
        for feature in features
    ) >= need


def ids_for(features, need, p, rows=None):
    rows = DETAIL if rows is None else rows
    return {
        r["position_id"]
        for r in rows
        if hit(r, features, need, p)
    }


def metrics(rows, ids):
    dropped = [r for r in rows if r["position_id"] in ids]
    ex = [r for r in dropped if truth(r["executable"])]
    bad = [
        r for r in rows
        if r["mfe_bucket"] in ("BAD_A_LT_0P30", "BAD_B_0P30_0P50")
    ]
    target = [r for r in rows if r["mfe_bucket"] == "TARGET_GE_1P00"]
    bad_drop = [
        r for r in dropped
        if r["mfe_bucket"] in ("BAD_A_LT_0P30", "BAD_B_0P30_0P50")
    ]
    target_drop = [r for r in dropped if r["mfe_bucket"] == "TARGET_GE_1P00"]
    return {
        "selected": len(dropped),
        "executable": len(ex),
        "bad_a": sum(r["mfe_bucket"] == "BAD_A_LT_0P30" for r in dropped),
        "bad_b": sum(r["mfe_bucket"] == "BAD_B_0P30_0P50" for r in dropped),
        "bad_total": len(bad_drop),
        "bad_recall": len(bad_drop) / len(bad) if bad else 0.0,
        "gray": sum(r["mfe_bucket"] == "GRAY_0P50_1P00" for r in dropped),
        "target": len(target_drop),
        "target_hit_rate": len(target_drop) / len(target) if target else 0.0,
        "bad_vs_target_precision": (
            len(bad_drop) / (len(bad_drop) + len(target_drop))
            if len(bad_drop) + len(target_drop) else 0.0
        ),
        "strong_selected": sum(truth(r["strong"]) for r in dropped),
        "strong_executable": sum(truth(r["strong"]) for r in ex),
        "wins": sum(float(r["pnl"]) > 0 for r in ex),
        "pnl": sum(float(r["pnl"]) for r in ex),
    }


# Reconstruct the transport candidate universe used during discovery.
train = [r for r in DETAIL if r["block"] == "Research_Discovery"]
holdout_research = [
    r for r in DETAIL
    if r["block"] in ("Research_Validation", "Research_Reserve")
]
fresh = [r for r in DETAIL if r["source"] == "fresh"]
oos = [r for r in DETAIL if r["block"] != "Research_Discovery"]

candidate_rows = []

for n in (2, 3):
    for feature_set in itertools.combinations(FEATURES, n):
        for p in PCTS:
            needs = [n] if n == 2 else [2, 3]
            for need in needs:
                ids = ids_for(feature_set, need, p)
                mt = metrics(train, ids)
                mh = metrics(holdout_research, ids)
                mf = metrics(fresh, ids)
                mo = metrics(oos, ids)
                ma = metrics(DETAIL, ids)

                block_metrics = {
                    b: metrics([r for r in DETAIL if r["block"] == b], ids)
                    for b in BLOCKS[1:]
                }
                oos_block_agree = sum(
                    z["bad_vs_target_precision"] >= 0.50
                    for z in block_metrics.values()
                )

                transport_candidate = (
                    mt["bad_total"] >= 12
                    and mt["bad_vs_target_precision"] >= 0.72
                    and mt["target_hit_rate"] <= 0.20
                    and mo["bad_total"] >= 25
                    and mo["bad_vs_target_precision"] >= 0.65
                    and mf["bad_total"] >= 20
                    and mf["bad_vs_target_precision"] >= 0.68
                    and mh["bad_total"] >= 3
                    and oos_block_agree >= 4
                )

                candidate_rows.append({
                    "n_features": n,
                    "need": need,
                    "percentile": p,
                    "features": "|".join(feature_set),
                    "transport_candidate": transport_candidate,
                    "train_bad": mt["bad_total"],
                    "train_precision": mt["bad_vs_target_precision"],
                    "oos_bad": mo["bad_total"],
                    "oos_precision": mo["bad_vs_target_precision"],
                    "holdout_research_bad": mh["bad_total"],
                    "holdout_research_precision": mh["bad_vs_target_precision"],
                    "fresh_bad": mf["bad_total"],
                    "fresh_precision": mf["bad_vs_target_precision"],
                    "all_bad": ma["bad_total"],
                    "all_target": ma["target"],
                    "all_strong": ma["strong_selected"],
                    "all_pnl": ma["pnl"],
                })

transport = [r for r in candidate_rows if r["transport_candidate"]]

archetypes = {}
archetype_ids = {}
for name, spec in FROZEN_ARCHETYPES.items():
    ids = ids_for(spec["features"], spec["need"], spec["percentile"])
    archetype_ids[name] = ids
    archetypes[name] = {
        **spec,
        "thresholds": {
            feature: THRESHOLDS[feature][spec["percentile"]]
            for feature in spec["features"]
        },
        "overall": metrics(DETAIL, ids),
        "by_block": {
            b: metrics([r for r in DETAIL if r["block"] == b], ids)
            for b in BLOCKS
        },
        "by_lane": {
            str(lane): metrics([r for r in DETAIL if int(r["lane"]) == lane], ids)
            for lane in range(4)
        },
        "research": metrics([r for r in DETAIL if r["source"] == "research"], ids),
        "fresh": metrics([r for r in DETAIL if r["source"] == "fresh"], ids),
    }

# BAD-only overlap.
bad_ids = {
    r["position_id"]
    for r in DETAIL
    if r["mfe_bucket"] in ("BAD_A_LT_0P30", "BAD_B_0P30_0P50")
}
overlap = []
names = list(FROZEN_ARCHETYPES)
for a in names:
    for b in names:
        aa = archetype_ids[a] & bad_ids
        bb = archetype_ids[b] & bad_ids
        jaccard = len(aa & bb) / len(aa | bb) if aa | bb else 0.0
        overlap.append({
            "archetype_a": a,
            "archetype_b": b,
            "bad_intersection": len(aa & bb),
            "bad_union": len(aa | bb),
            "bad_jaccard": jaccard,
        })

union_ids = set().union(*archetype_ids.values())

# Marginal BAD coverage in frozen greedy order.
covered_bad = set()
marginal = {}
for name in names:
    current_bad = archetype_ids[name] & bad_ids
    marginal[name] = {
        "bad_total": len(current_bad),
        "marginal_bad": len(current_bad - covered_bad),
    }
    covered_bad |= current_bad

summary = {
    "stage": "SHORT-CT7B",
    "status": "FAILURE_ARCHETYPE_DISCOVERY_PASS_NOT_VETO_READY",
    "contract": {
        "t_features_used": False,
        "lane_used_as_basis": False,
        "feature_basis": "8 independent non-temporal morphology representatives from CT7A",
        "threshold_fit": "Research Discovery TARGET-MFE quantiles only",
        "candidate_selection": "transport across known Research holdout and Fresh blocks",
        "future_mfe_use": "label only",
        "realized_pnl_use": "evaluation only",
        "runtime_change": False,
    },
    "transport_candidate_count": len(transport),
    "archetypes": archetypes,
    "marginal_bad_coverage": marginal,
    "union": {
        "overall": metrics(DETAIL, union_ids),
        "by_block": {
            b: metrics([r for r in DETAIL if r["block"] == b], union_ids)
            for b in BLOCKS
        },
        "by_lane": {
            str(lane): metrics([r for r in DETAIL if int(r["lane"]) == lane], union_ids)
            for lane in range(4)
        },
    },
    "warning": (
        "Archetypes identify failure territory, not executable vetoes. "
        "The union captures substantial BAD but also many TARGET/strong trades; "
        "CT7C must derive high-precision kill boundaries inside these archetypes."
    ),
}

(RESULTS / "ct7b_summary.json").write_text(json.dumps(summary, indent=2))

with open(RESULTS / "ct7b_candidate_archetypes.csv", "w", newline="") as f:
    fields = [
        "n_features", "need", "percentile", "features", "transport_candidate",
        "train_bad", "train_precision", "oos_bad", "oos_precision",
        "holdout_research_bad", "holdout_research_precision",
        "fresh_bad", "fresh_precision", "all_bad", "all_target",
        "all_strong", "all_pnl",
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(candidate_rows)

with open(RESULTS / "ct7b_overlap.csv", "w", newline="") as f:
    fields = [
        "archetype_a", "archetype_b",
        "bad_intersection", "bad_union", "bad_jaccard",
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(overlap)

with open(RESULTS / "ct7b_trade_membership.csv", "w", newline="") as f:
    fields = [
        "position_id", "symbol", "source", "block", "lane",
        "mfe_pct", "mfe_bucket", "strong", "executable", "pnl",
        *names, "archetype_count",
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in DETAIL:
        flags = {
            name: r["position_id"] in archetype_ids[name]
            for name in names
        }
        w.writerow({
            "position_id": r["position_id"],
            "symbol": r["symbol"],
            "source": r["source"],
            "block": r["block"],
            "lane": r["lane"],
            "mfe_pct": r["mfe_pct"],
            "mfe_bucket": r["mfe_bucket"],
            "strong": r["strong"],
            "executable": r["executable"],
            "pnl": r["pnl"],
            **flags,
            "archetype_count": sum(flags.values()),
        })

print("transport candidates", len(transport))
for name in names:
    print(name, archetypes[name]["overall"], "marginal", marginal[name])
print("union", summary["union"]["overall"])
print("overlap")
for row in overlap:
    if row["archetype_a"] < row["archetype_b"]:
        print(row)
print("blocks")
for b in BLOCKS:
    print(b, summary["union"]["by_block"][b])