from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from market_radar.persistence import _postgres_connect
from market_radar.profit_protection_v1 import evaluate_pp_decision_v1
from market_radar.profit_protection_v2 import evaluate_pp_decision_v2
from market_radar.profit_discriminator_stage6 import _exit_fill, _fee_rate, _gross

VERSION = "lq3d-open-lane-admission-pp-v1"
DRIFT_MAX = 0.06782
MAX_CONSECUTIVE_BARS = 2.0
GOOD = {"RECOVERED_DRAWDOWN", "CORRECT_RUNNER"}
BAD = {"TRUE_WRONG_DIRECTION", "STALL_NO_EDGE"}
RTF = "RIGHT_THEN_FAILURE"


def f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def admitted(static: dict[str, str]) -> bool:
    bars = f(static.get("f_micro_consecutive_selected_bars"))
    drift = f(static.get("f_gate_side_adjusted_drift_pct"))
    return bool(
        bars is not None
        and bars <= MAX_CONSECUTIVE_BARS
        and drift is not None
        and drift <= DRIFT_MAX
    )


def classification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    c = Counter(str(x["future_outcome_label"]) for x in rows)
    good = c["RECOVERED_DRAWDOWN"] + c["CORRECT_RUNNER"]
    bad = c["TRUE_WRONG_DIRECTION"] + c["STALL_NO_EDGE"]
    rtf = c[RTF]
    return {
        "n": len(rows),
        "good": good,
        "bad": bad,
        "rtf": rtf,
        "historical_wr_pct": round(100.0 * good / len(rows), 2) if rows else None,
        "good_vs_bad_rate_pct": round(100.0 * good / (good + bad), 2)
        if good + bad
        else None,
        "class_mix": dict(c),
    }


def replay(position: dict[str, Any], obs: list[dict[str, Any]], mode: str) -> tuple[float, list[dict[str, Any]]]:
    raw = json.loads(position.get("raw_json") or "{}")
    side = str(position["side"]).upper()
    entry = float(position["entry_price"])
    initial_qty = float(raw.get("initial_quantity") or 0.0)
    entry_fee = float(raw.get("entry_fee_total") or 0.0)
    remaining = initial_qty
    allocated_entry_fee = 0.0
    net = 0.0
    status = "OPEN"
    actions: list[dict[str, Any]] = []

    for o in obs:
        if mode == "V1":
            action, _ = evaluate_pp_decision_v1(
                peak_roi=float(o["mfe_pct"]),
                economic=float(o["current_pnl_pct"]),
                peak=max(0.0, float(o["mfe_pct"])),
                danger_score=int(o.get("danger_score") or 0),
                status=status,
            )
        else:
            result = evaluate_pp_decision_v2(
                mfe_pct=float(o["mfe_pct"]),
                current_pnl_pct=float(o["current_pnl_pct"]),
                previous_pnl_pct=None
                if o.get("previous_pnl_pct") is None
                else float(o["previous_pnl_pct"]),
                elapsed_seconds=None
                if o.get("elapsed_seconds") is None
                else float(o["elapsed_seconds"]),
                danger_score=int(o.get("danger_score") or 0),
                status=status,
            )
            action = str(result["final_action"])

        if action not in {"REDUCE", "CLOSE"} or remaining <= 0:
            continue

        exit_price = _exit_fill(side, float(o["current_price"]))
        qty = remaining * 0.5 if action == "REDUCE" else remaining
        allocated = (
            entry_fee * (qty / initial_qty)
            if action == "REDUCE" and initial_qty > 0
            else max(0.0, entry_fee - allocated_entry_fee)
        )
        fee = qty * exit_price * _fee_rate()
        net += _gross(side, qty, entry, exit_price) - allocated - fee
        allocated_entry_fee += allocated
        remaining -= qty
        actions.append(
            {
                "evaluated_at_ms": int(o["evaluated_at_ms"]),
                "action": action,
                "mfe_pct": float(o["mfe_pct"]),
                "current_pnl_pct": float(o["current_pnl_pct"]),
                "danger_score": int(o.get("danger_score") or 0),
            }
        )
        status = "REDUCED" if action == "REDUCE" else "CLOSED"
        if status == "CLOSED":
            break

    if remaining > 0:
        exit_price = float(position["exit_price"])
        allocated = max(0.0, entry_fee - allocated_entry_fee)
        fee = remaining * exit_price * _fee_rate()
        net += _gross(side, remaining, entry, exit_price) - allocated - fee

    return net, actions


