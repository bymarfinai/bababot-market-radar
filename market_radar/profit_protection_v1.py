from __future__ import annotations

from typing import Any

PP_DECISION_V1_VERSION = "pp-decision-v1-final-frozen"

PP_DECISION_V1_FINAL_POLICY: dict[str, Any] = {
    "kind": "PP_DECISION_UNIFIED",
    "mode": "DECISION_GATE",
    "sub1_arm_min_roi_pct": 0.50,
    "handoff_roi_pct": 1.00,
    "sub1_watch_giveback_ratio": 0.30,
    "sub1_decision_giveback_ratio": 0.50,
    "sub1_hard_stop_giveback_ratio": 1.00,
    "ge1_watch_giveback_ratio": 0.25,
    "ge1_decision_giveback_ratio": 0.35,
    "ge1_force_reduce_giveback_ratio": 0.50,
    "ge1_hard_close_giveback_ratio": 0.60,
    "watch_reduce_score": 4,
    "reduce_score": 2,
    "close_score": 4,
    "reduce_fraction": 0.50,
}


def _sub1_decision(
    policy: dict[str, Any],
    *,
    peak_roi: float,
    economic: float,
    peak: float,
    danger_score: int,
    status: str,
) -> tuple[str, dict[str, Any]]:
    giveback_ratio = (
        max(0.0, (float(peak) - float(economic)) / float(peak))
        if float(peak) > 0
        else 0.0
    )
    meta: dict[str, Any] = {
        "gate": "DISARMED",
        "giveback_ratio": giveback_ratio,
        "danger_score": int(danger_score),
    }
    if peak_roi < float(policy["arm_min_roi_pct"]):
        return "HOLD", meta
    if peak_roi >= float(policy["handoff_roi_pct"]):
        meta["gate"] = "HANDOFF_GE1"
        return "HOLD", meta

    meta["gate"] = "ARMED_SUB1"
    if giveback_ratio >= float(policy["hard_stop_giveback_ratio"]):
        meta["gate"] = "HARD_STOP"
        return "CLOSE", meta
    if giveback_ratio >= float(policy["decision_giveback_ratio"]):
        meta["gate"] = "MANDATORY_DECISION"
        if danger_score >= int(policy["close_score"]):
            return "CLOSE", meta
        if danger_score >= int(policy["reduce_score"]):
            return ("REDUCE" if status == "OPEN" else "CLOSE"), meta
        return "HOLD", meta
    if giveback_ratio >= float(policy["watch_giveback_ratio"]):
        meta["gate"] = "WATCH"
        if danger_score >= int(policy["watch_reduce_score"]):
            return ("REDUCE" if status == "OPEN" else "CLOSE"), meta
    return "HOLD", meta


def _ge1_decision(
    policy: dict[str, Any],
    *,
    peak_roi: float,
    economic: float,
    peak: float,
    danger_score: int,
    status: str,
) -> tuple[str, dict[str, Any]]:
    giveback_ratio = (
        max(0.0, (float(peak) - float(economic)) / float(peak))
        if float(peak) > 0
        else 0.0
    )
    meta: dict[str, Any] = {
        "gate": "DISARMED",
        "giveback_ratio": giveback_ratio,
        "danger_score": int(danger_score),
    }
    if peak_roi < float(policy["arm_min_roi_pct"]):
        return "HOLD", meta

    meta["gate"] = "ARMED_GE1"
    if giveback_ratio >= float(policy["hard_close_giveback_ratio"]):
        meta["gate"] = "HARD_CLOSE"
        return "CLOSE", meta
    if giveback_ratio >= float(policy["force_reduce_giveback_ratio"]):
        meta["gate"] = "FORCE_PROTECT"
        if danger_score >= int(policy["close_score"]) or status == "REDUCED":
            return "CLOSE", meta
        return "REDUCE", meta
    if giveback_ratio >= float(policy["decision_giveback_ratio"]):
        meta["gate"] = "MANDATORY_DECISION"
        if danger_score >= int(policy["close_score"]):
            return "CLOSE", meta
        if danger_score >= int(policy["reduce_score"]):
            return ("REDUCE" if status == "OPEN" else "CLOSE"), meta
        return "HOLD", meta
    if giveback_ratio >= float(policy["watch_giveback_ratio"]):
        meta["gate"] = "WATCH"
        if danger_score >= int(policy["watch_reduce_score"]):
            return ("REDUCE" if status == "OPEN" else "CLOSE"), meta
    return "HOLD", meta


def evaluate_pp_decision_v1(
    *,
    peak_roi: float,
    economic: float,
    peak: float,
    danger_score: int,
    status: str = "OPEN",
) -> tuple[str, dict[str, Any]]:
    """Frozen PP-DECISION V1 FINAL decision gate used as the V2 base contract."""
    policy = PP_DECISION_V1_FINAL_POLICY
    status_u = str(status).upper()
    handoff = float(policy["handoff_roi_pct"])
    if peak_roi < handoff:
        action, meta = _sub1_decision(
            {
                "arm_min_roi_pct": float(policy["sub1_arm_min_roi_pct"]),
                "handoff_roi_pct": handoff,
                "watch_giveback_ratio": float(policy["sub1_watch_giveback_ratio"]),
                "decision_giveback_ratio": float(policy["sub1_decision_giveback_ratio"]),
                "hard_stop_giveback_ratio": float(policy["sub1_hard_stop_giveback_ratio"]),
                "watch_reduce_score": int(policy["watch_reduce_score"]),
                "reduce_score": int(policy["reduce_score"]),
                "close_score": int(policy["close_score"]),
            },
            peak_roi=peak_roi,
            economic=economic,
            peak=peak,
            danger_score=int(danger_score),
            status=status_u,
        )
        meta["zone"] = "SUB1"
        return action, meta

    action, meta = _ge1_decision(
        {
            "arm_min_roi_pct": handoff,
            "watch_giveback_ratio": float(policy["ge1_watch_giveback_ratio"]),
            "decision_giveback_ratio": float(policy["ge1_decision_giveback_ratio"]),
            "force_reduce_giveback_ratio": float(policy["ge1_force_reduce_giveback_ratio"]),
            "hard_close_giveback_ratio": float(policy["ge1_hard_close_giveback_ratio"]),
            "watch_reduce_score": int(policy["watch_reduce_score"]),
            "reduce_score": int(policy["reduce_score"]),
            "close_score": int(policy["close_score"]),
        },
        peak_roi=peak_roi,
        economic=economic,
        peak=peak,
        danger_score=int(danger_score),
        status=status_u,
    )
    meta["zone"] = "GE1"
    return action, meta
