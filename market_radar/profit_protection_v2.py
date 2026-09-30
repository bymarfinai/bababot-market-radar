from __future__ import annotations

from typing import Any

from .stage6_validation import POLICIES, _pp_decision_unified


PP_DECISION_V2_VERSION = "pp-decision-v2-stage1-fast-decay"
_ACTION_RANK = {"HOLD": 0, "REDUCE": 1, "CLOSE": 2}

# Stage 1 intentionally overlays the frozen V1 policy instead of retuning it.
V2_FAST_DECAY_POLICY: dict[str, float] = {
    "arm_mfe_pct": 0.50,
    "watch_giveback_ratio": 0.10,
    "watch_decay_ratio_per_min": 0.20,
    "decision_giveback_ratio": 0.20,
    "decision_decay_ratio_per_min": 0.30,
    "force_giveback_ratio": 0.25,
    "force_decay_ratio_per_min": 0.50,
    "shock_min_mfe_pct": 1.00,
    "shock_giveback_ratio": 0.15,
    "shock_drop_pct_points": 0.25,
    "shock_max_seconds": 30.0,
    "reduce_score": 2.0,
    "close_score": 4.0,
}


def _max_action(*actions: str) -> str:
    return max(actions, key=lambda item: _ACTION_RANK.get(str(item).upper(), 0)).upper()


def _decay_metrics(
    *,
    mfe_pct: float,
    current_pnl_pct: float,
    previous_pnl_pct: float | None,
    elapsed_seconds: float | None,
) -> dict[str, float | None]:
    mfe = max(0.0, float(mfe_pct))
    current = float(current_pnl_pct)
    giveback_ratio = max(0.0, (mfe - current) / mfe) if mfe > 0 else 0.0
    if previous_pnl_pct is None or elapsed_seconds is None or float(elapsed_seconds) <= 0:
        return {
            "giveback_ratio": giveback_ratio,
            "drop_pct_points": None,
            "decay_ratio_per_min": None,
            "elapsed_seconds": elapsed_seconds,
        }
    elapsed = float(elapsed_seconds)
    drop = max(0.0, float(previous_pnl_pct) - current)
    decay_ratio_per_min = (
        (drop / mfe) * (60.0 / elapsed)
        if mfe > 0 and drop > 0
        else 0.0
    )
    return {
        "giveback_ratio": giveback_ratio,
        "drop_pct_points": drop,
        "decay_ratio_per_min": decay_ratio_per_min,
        "elapsed_seconds": elapsed,
    }


def evaluate_pp_decision_v2(
    *,
    mfe_pct: float,
    current_pnl_pct: float,
    previous_pnl_pct: float | None,
    elapsed_seconds: float | None,
    danger_score: int,
    status: str = "OPEN",
) -> dict[str, Any]:
    """Evaluate PP-DECISION V2 Stage 1.

    V1 Unified remains the base contract. The fast-decay layer can only escalate
    HOLD -> REDUCE -> CLOSE; it can never relax a V1 decision.
    """
    v1_policy = POLICIES["PP-DECISION-V1-FINAL"]
    base_action, base_meta = _pp_decision_unified(
        v1_policy,
        peak_roi=float(mfe_pct),
        economic=float(current_pnl_pct),
        peak=max(0.0, float(mfe_pct)),
        evidence={"danger_score": int(danger_score)},
        status=str(status).upper(),
    )
    metrics = _decay_metrics(
        mfe_pct=mfe_pct,
        current_pnl_pct=current_pnl_pct,
        previous_pnl_pct=previous_pnl_pct,
        elapsed_seconds=elapsed_seconds,
    )
    result: dict[str, Any] = {
        "version": PP_DECISION_V2_VERSION,
        "base_v1_action": base_action,
        "base_v1_gate": base_meta.get("gate"),
        "base_v1_zone": base_meta.get("zone"),
        "overlay_action": "HOLD",
        "final_action": base_action,
        "fast_gate": "DISARMED",
        "danger_score": int(danger_score),
        **metrics,
    }

    mfe = float(mfe_pct)
    if mfe < V2_FAST_DECAY_POLICY["arm_mfe_pct"]:
        return result
    if metrics["drop_pct_points"] is None or metrics["decay_ratio_per_min"] is None:
        result["fast_gate"] = "COLD_START"
        return result

    giveback = float(metrics["giveback_ratio"] or 0.0)
    drop = float(metrics["drop_pct_points"] or 0.0)
    decay = float(metrics["decay_ratio_per_min"] or 0.0)
    elapsed = float(metrics["elapsed_seconds"] or 0.0)
    status_u = str(status).upper()
    danger = int(danger_score)
    overlay = "HOLD"

    shock = bool(
        mfe >= V2_FAST_DECAY_POLICY["shock_min_mfe_pct"]
        and giveback >= V2_FAST_DECAY_POLICY["shock_giveback_ratio"]
        and drop >= V2_FAST_DECAY_POLICY["shock_drop_pct_points"]
        and elapsed <= V2_FAST_DECAY_POLICY["shock_max_seconds"]
    )
    force = bool(
        giveback >= V2_FAST_DECAY_POLICY["force_giveback_ratio"]
        and decay >= V2_FAST_DECAY_POLICY["force_decay_ratio_per_min"]
    )
    decision = bool(
        giveback >= V2_FAST_DECAY_POLICY["decision_giveback_ratio"]
        and decay >= V2_FAST_DECAY_POLICY["decision_decay_ratio_per_min"]
    )
    watch = bool(
        giveback >= V2_FAST_DECAY_POLICY["watch_giveback_ratio"]
        and decay >= V2_FAST_DECAY_POLICY["watch_decay_ratio_per_min"]
    )

    if force:
        result["fast_gate"] = "FAST_FORCE_PROTECT"
        overlay = "CLOSE" if status_u == "REDUCED" or danger >= int(V2_FAST_DECAY_POLICY["close_score"]) else "REDUCE"
    elif shock:
        result["fast_gate"] = "SHOCK_DECAY"
        overlay = "CLOSE" if status_u == "REDUCED" or danger >= int(V2_FAST_DECAY_POLICY["close_score"]) else "REDUCE"
    elif decision:
        result["fast_gate"] = "FAST_DECISION"
        if danger >= int(V2_FAST_DECAY_POLICY["close_score"]):
            overlay = "CLOSE"
        elif danger >= int(V2_FAST_DECAY_POLICY["reduce_score"]):
            overlay = "CLOSE" if status_u == "REDUCED" else "REDUCE"
    elif watch:
        result["fast_gate"] = "FAST_WATCH"

    result["overlay_action"] = overlay
    result["final_action"] = _max_action(base_action, overlay)
    return result
