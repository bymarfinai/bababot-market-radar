from __future__ import annotations

from dataclasses import replace

from .models import MovementDetection


MOVEMENT_STAGE_VERSION = "stage3-v1"

VALID_STAGES = {"IGNITION", "EXPANSION", "EXHAUSTION"}


def classify_movement_stage(movement: MovementDetection) -> MovementDetection:
    """Attach the frozen Stage 3 movement stage to a Stage 2 result.

    Stage 3 is intentionally downstream of movement detection:

      EARLY_MOVEMENT       -> IGNITION
      STRONG_CONTINUATION  -> EXPANSION
      LATE_MOVEMENT        -> EXHAUSTION

    NOISE/NORMAL/non-moving observations do not receive a trading stage.

    This function does NOT calculate LONG_SCORE/SHORT_SCORE and does NOT
    produce LONG/SHORT/NO TRADE. Those belong to later frozen stages.
    """
    if not movement.is_moving:
        return replace(
            movement,
            stage=None,
            stage_classifier_version=MOVEMENT_STAGE_VERSION,
        )

    mapping = {
        "EARLY_MOVEMENT": "IGNITION",
        "STRONG_CONTINUATION": "EXPANSION",
        "LATE_MOVEMENT": "EXHAUSTION",
    }

    stage = mapping.get(movement.movement_state)
    if stage is None:
        raise ValueError(
            f"{movement.symbol}: moving state {movement.movement_state!r} "
            "has no Stage 3 mapping"
        )

    return replace(
        movement,
        stage=stage,
        stage_classifier_version=MOVEMENT_STAGE_VERSION,
    )
