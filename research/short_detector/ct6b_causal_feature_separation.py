from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "short_detector" / "results"

DETAIL = list(csv.DictReader(open(RESULTS / "ct6a_trade_detail.csv")))
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

BASE = [
    "f_new_overheat_pressure",
    "f_new_accel_15_vs_60",
    "f_new_volume_over_range",
    "f_gate_price_drift_pct",
    "f_f_taker_accel_1m",
    "f_new_gate_price_x_flow_gap",
    "f_new_momentum_curvature",
    "f_context_breakdown_down_pct",
    "f_f_oi_accel_x_overheat",
    "f_f_coin_minus_market_30m",
    "f_f_oi_change_30m_pct",
    "f_micro_volume_ratio_last_vs_prev10",
    "f_new_flow_support",
    "f_new_micro_accel_1_vs_3",
    "f_gate_side_ret_1m_pct",
    "f_gate_taker_share_for_selected",
]

TEMP_SUFFIX = [
    "confirm_side_return_pct",
    "confirm_mfe_pct",
    "confirm_mae_pct",
    "confirm_selected_taker_share",
    "confirm_volume",
    "confirm_trades",
    "confirm_last_clv_selected",
    "confirm_last_body_selected",
    "confirm_last_rejection_wick",
    "f_micro_decay_3_vs_prev3",
    "delta_micro_selected_vwap_extension_20",
    "delta_f_coin_minus_market_15m",
]

DERIVED_STEMS = [
    "confirm_mfe_pct",
    "confirm_side_return_pct",
    "confirm_trades",
    "confirm_selected_taker_share",
    "confirm_mae_pct",
]

BUCKETS = [
    "BAD_A_LT_0P30",
    "BAD_B_0P30_0P50",
    "GRAY_0P50_1P00",
    "TARGET_GE_1P00",
]


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


def feature_names(lane):
    out = list(BASE)
    for h in range(1, lane + 1):
        out.extend(f"t{h}_{s}" for s in TEMP_SUFFIX)
    for h in range(2, lane + 1):
        out.extend(f"d{h}_{s}" for s in DERIVED_STEMS)
    return out


def feature_value(z, name):
    if name.startswith("d") and "_confirm_" in name:
        h = int(name[1])
        stem = name[3:]
        a = ff(z.get(f"t{h}_{stem}"))
        b = ff(z.get(f"t{h-1}_{stem}"))
        return None if a is None or b is None else a - b
    return ff(z.get(name))


