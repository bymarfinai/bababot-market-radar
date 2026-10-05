from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "short_detector" / "results"

DETAIL = list(csv.DictReader(open(RESULTS / "ct6a_trade_detail.csv")))
RESEARCH_ROWS = list(csv.DictReader(open("/opt/core-app/data/wd5h1_thesis_labeled_features.csv")))
FRESH_ROWS = list(csv.DictReader(open("/tmp/s10h_fresh_features.csv")))
RESEARCH = {r["meta_position_id"]: r for r in RESEARCH_ROWS}
FRESH = {r["meta_position_id"]: r for r in FRESH_ROWS}

BLOCKS = [
    "Research_Discovery",
    "Research_Validation",
    "Research_Reserve",
    "Fresh_2026-10-01",
    "Fresh_2026-10-02",
    "Fresh_2026-10-03",
]

LABEL_BAD = {"BAD_A_LT_0P30", "BAD_B_0P30_0P50"}
LABEL_TARGET = "TARGET_GE_1P00"

# Global low-MFE detector must not depend on T1/T2/T3.
EXCLUDE_EXACT = {
    "meta_position_id",
    "meta_signal_id",
    "meta_symbol",
    "meta_opened_at_ms",
    "f_decision_hour_utc",  # retained separately as contextual anatomy, not primary morphology
    "f_decision_weekday_utc",
    "f_side_is_long",       # SHORT universe, effectively constant
}
EXCLUDE_PREFIX = ("t1_", "t2_", "t3_")

# Known selection/runtime metadata that are causal but not useful as market morphology.
# We keep scores/context counters in the broad matrix but identify them as "selection_state"
# so later stages can choose whether to use them.
SELECTION_PREFIXES = (
    "f_long_score", "f_short_score", "f_selected_score", "f_opposite_score",
    "f_score_edge", "f_decision_context_", "f_evidence_count",
    "f_score_component_", "f_stage",
)

def ff(v):
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    sl = s.lower()
    if sl in ("true", "false"):
        return 1.0 if sl == "true" else 0.0
    try:
        x = float(s)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def raw(row):
    return RESEARCH[row["position_id"]] if row["source"] == "research" else FRESH[row["position_id"]]


