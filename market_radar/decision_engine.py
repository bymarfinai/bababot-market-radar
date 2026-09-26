from __future__ import annotations

from dataclasses import dataclass, replace

from .models import MarketContext, MovementDetection


DECISION_VERSION = "stage6-v1"


@dataclass(frozen=True)
class DecisionConfig:
    """Frozen Stage 6 decision gates.

    Score/edge gates preserve the existing MCD prototype defaults.
    Stage 5 context is used as confirmation/conflict; it never rewrites the
    Stage 4 LONG_SCORE/SHORT_SCORE.
    """

    min_score: float = 68.0
    min_edge: float = 10.0
    ignition_min_confirmations: int = 2
    expansion_min_confirmations: int = 1
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
) -> tuple[list[str], list[str], list[str]]:
    """Return confirmations, conflicts, and neutral observations.

    Funding is intentionally observational in Stage 6: the frozen blueprint
    says funding is positioning context, not a standalone trigger. No untested
    funding cutoff is invented here.
    """
    confirmations: list[str] = []
    conflicts: list[str] = []
    neutral: list[str] = []

    if ctx.volume_confirmed:
        confirmations.append("volume_expansion")
    else:
        neutral.append("volume_not_expanded")

    if side == "LONG":
        if ctx.structure_status == "BREAKOUT":
            confirmations.append("confirmed_breakout")
        elif ctx.structure_status == "FAILED_BREAKDOWN":
            confirmations.append("failed_breakdown_reclaim")
        elif ctx.structure_status == "BREAKDOWN":
            conflicts.append("confirmed_breakdown")
        elif ctx.structure_status == "FAILED_BREAKOUT":
            conflicts.append("failed_breakout")
        else:
            neutral.append(f"structure_{ctx.structure_status.lower()}")

        if ctx.taker_bias == "BUY":
            confirmations.append("taker_buy")
        elif ctx.taker_bias == "SELL":
            conflicts.append("taker_sell")
        else:
            neutral.append("taker_balanced")

        if ctx.oi_interpretation == "FRESH_LONG_PARTICIPATION":
            confirmations.append("oi_fresh_long")
        elif ctx.oi_interpretation == "SHORT_COVERING":
            neutral.append("oi_short_covering")
        elif ctx.oi_interpretation == "FRESH_SHORT_PARTICIPATION":
            conflicts.append("oi_fresh_short")
        elif ctx.oi_interpretation == "LONG_LIQUIDATION":
            conflicts.append("oi_long_liquidation")
        else:
            neutral.append("oi_unresolved")

        if ctx.market_regime == "BULL":
            confirmations.append("regime_bull")
        elif ctx.market_regime == "BEAR":
            conflicts.append("regime_bear")
        else:
            neutral.append("regime_sideways")

    elif side == "SHORT":
        if ctx.structure_status == "BREAKDOWN":
            confirmations.append("confirmed_breakdown")
        elif ctx.structure_status == "FAILED_BREAKOUT":
            confirmations.append("failed_breakout_reject")
        elif ctx.structure_status == "BREAKOUT":
            conflicts.append("confirmed_breakout")
        elif ctx.structure_status == "FAILED_BREAKDOWN":
            conflicts.append("failed_breakdown")
        else:
            neutral.append(f"structure_{ctx.structure_status.lower()}")

        if ctx.taker_bias == "SELL":
            confirmations.append("taker_sell")
        elif ctx.taker_bias == "BUY":
            conflicts.append("taker_buy")
        else:
            neutral.append("taker_balanced")

        if ctx.oi_interpretation == "FRESH_SHORT_PARTICIPATION":
            confirmations.append("oi_fresh_short")
        elif ctx.oi_interpretation == "LONG_LIQUIDATION":
            neutral.append("oi_long_liquidation")
        elif ctx.oi_interpretation == "FRESH_LONG_PARTICIPATION":
            conflicts.append("oi_fresh_long")
        elif ctx.oi_interpretation == "SHORT_COVERING":
            conflicts.append("oi_short_covering")
        else:
            neutral.append("oi_unresolved")

        if ctx.market_regime == "BEAR":
            confirmations.append("regime_bear")
        elif ctx.market_regime == "BULL":
            conflicts.append("regime_bull")
        else:
            neutral.append("regime_sideways")

    else:
        raise ValueError(f"invalid side: {side}")

    if ctx.funding_rate is not None:
        neutral.append(f"funding={ctx.funding_rate:+.8f}")

    return confirmations, conflicts, neutral


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
    confirmations, conflicts, neutral = _context_votes(side, ctx)
    n_confirm = len(confirmations)
    n_conflict = len(conflicts)
    balance = n_confirm - n_conflict

    reasons.extend(f"confirm:{item}" for item in confirmations)
    reasons.extend(f"conflict:{item}" for item in conflicts)
    reasons.extend(f"context:{item}" for item in neutral)

    # A confirmed structural break directly against the proposed side is a
    # hard contradiction. Softer conflicts can be outweighed by confirmations.
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

        if n_confirm < required_confirmations:
            reasons.append(
                f"confirmations_below_{required_confirmations}"
            )
            decision = "NO TRADE"
        elif balance < cfg.min_context_balance:
            reasons.append(
                f"context_balance_below_{cfg.min_context_balance}"
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