def auc(vals):
    # vals = [(x, is_bad)], AUC > 0.5 means high feature values associate with BAD.
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
        mid_rank = ((i + 1) + j) / 2.0
        rank_sum += mid_rank * sum(1 for _, y in z[i:j] if y)
        i = j
    n1, n0 = len(pos), len(neg)
    return (rank_sum - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def sep(a):
    return None if a is None else max(a, 1.0 - a)


def same_direction(a, b):
    if a is None or b is None:
        return False
    return (a - 0.5) * (b - 0.5) > 0


def percentile(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * p
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    w = pos - lo
    return s[lo] * (1 - w) + s[hi] * w


records = []
summary = {
    "stage": "SHORT-CT6B",
    "status": "CAUSAL_FEATURE_SEPARATION_COMPLETE",
    "contract": {
        "bad_label": "future max MFE < 0.50% (research label only)",
        "target_label": "future max MFE >= 1.00% (research label only)",
        "gray": "0.50% <= future max MFE < 1.00%; excluded from binary AUC",
        "causality": "T0 uses base features only; T1 adds T1 snapshots; T2 adds T1/T2; T3 adds T1/T2/T3. Observed confirm_mfe_pct is allowed because it is known by that horizon; future max MFE is never used as a feature.",
        "stable_separator_rule": "coverage >=95%, overall separation >=0.58, Research/Fresh same direction, at least 5 chronological blocks with same direction as overall",
    },
    "lanes": {},
}

for lane in range(4):
    lane_rows = [r for r in DETAIL if int(r["lane"]) == lane]
    binary = [
        r for r in lane_rows
        if r["mfe_bucket"] in ("BAD_A_LT_0P30", "BAD_B_0P30_0P50", "TARGET_GE_1P00")
    ]
    lane_out = []
    for feature in feature_names(lane):
        vals = []
        by_bucket = {b: [] for b in BUCKETS}
        for r in lane_rows:
            x = feature_value(raw(r), feature)
            if x is not None:
                by_bucket[r["mfe_bucket"]].append(x)
                if r in binary:
                    vals.append((x, r["mfe_bucket"] != "TARGET_GE_1P00", r))
        base_pairs = [(x, bad) for x, bad, _ in vals]
        a = auc(base_pairs)
        if a is None:
            continue
        coverage = len(vals) / len(binary) if binary else 0.0

        source_auc = {}
        for source in ("research", "fresh"):
            q = [(x, bad) for x, bad, r in vals if r["source"] == source]
            source_auc[source] = auc(q)

        block_auc = {}
        for block in BLOCKS:
            q = [(x, bad) for x, bad, r in vals if r["block"] == block]
            block_auc[block] = auc(q)

        direction = "HIGH_BAD" if a > 0.5 else "LOW_BAD"
        block_valid = [v for v in block_auc.values() if v is not None]
        block_agree = sum(same_direction(a, v) for v in block_valid)
        src_agree = same_direction(a, source_auc["research"]) and same_direction(a, source_auc["fresh"])

        # BAD-A and BAD-B separately versus TARGET.
        def sub_auc(bad_bucket):
            q = []
            for r in lane_rows:
                if r["mfe_bucket"] not in (bad_bucket, "TARGET_GE_1P00"):
                    continue
                x = feature_value(raw(r), feature)
                if x is not None:
                    q.append((x, r["mfe_bucket"] == bad_bucket))
            return auc(q)

        bad_a_auc = sub_auc("BAD_A_LT_0P30")
        bad_b_auc = sub_auc("BAD_B_0P30_0P50")

        row = {
            "lane": lane,
            "feature": feature,
            "direction": direction,
            "coverage": coverage,
            "auc_bad_lt_0p50_vs_target": a,
            "separation": sep(a),
            "auc_bad_a_vs_target": bad_a_auc,
            "auc_bad_b_vs_target": bad_b_auc,
            "research_auc": source_auc["research"],
            "fresh_auc": source_auc["fresh"],
            "research_fresh_direction_agree": src_agree,
            "block_agree": block_agree,
            "block_valid": len(block_valid),
            "stable_separator": (
                coverage >= 0.95
                and sep(a) >= 0.58
                and src_agree
                and block_agree >= 5
            ),
        }
        for block in BLOCKS:
            row[f"auc_{block}"] = block_auc[block]
        for b in BUCKETS:
            xs = by_bucket[b]
            row[f"{b}_n"] = len(xs)
            row[f"{b}_median"] = statistics.median(xs) if xs else None
            row[f"{b}_p25"] = percentile(xs, 0.25)
            row[f"{b}_p75"] = percentile(xs, 0.75)
        records.append(row)
        lane_out.append(row)

    stable = sorted(
        [r for r in lane_out if r["stable_separator"]],
        key=lambda r: (r["separation"], min(sep(r["research_auc"]) or 0, sep(r["fresh_auc"]) or 0)),
        reverse=True,
    )
    all_ranked = sorted(lane_out, key=lambda r: r["separation"], reverse=True)
    summary["lanes"][str(lane)] = {
        "selected": len(lane_rows),
        "bad": sum(r["mfe_bucket"] in ("BAD_A_LT_0P30", "BAD_B_0P30_0P50") for r in lane_rows),
        "bad_a": sum(r["mfe_bucket"] == "BAD_A_LT_0P30" for r in lane_rows),
        "bad_b": sum(r["mfe_bucket"] == "BAD_B_0P30_0P50" for r in lane_rows),
        "gray": sum(r["mfe_bucket"] == "GRAY_0P50_1P00" for r in lane_rows),
        "target": sum(r["mfe_bucket"] == "TARGET_GE_1P00" for r in lane_rows),
        "stable_separator_count": len(stable),
        "top_stable": stable[:12],
        "top_overall": all_ranked[:12],
    }

fields = [
    "lane", "feature", "direction", "coverage",
    "auc_bad_lt_0p50_vs_target", "separation",
    "auc_bad_a_vs_target", "auc_bad_b_vs_target",
    "research_auc", "fresh_auc", "research_fresh_direction_agree",
    "block_agree", "block_valid", "stable_separator",
]
fields += [f"auc_{b}" for b in BLOCKS]
for b in BUCKETS:
    fields += [f"{b}_n", f"{b}_median", f"{b}_p25", f"{b}_p75"]

with open(RESULTS / "ct6b_feature_separation.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(records)

(RESULTS / "ct6b_summary.json").write_text(json.dumps(summary, indent=2))

print("CT6B")
for lane in range(4):
    z = summary["lanes"][str(lane)]
    print("\nLANE", lane, "bad", z["bad"], "target", z["target"], "stable", z["stable_separator_count"])
    for r in z["top_stable"][:8]:
        print(
            r["feature"],
            "dir", r["direction"],
            "sep", round(r["separation"], 3),
            "A/B", round(r["auc_bad_a_vs_target"], 3), round(r["auc_bad_b_vs_target"], 3),
            "R/F", round(r["research_auc"], 3), round(r["fresh_auc"], 3),
            "blocks", f'{r["block_agree"]}/{r["block_valid"]}',
        )