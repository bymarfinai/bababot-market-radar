from __future__ import annotations

from dataclasses import dataclass, replace

from .models import MarketContext, MovementDetection


DECISION_VERSION = "stage6-v2-directional-context"


@dataclass(frozen=True)
class DecisionConfig:
    """Stage 6 deterministic decision gates.

    Stage 4 score/edge gates remain unchanged. Stage 5 context is split into:
    - activity evidence: confirms that movement is active, but has no direction;
    - directional evidence: supports LONG or SHORT;
    - core directional evidence: structure, taker flow, or fresh OI.

    Activity evidence can never qualify a trade by itself. Regime can reinforce
    a direction, but at least one core directional confirmation is required.
    """

    min_score: float = 68.0
    min_edge: float = 10.0
    ignition_min_confirmations: int = 2
    expansion_min_confirmations: int = 1
    min_core_directional_confirmations: int = 1
    min_context_balance: int = 1


def _required_context_complete(ctx: MarketContext | None) -> bool:
    if ctx is None:
        return False
    return (
        ctx.raw_oi_change_pct is not None
        and ctx.oi_interpretation is not None
        and ctx.funding_rate is not None
        and ctx.market_regime in {"BULL", "BEAR", "SIDEWAYS"}
    )


def _context_votes(
    side: str,
    ctx: MarketContext,
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    """Return directional, core-directional, conflicts, activity, and neutral.

    Funding remains observational. Volume expansion is activity evidence only:
    it proves that something is moving, not that LONG or SHORT is correct.
    Market regime is directional context but cannot be the sole entry proof.
    """

    directional: list[str] = []
    core_directional: list[str] = []
    conflicts: list[str] = []
    activity: list[str] = []
    neutral: list[str] = []

    if ctx.volume_confirmed:
        activity.append("volume_expansion")
    else:
        neutral.append("volume_not_expanded")

    if side == "LONG":
        if ctx.structure_status == "BREAKOUT":
            directional.append("confirmed_breakout")
            core_directional.append("confirmed_breakout")
        elif ctx.structure_status == "FAILED_BREAKDOWN":
            directional.append("failed_breakdown_reclaim")
            core_directional.append("failed_breakdown_reclaim")
        elif ctx.structure_status == "BREAKDOWN":
            conflicts.append("confirmed_breakdown")
        elif ctx.structure_status == "FAILED_BREAKOUT":
            conflicts.append("failed_breakout")
        else:
            neutral.append(f"structure_{ctx.structure_status.lower()}")

        if ctx.taker_bias == "BUY":
            directional.append("taker_buy")
            core_directional.append("taker_buy")
        elif ctx.taker_bias == "SELL":
            conflicts.append("taker_sell")
        else:
            neutral.append("taker_balanced")

        if ctx.oi_interpretation == "FRESH_LONG_PARTICIPATION":
            directional.append("oi_fresh_long")
            core_directional.append("oi_fresh_long")
        elif ctx.oi_interpretation == "SHORT_COVERING":
            neutral.append("oi_short_covering")
        elif ctx.oi_interpretation == "FRESH_SHORT_PARTICIPATION":
            conflicts.append("oi_fresh_short")
        elif ctx.oi_interpretation == "LONG_LIQUIDATION":
            conflicts.append("oi_long_liquidation")
        else:
            neutral.append("oi_unresolved")

        if ctx.market_regime == "BULL":
            directional.append("regime_bull")
        elif ctx.market_regime == "BEAR":
            conflicts.append("regime_bear")
        else:
            neutral.append("regime_sideways")

    elif side == "SHORT":
        if ctx.structure_status == "BREAKDOWN":
            directional.append("confirmed_breakdown")
            core_directional.append("confirmed_breakdown")
        elif ctx.structure_status == "FAILED_BREAKOUT":
            directional.append("failed_breakout_reject")
            core_directional.append("failed_breakout_reject")
        elif ctx.structure_status == "BREAKOUT":
            conflicts.append("confirmed_breakout")
        elif ctx.structure_status == "FAILED_BREAKDOWN":
            conflicts.append("failed_breakdown")
        else:
            neutral.append(f"structure_{ctx.structure_status.lower()}")

        if ctx.taker_bias == "SELL":
            directional.append("taker_sell")
            core_directional.append("taker_sell")
        elif ctx.taker_bias == "BUY":
            conflicts.append("taker_buy")
        else:
            neutral.append("taker_balanced")

        if ctx.oi_interpretation == "FRESH_SHORT_PARTICIPATION":
            directional.append("oi_fresh_short")
            core_directional.append("oi_fresh_short")
        elif ctx.oi_interpretation == "LONG_LIQUIDATION":
            neutral.append("oi_long_liquidation")
        elif ctx.oi_interpretation == "FRESH_LONG_PARTICIPATION":
            conflicts.append("oi_fresh_long")
        elif ctx.oi_interpretation == "SHORT_COVERING":
            conflicts.append("oi_short_covering")
        else:
            neutral.append("oi_unresolved")

        if ctx.market_regime == "BEAR":
            directional.append("regime_bear")
        elif ctx.market_regime == "BULL":
            conflicts.append("regime_bull")
        else:
            neutral.append("regime_sideways")

    else:
        raise ValueError(f"invalid side: {side}")

    if ctx.funding_rate is not None:
        neutral.append(f"funding={ctx.funding_rate:+.8f}")

    return directional, core_directional, conflicts, activity, neutral


def decide(
    movement: MovementDetection,
    config: DecisionConfig | None = None,
) -> MovementDetection:
    """Produce final LONG / SHORT / NO TRADE for one moving candidate."""
    cfg = config or DecisionConfig()
    reasons: list[str] = []

    if not movement.is_moving:
        return replace(
            movement,
            decision="NO TRADE",
            decision_side_candidate=None,
            decision_context_confirmations=0,
            decision_context_conflicts=0,
            decision_context_balance=0,
            decision_reasons=("not_moving",),
            decision_version=DECISION_VERSION,
        )

    if movement.stage not in {"IGNITION", "EXPANSION", "EXHAUSTION"}:
        return replace(
            movement,
            decision="NO TRADE",
            decision_side_candidate=None,
            decision_context_confirmations=0,
            decision_context_conflicts=0,
            decision_context_balance=0,
            decision_reasons=("invalid_or_missing_stage",),
            decision_version=DECISION_VERSION,
        )

    if movement.stage == "EXHAUSTION":
        return replace(
            movement,
            decision="NO TRADE",
            decision_side_candidate=None,
            decision_context_confirmations=0,
            decision_context_conflicts=0,
            decision_context_balance=0,
            decision_reasons=("exhaustion_chase_risk",),
            decision_version=DECISION_VERSION,
        )

    long_score = movement.long_score
    short_score = movement.short_score
    if long_score is None or short_score is None:
        return replace(
            movement,
            decision="NO TRADE",
            decision_side_candidate=None,
            decision_context_confirmations=0,
            decision_context_conflicts=0,
            decision_context_balance=0,
            decision_reasons=("missing_direction_scores",),
            decision_version=DECISION_VERSION,
        )

    if long_score >= short_score:
        side = "LONG"
        winning_score = long_score
        losing_score = short_score
    else:
        side = "SHORT"
        winning_score = short_score
        losing_score = long_score

    edge = winning_score - losing_score
    reasons.append(
        f"score:{side}={winning_score:.2f},opposite={losing_score:.2f},edge={edge:.2f}"
    )

    if winning_score < cfg.min_score:
        reasons.append(f"score_below_{cfg.min_score:.0f}")
        return replace(
            movement,
            decision="NO TRADE",
            decision_side_candidate=side,
            decision_context_confirmations=0,
            decision_context_conflicts=0,
            decision_context_balance=0,
            decision_reasons=tuple(reasons),
            decision_version=DECISION_VERSION,
        )

    if edge < cfg.min_edge:
        reasons.append(f"edge_below_{cfg.min_edge:.0f}")
        return replace(
            movement,
            decision="NO TRADE",
            decision_side_candidate=side,
            decision_context_confirmations=0,
            decision_context_conflicts=0,
            decision_context_balance=0,
            decision_reasons=tuple(reasons),
            decision_version=DECISION_VERSION,
        )

    ctx = movement.market_context
    if not _required_context_complete(ctx):
        reasons.append("required_context_incomplete")
        if ctx is not None and ctx.context_errors:
            reasons.extend(f"context_error:{x}" for x in ctx.context_errors)
        return replace(
            movement,
            decision="NO TRADE",
            decision_side_candidate=side,
            decision_context_confirmations=0,
            decision_context_conflicts=0,
            decision_context_balance=0,
            decision_reasons=tuple(reasons),
            decision_version=DECISION_VERSION,
        )

    assert ctx is not None
    directional, core_directional, conflicts, activity, neutral = _context_votes(
        side,
        ctx,
    )
    n_confirm = len(directional)
    n_core_confirm = len(core_directional)
    n_conflict = len(conflicts)
    balance = n_confirm - n_conflict

    reasons.extend(f"confirm:{item}" for item in directional)
    reasons.extend(f"activity:{item}" for item in activity)
    reasons.extend(f"conflict:{item}" for item in conflicts)
    reasons.extend(f"context:{item}" for item in neutral)

    # A confirmed structural break directly against the proposed side is a
    # hard contradiction. Softer conflicts can still be outweighed by aligned
    # directional context, but activity cannot offset a directional conflict.
    hard_structure_conflict = (
        (side == "LONG" and ctx.structure_status == "BREAKDOWN")
        or (side == "SHORT" and ctx.structure_status == "BREAKOUT")
    )
    if hard_structure_conflict:
        reasons.append("hard_structure_conflict")
        decision = "NO TRADE"
    else:
        required_confirmations = (
            cfg.ignition_min_confirmations
            if movement.stage == "IGNITION"
            else cfg.expansion_min_confirmations
        )

        if n_core_confirm < cfg.min_core_directional_confirmations:
            reasons.append(
                "core_directional_confirmations_below_"
                f"{cfg.min_core_directional_confirmations}"
            )
            decision = "NO TRADE"
        elif n_confirm < required_confirmations:
            reasons.append(
                f"directional_confirmations_below_{required_confirmations}"
            )
            decision = "NO TRADE"
        elif balance < cfg.min_context_balance:
            reasons.append(
                f"directional_balance_below_{cfg.min_context_balance}"
            )
            decision = "NO TRADE"
        else:
            decision = side

    return replace(
        movement,
        decision=decision,
        decision_side_candidate=side,
        decision_context_confirmations=n_confirm,
        decision_context_conflicts=n_conflict,
        decision_context_balance=balance,
        decision_reasons=tuple(reasons),
        decision_version=DECISION_VERSION,
    )
