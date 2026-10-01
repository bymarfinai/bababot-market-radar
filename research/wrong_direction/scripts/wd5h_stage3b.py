from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research.wrong_direction.wd5h_stage3b import run_wd5h_stage3b


def main() -> None:
    r = run_wd5h_stage3b()
    print(json.dumps({
        "version": r["version"],
        "feature_count": r["feature_count"],
        "split_summary": r["split_summary"],
        "hyperparameters": {
            k: {
                "purge": v["purge"],
                "inner_train_n": v["inner_train_n"],
                "inner_val_n": v["inner_val_n"],
                "selected": {
                    "top_k": v["selected"]["top_k"],
                    "l2": v["selected"]["l2"],
                    "metrics": v["selected"]["metrics"],
                    "features": v["selected"]["features"],
                },
            }
            for k, v in r["hyperparameters"].items()
        },
        "outer_validation": r["outer_validation"],
        "selected_architecture": r["selected_architecture"],
        "final_test": r["final_test"],
        "assessment": r["assessment"],
        "outputs": r["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
