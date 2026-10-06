from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "short_detector" / "results"

DETAIL = list(csv.DictReader(open(RESULTS / "ct7b_trade_membership.csv")))
RESEARCH = {
    r["meta_position_id"]: r
    for r in csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv"))
}
FRESH = {
    r["meta_position_id"]: r
    for r in csv.DictReader(open("/tmp/s10h_fresh_features.csv"))
}
CT4 = [
    r for r in csv.DictReader(open(RESULTS / "ct4_trade_detail.csv"))
    if r["candidate"] == "T0075"
]

BLOCKS = [
    "Research_Discovery",
    "Research_Validation",
    "Research_Reserve",
    "Fresh_2026-10-01",
    "Fresh_2026-10-02",
    "Fresh_2026-10-03",
]

FEATURES = [
    "f_f_market_dispersion_5m",
    "f_new_accel_5_vs_15",
    "f_new_positioning_support",
    "f_context_quote_volume_24h",
    "f_micro_prev3_side_ret",
    "f_micro_side_ret_5m",
    "f_new_extension_60m_norm",
]


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

DISCOVERY_TARGET = [
    r for r in DETAIL
    if r["block"] == "Research_Discovery"
    and r["mfe_bucket"] == "TARGET_GE_1P00"
]

QUANTILES = {
    feature: {
        p: percentile(
            [r["_v"][feature] for r in DISCOVERY_TARGET if r["_v"][feature] is not None],
            p,
        )
        for p in (0.30, 0.35, 0.40, 0.60, 0.65, 0.70)
    }
    for feature in FEATURES
}

THRESHOLDS = {
    "market_dispersion_q70": QUANTILES["f_f_market_dispersion_5m"][0.70],
    "accel_5_vs_15_q70": QUANTILES["f_new_accel_5_vs_15"][0.70],
    "positioning_support_q30": QUANTILES["f_new_positioning_support"][0.30],
    "market_dispersion_q65": QUANTILES["f_f_market_dispersion_5m"][0.65],
    "quote_volume_24h_q35": QUANTILES["f_context_quote_volume_24h"][0.35],
    "prev3_side_ret_q60": QUANTILES["f_micro_prev3_side_ret"][0.60],
    "side_ret_5m_q60": QUANTILES["f_micro_side_ret_5m"][0.60],
    "extension_60m_q40": QUANTILES["f_new_extension_60m_norm"][0.40],
}


def k1_a1(row):
    if row["A1_LOW_DISPLACEMENT"] != "True":
        return False
    checks = [
        row["_v"]["f_f_market_dispersion_5m"] is not None
        and row["_v"]["f_f_market_dispersion_5m"] >= THRESHOLDS["market_dispersion_q70"],
        row["_v"]["f_new_accel_5_vs_15"] is not None
        and row["_v"]["f_new_accel_5_vs_15"] >= THRESHOLDS["accel_5_vs_15_q70"],
        row["_v"]["f_new_positioning_support"] is not None
        and row["_v"]["f_new_positioning_support"] <= THRESHOLDS["positioning_support_q30"],
    ]
    return sum(checks) >= 2


def k2_a2(row):
    if row["A2_WEAK_RELATIVE_EXPANSION"] != "True":
        return False
    return (
        row["_v"]["f_f_market_dispersion_5m"] is not None
        and row["_v"]["f_context_quote_volume_24h"] is not None
        and row["_v"]["f_f_market_dispersion_5m"] >= THRESHOLDS["market_dispersion_q65"]
        and row["_v"]["f_context_quote_volume_24h"] <= THRESHOLDS["quote_volume_24h_q35"]
    )


def k3_a3(row):
    if row["A3_LOW_ENERGY_RESIDUAL"] != "True":
        return False
    checks = [
        row["_v"]["f_micro_prev3_side_ret"] is not None
        and row["_v"]["f_micro_prev3_side_ret"] >= THRESHOLDS["prev3_side_ret_q60"],
        row["_v"]["f_micro_side_ret_5m"] is not None
        and row["_v"]["f_micro_side_ret_5m"] >= THRESHOLDS["side_ret_5m_q60"],
        row["_v"]["f_new_extension_60m_norm"] is not None
        and row["_v"]["f_new_extension_60m_norm"] <= THRESHOLDS["extension_60m_q40"],
    ]
    return sum(checks) >= 2


BRANCHES = {
    "K1_A1_TURBULENT_UNSUPPORTED": k1_a1,
    "K2_A2_ILLIQUID_DISPERSION": k2_a2,
    "K3_A3_SHORT_BURST_NO_EXTENSION": k3_a3,
}


