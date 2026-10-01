from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_radar.wd5h_stage2 import run_wd5h_stage2


def main() -> None:
    r = run_wd5h_stage2()
    print(json.dumps({
        "version": r["version"],
        "split": r["split"],
        "heads": {
            k: {
                "train_pair_n": v["train_pair_n"],
                "inner_validation": v["inner_validation"],
                "selected_top_k": v["selected_top_k"],
                "selected_l2": v["selected_l2"],
                "features": v["selected_features"],
            }
            for k, v in r["heads"].items()
        },
        "pairwise_validation": r["pairwise_validation"],
        "pairwise_test": r["pairwise_test"],
        "hierarchical": {
            "selected_thresholds": r["hierarchical_gate"]["selected_thresholds"],
            "validation": r["hierarchical_gate"]["validation"],
            "test": r["hierarchical_gate"]["test"],
            "novel_symbol_test": r["hierarchical_gate"]["novel_symbol_test"],
            "frontier": r["hierarchical_gate"]["threshold_search"]["precision_frontier"],
        },
        "flat": {
            "threshold": r["flat_baseline"]["selected_threshold"],
            "validation": r["flat_baseline"]["validation"],
            "test": r["flat_baseline"]["test"],
            "frontier": r["flat_baseline"]["threshold_search"]["precision_frontier"],
        },
        "assessment": r["assessment"],
        "outputs": r["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
