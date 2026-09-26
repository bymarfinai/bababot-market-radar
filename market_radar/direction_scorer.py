from __future__ import annotations

from dataclasses import dataclass, replace

from .models import MovementDetection


DIRECTION_SCORE_VERSION = "stage4-v1"


@dataclass(frozen=True)
class DirectionScoreConfig:
    """Stage 4 scoring weights.

    Stage 4 uses only evidence already produced by Stage 2/3. It intentionally
    does NOT read breakout/breakdown, taker flow, open interest, funding, or
    market regime; those belong to frozen Stage 5.
    """

    ret_5m_full_pct: float = 0.80
    ret_15m_full_pct: float = 1.80
    ret_1h_full_pct: float = 4.00
    acceleration_full_pct: float = 0.40

    return_expansion_full_ratio: float = 4.0
    volume_full_ratio: float = 3.0
    range_full_ratio: float = 2.5
    trades_full_ratio: float = 3.0


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _positive_points(value: float, full_at: float, points: float) -> float:
    if value <= 0.0 or full_at <= 0.0:
        return 0.0
    return points * _clip(value / full_at)


def _ratio_points(ratio: float, full_ratio: float, points: float) -> float:
    """Score expansion above 1.0x baseline."""
    if ratio <= 1.0 or full_ratio <= 1.0:
        return 0.0
    return points * _clip((ratio - 1.0) / (full_ratio - 1.0))


def _activity_alignment(r5: float, r15: float, r60: float) -> float:
    """Allocate non-directional activity evidence to a direction.

    Current 5m direction gets full activity evidence. If current 5m disagrees,
    a direction supported only by 15m or 1h can still retain partial evidence.
    This is why LONG_SCORE and SHORT_SCORE are independent rather than forced
    complements.
    """
    if r5 > 0.0:
        return 1.0
    if r15 > 0.0:
        return 0.50
    if r60 > 0.0:
        return 0.25
    return 0.0


def _score_side(
    movement: MovementDetection,
    sign: float,
    cfg: DirectionScoreConfig,
) -> tuple[float, dict[str, float]]:
    r5 = sign * movement.ret_5m_pct
    r15 = sign * movement.ret_15m_pct
    r60 = sign * movement.ret_1h_pct
    acceleration = r5 - (r15 / 3.0)

    # 50 points: signed price momentum and acceleration.
    momentum = (
        _positive_points(r5, cfg.ret_5m_full_pct, 20.0)
        + _positive_points(r15, cfg.ret_15m_full_pct, 15.0)
        + _positive_points(r60, cfg.ret_1h_full_pct, 10.0)
        + _positive_points(acceleration, cfg.acceleration_full_pct, 5.0)
    )

    # 25 points: movement/activity expansion already computed in Stage 2.
    # These metrics are non-directional, so they are gated by price alignment.
    activity_raw = (
        _ratio_points(
            movement.return_expansion_ratio,
            cfg.return_expansion_full_ratio,
            10.0,
        )
        + _ratio_points(movement.volume_ratio, cfg.volume_full_ratio, 6.0)
        + _ratio_points(movement.range_ratio, cfg.range_full_ratio, 5.0)
        + _ratio_points(movement.trades_ratio, cfg.trades_full_ratio, 4.0)
    )
    alignment = _activity_alignment(r5, r15, r60)
    activity = activity_raw * alignment

    # 10 points: Stage 2 persistence, only for the matching raw direction.
    side_hint = "UP" if sign > 0 else "DOWN"
    persistence = (
        10.0
        if movement.directional_persistence
        and movement.direction_hint == side_hint
        else 0.0
    )

    # 15 points: cross-timeframe directional consistency.
    consistency = 0.0
    if r5 > 0 and r15 > 0:
        consistency += 5.0
    if r15 > 0 and r60 > 0:
        consistency += 5.0
    if r5 > 0 and r15 > 0 and r60 > 0:
        consistency += 5.0

    score = _clip(momentum + activity + persistence + consistency, 0.0, 100.0)

    components = {
        "momentum": round(momentum, 4),
        "activity": round(activity, 4),
        "persistence": round(persistence, 4),
        "timeframe_consistency": round(consistency, 4),
    }
    return round(score, 2), components


def score_directions(
    movement: MovementDetection,
    config: DirectionScoreConfig | None = None,
) -> MovementDetection:
    """Attach independent LONG_SCORE and SHORT_SCORE.

    Scores measure directional evidence only. They are not an order signal and
    are not required to sum to 100.

    Stage 4 does NOT produce LONG/SHORT/NO TRADE. Final decisions remain frozen
    for Stage 6 after Stage 5 context is available.
    """
    cfg = config or DirectionScoreConfig()

    if not movement.is_moving:
        return replace(
            movement,
            long_score=0.0,
            short_score=0.0,
            score_gap=0.0,
            score_edge=0.0,
            long_score_components={},
            short_score_components={},
            direction_score_version=DIRECTION_SCORE_VERSION,
        )

    if movement.stage not in {"IGNITION", "EXPANSION", "EXHAUSTION"}:
        raise ValueError(
            f"{movement.symbol}: Stage 4 requires a valid Stage 3 classification"
        )

    long_score, long_components = _score_side(movement, +1.0, cfg)
    short_score, short_components = _score_side(movement, -1.0, cfg)

    gap = round(long_score - short_score, 2)
    edge = round(abs(gap), 2)

    return replace(
        movement,
        long_score=long_score,
        short_score=short_score,
        score_gap=gap,
        score_edge=edge,
        long_score_components=long_components,
        short_score_components=short_components,
        direction_score_version=DIRECTION_SCORE_VERSION,
    )