def economics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n": 0}
    out: dict[str, Any] = {"n": len(rows)}
    for key in ("actual", "v1", "v2"):
        vals = [float(x[key]) for x in rows]
        out[key] = {
            "wins": sum(v > 0 for v in vals),
            "wr_pct": round(100.0 * sum(v > 0 for v in vals) / len(vals), 2),
            "net_pnl": round(sum(vals), 2),
        }
    out["class_mix"] = dict(Counter(x["future_outcome_label"] for x in rows))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--lq3c",
        default="research/liquidity_location/results/lq3c_trade_level.csv",
    )
    ap.add_argument(
        "--static",
        default="/opt/core-app/data/wd5h1_thesis_labeled_features.csv",
    )
    ap.add_argument(
        "--output-dir",
        default="research/liquidity_location/results",
    )
    args = ap.parse_args()

    lq3c = load_csv(Path(args.lq3c))
    static_rows = load_csv(Path(args.static))
    static = {x["meta_position_id"]: x for x in static_rows}

    open_lane = [
        x for x in lq3c if str(x.get("lq3c_open_lane") or "").lower() == "true"
    ]
    selected = [x for x in open_lane if admitted(static[x["position_id"]])]

    split = {
        name: classification([x for x in selected if x["chrono_split"] == name])
        for name in ("TRAIN", "VALIDATION", "RESERVE")
    }
    split["ALL"] = classification(selected)

    ids = [str(x["position_id"]) for x in selected]
    meta = {
        str(x["position_id"]): {
            "chrono_split": str(x["chrono_split"]),
            "future_outcome_label": str(x["future_outcome_label"]),
        }
        for x in selected
    }

    replay_rows: list[dict[str, Any]] = []
    with _postgres_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select position_id,symbol,side,status,opened_at_ms,closed_at_ms,
                       entry_price,exit_price,realized_pnl,raw_json
                from positions where position_id=any(%s)
                """,
                (ids,),
            )
            cols = [x[0] for x in cur.description]
            positions = {row[0]: dict(zip(cols, row)) for row in cur.fetchall()}
            for pid, position in positions.items():
                cur.execute(
                    """
                    select evaluated_at_ms,current_price,current_pnl_pct,mfe_pct,
                           previous_pnl_pct,elapsed_seconds,danger_score
                    from pp_decision_v2_observations
                    where position_id=%s and evaluated_at_ms<=%s
                    order by evaluated_at_ms
                    """,
                    (pid, int(position["closed_at_ms"])),
                )
                ocols = [x[0] for x in cur.description]
                obs = [dict(zip(ocols, row)) for row in cur.fetchall()]
                if not obs:
                    continue
                v1, actions_v1 = replay(position, obs, "V1")
                v2, actions_v2 = replay(position, obs, "V2")
                replay_rows.append(
                    {
                        "position_id": pid,
                        "chrono_split": meta[pid]["chrono_split"],
                        "future_outcome_label": meta[pid]["future_outcome_label"],
                        "actual": float(position["realized_pnl"] or 0.0),
                        "v1": v1,
                        "v2": v2,
                        "observation_count": len(obs),
                        "v1_actions": actions_v1,
                        "v2_actions": actions_v2,
                    }
                )

    replay_summary = {
        "coverage": {
            "selected": len(selected),
            "fast_shadow_covered": len(replay_rows),
            "coverage_pct": round(100.0 * len(replay_rows) / len(selected), 2),
        },
        "ALL": economics(replay_rows),
        "TRAIN": economics([x for x in replay_rows if x["chrono_split"] == "TRAIN"]),
        "VALIDATION": economics(
            [x for x in replay_rows if x["chrono_split"] == "VALIDATION"]
        ),
        "RESERVE": economics(
            [x for x in replay_rows if x["chrono_split"] == "RESERVE"]
        ),
        "RTF": economics(
            [x for x in replay_rows if x["future_outcome_label"] == RTF]
        ),
        "CORRECT_RUNNER": economics(
            [
                x
                for x in replay_rows
                if x["future_outcome_label"] == "CORRECT_RUNNER"
            ]
        ),
        "RECOVERED_DRAWDOWN": economics(
            [
                x
                for x in replay_rows
                if x["future_outcome_label"] == "RECOVERED_DRAWDOWN"
            ]
        ),
    }

    target_wins = math.ceil(0.60 * len(selected))
    current_wins = split["ALL"]["good"]
    target_math = {
        "selected_trades": len(selected),
        "historical_wins": current_wins,
        "target_wr_pct": 60.0,
        "wins_needed_for_target": target_wins,
        "additional_net_wins_needed": target_wins - current_wins,
        "available_rtf": split["ALL"]["rtf"],
        "required_rtf_conversion_pct_if_no_winner_harm": round(
            100.0 * (target_wins - current_wins) / split["ALL"]["rtf"], 2
        ),
    }

    summary = {
        "version": VERSION,
        "contract": {
            "base": "LQ3C OPEN_LANE",
            "admission_rule": {
                "f_micro_consecutive_selected_bars_max": MAX_CONSECUTIVE_BARS,
                "f_gate_side_adjusted_drift_pct_max": DRIFT_MAX,
            },
            "pp_v2": (
                "Frozen PP Decision V2: V1 base contract + fast-decay overlay"
            ),
            "pp_replay_source": "pp_decision_v2_observations fast-shadow",
            "production_authority": "NONE",
        },
        "open_lane_rows": len(open_lane),
        "admission": split,
        "pp_replay": replay_summary,
        "target_math": target_math,
        "good_vs_all_entry_result": {
            "best_univariate_auc": 0.5929,
            "stable_2feature_rules_ge60_all_splits": 0,
            "interpretation": (
                "GOOD separates from BAD, but RTF overlaps GOOD at entry; "
                "entry-time isolation of GOOD vs all non-GOOD is weak."
            ),
        },
        "good_vs_rtf_temporal": {
            "best_auc": 0.687,
            "best_feature": "T+3 selected slope5 norm",
            "t2_side_return_auc": 0.675,
            "t3_side_return_auc": 0.673,
            "interpretation": (
                "GOOD and RTF begin to diverge after entry, but separation is "
                "moderate rather than a clean hard classifier."
            ),
        },
        "verdict": {
            "admission": "PASS_PARTIAL_GOOD_VS_BAD_ONLY",
            "good_isolation": "FAIL_GOOD_VS_ALL_AT_ENTRY",
            "pp_v2_target60": "FAIL",
            "next": (
                "Study RTF temporal decay / profit-lock timing directly; current "
                "entry features cannot cleanly remove RTF and current V2 does not "
                "convert enough RTF to reach 60% WR."
            ),
        },
    }

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "lq3d_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    audit = []
    replay_by_id = {x["position_id"]: x for x in replay_rows}
    for row in selected:
        pid = row["position_id"]
        item = {
            "position_id": pid,
            "symbol": row["symbol"],
            "chrono_split": row["chrono_split"],
            "future_outcome_label": row["future_outcome_label"],
            "historical_realized_pnl": row["future_realized_pnl"],
            "historical_mfe_pct": row["future_max_mfe_pct"],
            "admission_selected": True,
            "fast_shadow_covered": pid in replay_by_id,
        }
        if pid in replay_by_id:
            rr = replay_by_id[pid]
            item["v1_replay_pnl"] = rr["v1"]
            item["v2_replay_pnl"] = rr["v2"]
            item["fast_observation_count"] = rr["observation_count"]
            item["v1_action_count"] = len(rr["v1_actions"])
            item["v2_action_count"] = len(rr["v2_actions"])
        audit.append(item)

    keys: list[str] = []
    seen: set[str] = set()
    for row in audit:
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(key)
    with (out / "lq3d_selected_trade_level.csv").open(
        "w", encoding="utf-8", newline=""
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=keys)
        writer.writeheader()
        writer.writerows(audit)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()