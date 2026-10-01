from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.wrong_direction.wd5h_stage1 import run_wd5h_stage1


def main() -> None:
    r = run_wd5h_stage1()
    print(json.dumps({
        "version": r["version"],
        "coverage": r["coverage"],
        "labels": r["label_summary"],
        "feature_count": r["feature_count"],
        "feature_families": r["feature_family_counts"],
        "comparisons": {
            x["comparison"]: {
                "positive_n": x["positive_n"],
                "negative_n": x["negative_n"],
                "stable_feature_count": x["stable_feature_count"],
                "stable_family_counts": x["stable_family_counts"],
                "top_features": [
                    {
                        "feature": y["feature"],
                        "family": y["family"],
                        "separation": y["separation"],
                        "median_fifth_separation": y[
                            "median_fifth_separation"
                        ],
                        "min_fifth_separation": y[
                            "min_fifth_separation"
                        ],
                    }
                    for y in x["top_features"][:12]
                ],
            }
            for x in r["comparisons"]
        },
        "conclusion": r["conclusion"],
        "outputs": r["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
