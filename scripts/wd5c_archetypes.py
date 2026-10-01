from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_radar.wd5c_archetypes import run_wd5c


def main() -> None:
    result = run_wd5c()
    compact = {
        "version": result["version"],
        "rows": result["rows"],
        "causal_audit": result["causal_audit"],
        "opportunity": result["group_summaries"]["label_opportunity_tier"],
        "realized": result["group_summaries"]["label_realized_win_tier"],
        "capture": result["group_summaries"]["label_capture_class"],
        "composite": result["group_summaries"]["label_composite_archetype"],
        "output": result["outputs"],
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
