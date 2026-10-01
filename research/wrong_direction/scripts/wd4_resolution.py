from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.wrong_direction.wd4_resolution import run_wd4


def main() -> None:
    result = run_wd4()
    output = Path("/app/data/wd4_resolution_results.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({
        "version": result["version"],
        "wrong_direction_n": result["wrong_direction_n"],
        "primary_horizon_min": result["primary_horizon_min"],
        "primary_summary": result["summaries"][str(result["primary_horizon_min"])],
        "output": str(output),
    }, indent=2))


if __name__ == "__main__":
    main()