def metrics(rows, ids):
    rows = list(rows)
    dropped = [r for r in rows if r["position_id"] in ids]
    ex = [r for r in dropped if truth(r["executable"])]
    bad = [r for r in dropped if r["mfe_bucket"] in ("BAD_A_LT_0P30", "BAD_B_0P30_0P50")]
    target = [r for r in dropped if r["mfe_bucket"] == "TARGET_GE_1P00"]
    return {
        "selected": len(dropped),
        "executable": len(ex),
        "bad_a": sum(r["mfe_bucket"] == "BAD_A_LT_0P30" for r in dropped),
        "bad_b": sum(r["mfe_bucket"] == "BAD_B_0P30_0P50" for r in dropped),
        "bad_total": len(bad),
        "gray": sum(r["mfe_bucket"] == "GRAY_0P50_1P00" for r in dropped),
        "target": len(target),
        "strong_selected": sum(truth(r["strong"]) for r in dropped),
        "strong_executable": sum(truth(r["strong"]) for r in ex),
        "wins": sum(float(r["pnl"]) > 0 for r in ex),
        "pnl": sum(float(r["pnl"]) for r in ex),
        "bad_vs_target_precision": (
            len(bad) / (len(bad) + len(target))
            if len(bad) + len(target) else 0.0
        ),
    }


branch_ids = {
    name: {r["position_id"] for r in DETAIL if fn(r)}
    for name, fn in BRANCHES.items()
}
union_ids = set().union(*branch_ids.values())

# Marginal contribution in frozen branch order.
covered = set()
marginal = {}
for name in BRANCHES:
    new_ids = branch_ids[name] - covered
    marginal[name] = metrics(DETAIL, new_ids)
    covered |= branch_ids[name]

# Label PnL decomposition.
label_pnl = {}
for label in (
    "BAD_A_LT_0P30",
    "BAD_B_0P30_0P50",
    "GRAY_0P50_1P00",
    "TARGET_GE_1P00",
):
    rows = [
        r for r in DETAIL
        if r["position_id"] in union_ids
        and r["mfe_bucket"] == label
        and truth(r["executable"])
    ]
    label_pnl[label] = {
        "executable": len(rows),
        "pnl": sum(float(r["pnl"]) for r in rows),
        "wins": sum(float(r["pnl"]) > 0 for r in rows),
    }

strong_rows = [
    r for r in DETAIL
    if r["position_id"] in union_ids
    and truth(r["strong"])
    and truth(r["executable"])
]
strong_pnl = sum(float(r["pnl"]) for r in strong_rows)

# Global baseline denominators.
all_bad = [
    r for r in DETAIL
    if r["mfe_bucket"] in ("BAD_A_LT_0P30", "BAD_B_0P30_0P50")
]
all_target = [r for r in DETAIL if r["mfe_bucket"] == "TARGET_GE_1P00"]
all_strong = [r for r in DETAIL if truth(r["strong"])]
all_strong_exec = [r for r in DETAIL if truth(r["strong"]) and truth(r["executable"])]

union_metrics = metrics(DETAIL, union_ids)
union_metrics["bad_recall_global"] = union_metrics["bad_total"] / len(all_bad)
union_metrics["target_hit_rate_global"] = union_metrics["target"] / len(all_target)
union_metrics["strong_selected_retention"] = (
    1.0 - union_metrics["strong_selected"] / len(all_strong)
)
union_metrics["strong_executable_retention"] = (
    1.0 - union_metrics["strong_executable"] / len(all_strong_exec)
)
union_metrics["strong_pnl_sacrificed"] = strong_pnl
union_metrics["label_pnl"] = label_pnl

# CT4 exact replay impact, and overlap with prior research layers.
ct4_map = {r["position_id"]: r for r in CT4}
ct5b = json.load(open(RESULTS / "ct5b_summary.json"))
ct5_ids = set(
    ct5b["candidates"]["PRIMARY_BLOCK_ALT_PLUS_T23_DELTA_0075"]["drop_ids"]
)
ct6_ids = {
    r["position_id"]
    for r in csv.DictReader(open(RESULTS / "ct6c_veto_trade_detail.csv"))
}
combined_ids = union_ids | ct5_ids | ct6_ids

def exact_drop_pnl(ids, source=None):
    rows = [
        r for pid, r in ct4_map.items()
        if pid in ids
        and truth(r["executable"])
        and (source is None or r["source"] == source)
    ]
    return sum(float(r["pnl"]) for r in rows)

baseline_all = sum(float(r["pnl"]) for r in CT4 if truth(r["executable"]))
baseline_research = sum(
    float(r["pnl"]) for r in CT4
    if truth(r["executable"]) and r["source"] == "research"
)
baseline_fresh = sum(
    float(r["pnl"]) for r in CT4
    if truth(r["executable"]) and r["source"] == "fresh"
)

