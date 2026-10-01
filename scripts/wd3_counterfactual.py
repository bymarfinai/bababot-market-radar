from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_radar.wd3_counterfactual import run_wd3


def main() -> None:
    result = run_wd3()
    output = Path("/app/data/wd3_counterfactual_results.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({
        "version": result["version"],
        "full_cohort_n": result["full_cohort_n"],
        "actual_net": result["actual_net"],
        "top_dynamic": result["ranked_dynamic_exit"][0] if result["ranked_dynamic_exit"] else None,
        "top_delay": result["ranked_delay_confirm"][0] if result["ranked_delay_confirm"] else None,
        "output": str(output),
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
