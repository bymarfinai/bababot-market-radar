from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research.wrong_direction.wd5h_stage4b import run_wd5h_stage4b


def main() -> None:
    r = run_wd5h_stage4b()
    print(json.dumps({
        "version": r["version"],
        "split_counts": r["split_counts"],
        "horizon_comparison": r["horizon_comparison"],
        "descriptive_best_horizon": r["descriptive_best_horizon"],
        "horizons": {
            h: {
                "eligible_feature_n": x["eligible_feature_n"],
                "stable_direction_n": x["stable_direction_n"],
                "robust_n": x["robust_n"],
                "strong_n": x["strong_n"],
                "families": x["families"],
                "top_20": x["top_20"],
            }
            for h, x in r["horizons"].items()
        },
        "diagnostic_models": r["diagnostic_models"],
        "direct_confirmation_features": r["direct_confirmation_features"],
        "stage_conclusion": r["stage_conclusion"],
        "outputs": r["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