combined = {
    "ct4_baseline_pnl": baseline_all,
    "ct7c_incremental_drop_pnl": exact_drop_pnl(union_ids),
    "ct7c_only_keep_pnl": baseline_all - exact_drop_pnl(union_ids),
    "ct5b_ct6c_ct7c_union_selected": len(combined_ids),
    "ct5b_ct6c_ct7c_drop_pnl": exact_drop_pnl(combined_ids),
    "ct5b_ct6c_ct7c_keep_pnl": baseline_all - exact_drop_pnl(combined_ids),
    "research_keep_pnl": baseline_research - exact_drop_pnl(combined_ids, "research"),
    "fresh_keep_pnl": baseline_fresh - exact_drop_pnl(combined_ids, "fresh"),
    "overlap_ct7c_ct6c": len(union_ids & ct6_ids),
    "overlap_ct7c_ct5b": len(union_ids & ct5_ids),
    "overlap_ct5b_ct6c": len(ct5_ids & ct6_ids),
    "combined_strong_selected_removed": sum(
        truth(ct4_map[pid]["strong"])
        for pid in combined_ids if pid in ct4_map
    ),
    "combined_strong_executable_removed": sum(
        truth(ct4_map[pid]["strong"]) and truth(ct4_map[pid]["executable"])
        for pid in combined_ids if pid in ct4_map
    ),
}

summary = {
    "stage": "SHORT-CT7C",
    "status": "CONDITIONAL_KILL_CANDIDATE_PASS_RESEARCH_ONLY",
    "contract": {
        "t_features_used": False,
        "lane_used_as_basis": False,
        "archetypes": "CT7B frozen A1/A2/A3",
        "threshold_fit": "Research Discovery TARGET-MFE quantiles only",
        "future_mfe_use": "label/evaluation only",
        "realized_pnl_use": "evaluation only",
        "runtime_change": False,
    },
    "thresholds": THRESHOLDS,
    "branches": {},
    "marginal": marginal,
    "union": union_metrics,
    "by_block": {},
    "by_source": {},
    "by_lane": {},
    "combined_with_ct5b_ct6c": combined,
}

for name in BRANCHES:
    summary["branches"][name] = metrics(DETAIL, branch_ids[name])

for block in BLOCKS:
    summary["by_block"][block] = metrics(
        [r for r in DETAIL if r["block"] == block],
        union_ids,
    )

for source in ("research", "fresh"):
    summary["by_source"][source] = metrics(
        [r for r in DETAIL if r["source"] == source],
        union_ids,
    )

for lane in range(4):
    summary["by_lane"][str(lane)] = metrics(
        [r for r in DETAIL if int(r["lane"]) == lane],
        union_ids,
    )

(RESULTS / "ct7c_summary.json").write_text(json.dumps(summary, indent=2))

# Branch summary.
with open(RESULTS / "ct7c_branch_summary.csv", "w", newline="") as f:
    fields = [
        "branch", "selected", "executable", "bad_a", "bad_b", "bad_total",
        "gray", "target", "strong_selected", "strong_executable",
        "wins", "pnl", "bad_vs_target_precision",
        "marginal_bad", "marginal_target", "marginal_strong", "marginal_pnl",
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for name in BRANCHES:
        z = summary["branches"][name]
        mz = marginal[name]
        w.writerow({
            "branch": name,
            **{k: z[k] for k in fields if k in z},
            "marginal_bad": mz["bad_total"],
            "marginal_target": mz["target"],
            "marginal_strong": mz["strong_selected"],
            "marginal_pnl": mz["pnl"],
        })

# Trade membership.
with open(RESULTS / "ct7c_trade_detail.csv", "w", newline="") as f:
    fields = [
        "position_id", "symbol", "source", "block", "lane",
        "mfe_pct", "mfe_bucket", "strong", "executable", "pnl", "reason",
        *BRANCHES.keys(), "ct7c_kill",
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in DETAIL:
        flags = {name: r["position_id"] in branch_ids[name] for name in BRANCHES}
        if not any(flags.values()):
            continue
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
            "reason": r.get("reason", ""),
            **flags,
            "ct7c_kill": True,
        })

print("THRESHOLDS", THRESHOLDS)
print("BRANCHES")
for name in BRANCHES:
    print(name, summary["branches"][name], "marginal", marginal[name])
print("UNION", union_metrics)
print("BLOCKS")
for b in BLOCKS:
    print(b, summary["by_block"][b])
print("SOURCES", summary["by_source"])
print("COMBINED", combined)