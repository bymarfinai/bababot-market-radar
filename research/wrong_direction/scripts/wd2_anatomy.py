from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.wrong_direction.wd2_anatomy import run_wd2


def main() -> None:
    result = run_wd2()
    output = Path("/app/data/wd2_anatomy_results.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({
        "version": result["version"],
        "trades": result["trades"],
        "gate_snapshot_missing": result["gate_snapshot_missing"],
        "output": str(output),
    }, indent=2))


if __name__ == "__main__":
    main()
