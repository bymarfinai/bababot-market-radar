from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from pathlib import Path

import numpy as np


EXCLUDED = {
    "f_decision_hour_utc",
    "f_decision_hour_sin",
    "f_decision_hour_cos",
    "f_decision_weekday_utc",
    "f_latency_ai_queue_s",
    "f_latency_ai_execution_s",
    "f_latency_stage11c_s",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_float(value: str | None) -> float:
    if value in ("", None, "nan", "NaN", "None", "null"):
        return np.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def phi_from_counts(tp, selected, targets, n):
    fp = selected - tp
    fn = targets - tp
    tn = n - selected - fn
    den = np.sqrt(selected * targets * (n - targets) * (n - selected))
    return np.where(den > 0, (tp * tn - fp * fn) / den, 0.0)


def metrics(mask: np.ndarray, idx: np.ndarray, y: np.ndarray, pnl: np.ndarray, ret: np.ndarray) -> dict:
    b = mask[idx]
    yy = y[idx]
    n = len(idx)
    selected = int(b.sum())
    targets = int(yy.sum())
    tp = int((b & (yy == 1)).sum())
    fp = selected - tp
    fn = targets - tp
    tn = n - selected - fn
    den = math.sqrt(selected * targets * (n - targets) * (n - selected)) if 0 < selected < n else 0.0
    phi = ((tp * tn - fp * fn) / den) if den else 0.0
    return {
        "n": n,
        "targets": targets,
        "selected": selected,
        "captured": tp,
        "false_pos": fp,
        "recall": tp / targets if targets else 0.0,
        "precision": tp / selected if selected else 0.0,
        "selection_rate": selected / n if n else 0.0,
        "phi": phi,
        "pnl": float(pnl[idx][b].sum()) if selected else 0.0,
        "avg_return": float(ret[idx][b].mean()) if selected else 0.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--long-win", required=True, type=Path)
    ap.add_argument("--long-loss", required=True, type=Path)
    ap.add_argument("--stage3b-predictions", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    raw = read_csv(args.long_win) + read_csv(args.long_loss)
    pred = read_csv(args.stage3b_predictions)
    raw_map = {r["meta_position_id"]: r for r in raw}

    rows = []
    for p in pred:
        rr = raw_map[p["meta_position_id"]]
        rows.append({
            "raw": rr,
            "split": p["split"],
            "target": int(p["stage3b_target"]),
            "pnl": float(p["historical_realized_pnl"]),
            "ret": float(p["historical_realized_pnl_pct"]),
        })

    headers = list(raw[0])
    feature_cols = [c for c in headers if c.startswith("f_") and c not in EXCLUDED]
    assert len(feature_cols) == 224, len(feature_cols)

    numeric, categorical = [], []
    for c in feature_cols:
        vals = [r["raw"][c] for r in rows if r["raw"][c] not in ("", None)]
        good = 0
        for v in vals:
            try:
                float(v)
                good += 1
            except ValueError:
                pass
        (numeric if vals and good / len(vals) >= 0.999 else categorical).append(c)

    y = np.array([r["target"] for r in rows], dtype=int)
    pnl = np.array([r["pnl"] for r in rows], dtype=float)
    ret = np.array([r["ret"] for r in rows], dtype=float)
    split_idx = {
        s: np.array([i for i, r in enumerate(rows) if r["split"] == s], dtype=int)
        for s in ("Discovery", "Validation", "Reserve")
    }
    didx, vidx = split_idx["Discovery"], split_idx["Validation"]
    yd, yv = y[didx], y[vidx]
    nd, nv = len(didx), len(vidx)
    td, tv = int(yd.sum()), int(yv.sum())

    Xnum = {
        c: np.array([to_float(r["raw"][c]) for r in rows], dtype=float)
        for c in numeric
    }

    tuned = []
    candidate_count = 0

    for c in numeric:
        xd, xv = Xnum[c][didx], Xnum[c][vidx]
        md, mv = np.isfinite(xd), np.isfinite(xv)
        ad, av = xd[md], xv[mv]
        byd, byv = yd[md], yv[mv]
        if len(ad) < 10 or np.nanstd(ad) == 0:
            continue

        od = np.argsort(ad, kind="mergesort")
        sd, syd = ad[od], byd[od]
        pd = np.cumsum(syd)
        ov = np.argsort(av, kind="mergesort")
        sv, syv = av[ov], byv[ov]
        pv = np.cumsum(syv)

        ends = np.flatnonzero(np.r_[sd[1:] != sd[:-1], True])
        starts = np.r_[0, ends[:-1] + 1]
        vals = sd[starts]
        end_vals = sd[ends]
        end_tp = pd[ends]
        before_tp = np.where(starts > 0, pd[starts - 1], 0)
        total_tp = int(syd.sum())

        best = {"score": -999.0}

        def consider(rule_type, low, high, dsel, dtp, dphi, vsel, vtp, vphi):
            nonlocal best
            ok = dsel >= 5 and dsel <= nd - 5 and vsel >= 5 and vsel <= nv - 5
            if not ok:
                return
            score = min(float(dphi), float(vphi))
            if score > best["score"]:
                best = {
                    "feature": c,
                    "rule_type": rule_type,
                    "low": low,
                    "high": high,
                    "score": score,
                    "discovery_phi": float(dphi),
                    "validation_phi": float(vphi),
                }

        # <=
        dsel = ends + 1
        dtp = end_tp
        dphi = phi_from_counts(dtp, dsel, td, nd)
        rv = np.searchsorted(sv, end_vals, side="right") - 1
        vsel = rv + 1
        vtp = np.where(rv >= 0, pv[np.maximum(rv, 0)], 0)
        vphi = np.zeros(len(rv))
        ok = (vsel >= 5) & (vsel <= nv - 5) & (dsel >= 5) & (dsel <= nd - 5)
        vphi[ok] = phi_from_counts(vtp[ok], vsel[ok], tv, nv)
        candidate_count += len(end_vals)
        for k in np.flatnonzero(ok):
            consider("<=", None, float(end_vals[k]), int(dsel[k]), int(dtp[k]), dphi[k], int(vsel[k]), int(vtp[k]), vphi[k])

        # >=
        dsel = len(sd) - starts
        dtp = total_tp - before_tp
        dphi = phi_from_counts(dtp, dsel, td, nd)
        lv = np.searchsorted(sv, vals, side="left")
        vsel = len(sv) - lv
        vbefore = np.where(lv > 0, pv[np.maximum(lv - 1, 0)], 0)
        vtp = int(syv.sum()) - vbefore
        vphi = np.zeros(len(vals))
        ok = (vsel >= 5) & (vsel <= nv - 5) & (dsel >= 5) & (dsel <= nd - 5)
        vphi[ok] = phi_from_counts(vtp[ok], vsel[ok], tv, nv)
        candidate_count += len(vals)
        for k in np.flatnonzero(ok):
            consider(">=", float(vals[k]), None, int(dsel[k]), int(dtp[k]), dphi[k], int(vsel[k]), int(vtp[k]), vphi[k])

        # exact contiguous bands
        for i in range(len(starts)):
            low = float(vals[i])
            rr = ends[i:]
            dsel = rr - starts[i] + 1
            dtp = end_tp[i:] - before_tp[i]
            dphi = phi_from_counts(dtp, dsel, td, nd)

            highs = end_vals[i:]
            lv0 = np.searchsorted(sv, low, side="left")
            rv = np.searchsorted(sv, highs, side="right") - 1
            vsel = np.maximum(0, rv - lv0 + 1)
            vbefore = pv[lv0 - 1] if lv0 > 0 else 0
            vtp = np.where(vsel > 0, pv[np.maximum(rv, 0)] - vbefore, 0)
            vphi = np.zeros(len(highs))
            ok = (vsel >= 5) & (vsel <= nv - 5) & (dsel >= 5) & (dsel <= nd - 5)
            vphi[ok] = phi_from_counts(vtp[ok], vsel[ok], tv, nv)
            candidate_count += len(highs)

            score = np.where(ok, np.minimum(dphi, vphi), -999)
            k = int(np.argmax(score))
            if score[k] > best["score"]:
                best = {
                    "feature": c,
                    "rule_type": "band",
                    "low": low,
                    "high": float(highs[k]),
                    "score": float(score[k]),
                    "discovery_phi": float(dphi[k]),
                    "validation_phi": float(vphi[k]),
                }

        xx = Xnum[c]
        if best["rule_type"] == "<=":
            mask = np.isfinite(xx) & (xx <= best["high"])
        elif best["rule_type"] == ">=":
            mask = np.isfinite(xx) & (xx >= best["low"])
        else:
            mask = np.isfinite(xx) & (xx >= best["low"]) & (xx <= best["high"])

        for s, idx in split_idx.items():
            best[s.lower()] = metrics(mask, idx, y, pnl, ret)
        best["full"] = metrics(mask, np.arange(len(rows)), y, pnl, ret)
        tuned.append(best)

    # categorical rules
    for c in categorical:
        arr = np.array([r["raw"][c] for r in rows], dtype=object)
        vals = sorted(set(arr[didx]))
        subsets = (
            [comb for k in range(1, len(vals)) for comb in itertools.combinations(vals, k)]
            if 1 < len(vals) <= 8
            else [(v,) for v in vals]
        )
        best = {"score": -999.0}
        for comb in subsets:
            candidate_count += 1
            mask = np.isin(arr, comb)
            dm = metrics(mask, didx, y, pnl, ret)
            vm = metrics(mask, vidx, y, pnl, ret)
            if not (5 <= dm["selected"] <= nd - 5 and 5 <= vm["selected"] <= nv - 5):
                continue
            score = min(dm["phi"], vm["phi"])
            if score > best["score"]:
                best = {"feature": c, "rule_type": "in", "values": comb, "score": score}
        mask = np.isin(arr, best.get("values", ()))
        for s, idx in split_idx.items():
            best[s.lower()] = metrics(mask, idx, y, pnl, ret)
        best["full"] = metrics(mask, np.arange(len(rows)), y, pnl, ret)
        tuned.append(best)

    payload = {
        "stage": "D4 Stage 3C.1 — Exhaustive Single-Parameter Tuning",
        "target": "META_WIN AND historical_max_mfe_pct >= 1.00%",
        "candidate_rules": candidate_count,
        "feature_count": len(feature_cols),
        "numeric_features": len(numeric),
        "categorical_features": len(categorical),
        "strong_abs_phi_threshold": 0.50,
        "strong_rules_found": sum(
            1 for r in tuned
            if r["discovery"]["phi"] >= 0.50
            and r["validation"]["phi"] >= 0.50
            and r["reserve"]["phi"] >= 0.50
        ),
        "rules": tuned,
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
