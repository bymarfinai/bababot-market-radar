from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_radar.pipeline_cohort import backfill_position_cohorts
from market_radar.wrong_direction_labels import (
    backfill_wd1_labels,
    wd1_summary,
)


def main() -> None:
    wd0 = backfill_position_cohorts()
    wd1 = backfill_wd1_labels()
    summary = wd1_summary()

    output = {
        "stage": "WD-1",
        "status": (
            "LABELED"
            if wd1["eligible_closed_positions"] > 0
            else "NO_ELIGIBLE_TRADES"
        ),
        "wd0_backfill_counts": wd0,
        "wd1_backfill": wd1,
        "wd1_summary": summary,
        "next_stage": "WD-2_ANATOMY_BY_HORIZON",
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