def percentile(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * p
    lo = int(math.floor(pos))
    hi = min(len(s) - 1, lo + 1)
    w = pos - lo
    return s[lo] * (1 - w) + s[hi] * w


def auc(vals):
    # vals = [(value, is_bad)], AUC > .5 => high values associate with BAD.
    pos = [x for x, y in vals if y]
    neg = [x for x, y in vals if not y]
    if not pos or not neg:
        return None
    z = sorted(vals, key=lambda x: x[0])
    rank_sum = 0.0
    i = 0
    while i < len(z):
        j = i + 1
        while j < len(z) and z[j][0] == z[i][0]:
            j += 1
        rank = ((i + 1) + j) / 2.0
        rank_sum += rank * sum(1 for _, y in z[i:j] if y)
        i = j
    n1, n0 = len(pos), len(neg)
    return (rank_sum - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def sep(a):
    return None if a is None else max(a, 1.0 - a)


def same_dir(a, b):
    if a is None or b is None or a == 0.5 or b == 0.5:
        return False
    return (a - 0.5) * (b - 0.5) > 0


def feature_family(name):
    if any(name.startswith(p) for p in SELECTION_PREFIXES):
        return "selection_state"
    if name.startswith("f_f_coin_") or name.startswith("f_f_market_") or name.startswith("f_f_btc_") or name.startswith("f_f_eth_") or name.startswith("f_f_relative_"):
        return "market_relative"
    if name.startswith("f_f_oi_") or "oi_" in name or "positioning" in name:
        return "oi_positioning"
    if name.startswith("f_f_taker_") or "taker" in name or "flow" in name:
        return "flow_taker"
    if name.startswith("f_micro_"):
        return "microstructure"
    if name.startswith("f_new_"):
        if any(k in name for k in ("accel", "momentum", "extension", "continuation")):
            return "momentum_extension"
        if any(k in name for k in ("activity", "volume", "trades", "range", "heat")):
            return "activity_heat"
        return "derived_interaction"
    if name.startswith("f_gate_"):
        return "gate_snapshot"
    if name.startswith("f_context_"):
        return "context"
    if name.startswith("f_ret_") or "return_" in name or name.startswith("f_range_") or name.startswith("f_trades_") or name.startswith("f_volume_"):
        return "signal_kinematics"
    if name.startswith("f_latency_"):
        return "latency"
    return "other"


# Common non-temporal columns only.
h1 = list(RESEARCH_ROWS[0].keys())
h2 = set(FRESH_ROWS[0].keys())
CANDIDATES = [
    c for c in h1
    if c in h2
    and c not in EXCLUDE_EXACT
    and not c.startswith(EXCLUDE_PREFIX)
    and not c.startswith("meta_")
]

binary_rows = [
    r for r in DETAIL
    if r["mfe_bucket"] in LABEL_BAD or r["mfe_bucket"] == LABEL_TARGET
]
bad_rows = [r for r in binary_rows if r["mfe_bucket"] in LABEL_BAD]
target_rows = [r for r in binary_rows if r["mfe_bucket"] == LABEL_TARGET]

records = []

for feature in CANDIDATES:
    vals = []
    for r in binary_rows:
        x = ff(raw(r).get(feature))
        if x is not None:
            vals.append((x, r["mfe_bucket"] in LABEL_BAD, r))
    if len(vals) < 0.90 * len(binary_rows):
        continue

    a = auc([(x, y) for x, y, _ in vals])
    if a is None:
        continue

    bad_x = [x for x, y, _ in vals if y]
    tar_x = [x for x, y, _ in vals if not y]

    src_auc = {}
    for src in ("research", "fresh"):
        q = [(x, y) for x, y, r in vals if r["source"] == src]
        src_auc[src] = auc(q)

    block_auc = {}
    for b in BLOCKS:
        q = [(x, y) for x, y, r in vals if r["block"] == b]
        block_auc[b] = auc(q)

    lane_auc = {}
    for lane in range(4):
        q = [(x, y) for x, y, r in vals if int(r["lane"]) == lane]
        lane_auc[str(lane)] = auc(q)

    block_valid = [x for x in block_auc.values() if x is not None]
    lane_valid = [x for x in lane_auc.values() if x is not None]
    block_agree = sum(same_dir(a, x) for x in block_valid)
    lane_agree = sum(same_dir(a, x) for x in lane_valid)
    src_agree = same_dir(a, src_auc["research"]) and same_dir(a, src_auc["fresh"])

    rec = {
        "feature": feature,
        "family": feature_family(feature),
        "coverage": len(vals) / len(binary_rows),
        "auc_bad_vs_target": a,
        "separation": sep(a),
        "direction": "HIGH_BAD" if a > 0.5 else "LOW_BAD",
        "bad_n": len(bad_x),
        "target_n": len(tar_x),
        "bad_median": statistics.median(bad_x),
        "bad_p25": percentile(bad_x, 0.25),
        "bad_p75": percentile(bad_x, 0.75),
        "target_median": statistics.median(tar_x),
        "target_p25": percentile(tar_x, 0.25),
        "target_p75": percentile(tar_x, 0.75),
        "research_auc": src_auc["research"],
        "fresh_auc": src_auc["fresh"],
        "source_direction_agree": src_agree,
        "block_agree": block_agree,
        "block_valid": len(block_valid),
        "lane_agree": lane_agree,
        "lane_valid": len(lane_valid),
    }
    for b in BLOCKS:
        rec["auc_" + b] = block_auc[b]
    for lane in range(4):
        rec["auc_lane_" + str(lane)] = lane_auc[str(lane)]

    # A strict "global morphology" separator should transport by source,
    # chronology, and lane even though lane is not part of the model basis.
    rec["global_stable"] = (
        rec["coverage"] >= 0.95
        and rec["separation"] >= 0.58
        and src_agree
        and block_agree >= 5
        and lane_agree >= 3
    )
    records.append(rec)

ranked = sorted(records, key=lambda r: (r["separation"], r["block_agree"], r["lane_agree"]), reverse=True)
stable = [r for r in ranked if r["global_stable"]]

family_summary = {}
for fam in sorted(set(r["family"] for r in records)):
    rr = [r for r in records if r["family"] == fam]
    ss = [r for r in rr if r["global_stable"]]
    family_summary[fam] = {
        "numeric_features": len(rr),
        "stable_features": len(ss),
        "best_separation": max((r["separation"] for r in rr), default=None),
        "top_features": [
            {
                "feature": r["feature"],
                "direction": r["direction"],
                "separation": r["separation"],
                "research_auc": r["research_auc"],
                "fresh_auc": r["fresh_auc"],
                "block_agree": r["block_agree"],
                "lane_agree": r["lane_agree"],
            }
            for r in sorted(rr, key=lambda x: x["separation"], reverse=True)[:5]
        ],
    }

# Severity anatomy across BAD-A/B/GRAY/TARGET for the top stable variables.
severity = []
for rec in stable[:30]:
    feature = rec["feature"]
    row = {
        "feature": feature,
        "family": rec["family"],
        "direction": rec["direction"],
        "separation": rec["separation"],
    }
    for bucket in (
        "BAD_A_LT_0P30",
        "BAD_B_0P30_0P50",
        "GRAY_0P50_1P00",
        "TARGET_GE_1P00",
    ):
        xs = [
            ff(raw(r).get(feature))
            for r in DETAIL
            if r["mfe_bucket"] == bucket and ff(raw(r).get(feature)) is not None
        ]
        row[bucket + "_n"] = len(xs)
        row[bucket + "_median"] = statistics.median(xs) if xs else None
        row[bucket + "_p25"] = percentile(xs, 0.25)
        row[bucket + "_p75"] = percentile(xs, 0.75)
    severity.append(row)

# Contextual anatomy: not detector basis, but useful sanity.
context = {
    "total_selected": len(DETAIL),
    "bad_lt_0p50": len([r for r in DETAIL if r["mfe_bucket"] in LABEL_BAD]),
    "gray_0p50_1p00": len([r for r in DETAIL if r["mfe_bucket"] == "GRAY_0P50_1P00"]),
    "target_ge_1p00": len([r for r in DETAIL if r["mfe_bucket"] == LABEL_TARGET]),
    "bad_by_lane": {
        str(lane): len([r for r in DETAIL if int(r["lane"]) == lane and r["mfe_bucket"] in LABEL_BAD])
        for lane in range(4)
    },
    "target_by_lane": {
        str(lane): len([r for r in DETAIL if int(r["lane"]) == lane and r["mfe_bucket"] == LABEL_TARGET])
        for lane in range(4)
    },
    "bad_by_block": {
        b: len([r for r in DETAIL if r["block"] == b and r["mfe_bucket"] in LABEL_BAD])
        for b in BLOCKS
    },
    "target_by_block": {
        b: len([r for r in DETAIL if r["block"] == b and r["mfe_bucket"] == LABEL_TARGET])
        for b in BLOCKS
    },
}

summary = {
    "stage": "SHORT-CT7A",
    "status": "GLOBAL_LOW_MFE_ANATOMY_COMPLETE",
    "contract": {
        "primary_basis": "global BAD MFE<0.50 vs TARGET MFE>=1.00",
        "temporal_t_features_used": False,
        "lane_used_as_model_basis": False,
        "lane_use": "secondary transport/sanity check only",
        "gray_use": "excluded from primary binary separation; retained for severity anatomy",
        "future_mfe_use": "label only",
        "feature_space": "common Research/Fresh non-temporal causal snapshot features",
    },
    "population": context,
    "feature_counts": {
        "common_non_temporal_candidates": len(CANDIDATES),
        "numeric_high_coverage_features": len(records),
        "global_stable_features": len(stable),
    },
    "top_global_features": stable[:30],
    "family_summary": family_summary,
}

(RESULTS / "ct7a_summary.json").write_text(json.dumps(summary, indent=2))

fieldnames = [
    "feature", "family", "coverage", "auc_bad_vs_target", "separation", "direction",
    "bad_n", "target_n", "bad_median", "bad_p25", "bad_p75",
    "target_median", "target_p25", "target_p75",
    "research_auc", "fresh_auc", "source_direction_agree",
    "block_agree", "block_valid", "lane_agree", "lane_valid", "global_stable",
]
fieldnames += ["auc_" + b for b in BLOCKS]
fieldnames += ["auc_lane_" + str(i) for i in range(4)]
with open(RESULTS / "ct7a_global_feature_anatomy.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(records)

sev_fields = ["feature", "family", "direction", "separation"]
for bucket in (
    "BAD_A_LT_0P30",
    "BAD_B_0P30_0P50",
    "GRAY_0P50_1P00",
    "TARGET_GE_1P00",
):
    sev_fields += [
        bucket + "_n", bucket + "_median",
        bucket + "_p25", bucket + "_p75",
    ]
with open(RESULTS / "ct7a_severity_anatomy.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=sev_fields)
    w.writeheader()
    w.writerows(severity)

print("population", context)
print("features candidates", len(CANDIDATES), "numeric/high coverage", len(records), "global stable", len(stable))
print("\nTOP GLOBAL STABLE")
for r in stable[:25]:
    print(
        r["feature"], r["family"], r["direction"],
        "sep", round(r["separation"], 4),
        "R/F", None if r["research_auc"] is None else round(r["research_auc"], 4),
        None if r["fresh_auc"] is None else round(r["fresh_auc"], 4),
        "blocks", f'{r["block_agree"]}/{r["block_valid"]}',
        "lanes", f'{r["lane_agree"]}/{r["lane_valid"]}',
        "med", round(r["bad_median"], 5), round(r["target_median"], 5),
    )
print("\nFAMILIES")
for fam, z in sorted(family_summary.items(), key=lambda kv: (kv[1]["stable_features"], kv[1]["best_separation"] or 0), reverse=True):
    print(fam, z["numeric_features"], z["stable_features"], "best", z["best_separation"])