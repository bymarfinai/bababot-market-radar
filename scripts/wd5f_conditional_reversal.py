from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_radar.wd5f_conditional_reversal import run_wd5f


def main() -> None:
    result = run_wd5f()
    compact = {
        "version": result["version"],
        "cohort": result["cohort"],
        "split": result["split"],
        "selected_variant": result["selected_variant"],
        "selected": {
            "validation": result["selected"]["validation"],
            "test": result["selected"]["test"],
            "test_triage": result["selected"]["test_triage"],
            "novel_symbol_n": result["selected"]["novel_symbol_n"],
            "novel_symbol_metrics": result["selected"]["novel_symbol_metrics"],
            "one_sided_reverse_gate": result["selected"]["one_sided_reverse_gate"],
            "test_one_sided_reverse_gate": result["selected"]["test_one_sided_reverse_gate"],
            "novel_symbol_one_sided_reverse_gate": result["selected"]["novel_symbol_one_sided_reverse_gate"],
            "features": result["selected"]["selected_features"],
        },
        "nonlinear": result["nonlinear_sensitivity"]["selected"],
        "promotion": result["promotion_assessment"],
        "outputs": result["outputs"],
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
