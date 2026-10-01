from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research.wrong_direction.wd5h_stage3c import run_wd5h_stage3c


def main() -> None:
    r = run_wd5h_stage3c()
    print(json.dumps({
        "version": r["version"],
        "method": r["method"],
        "primary_model": r["primary_model"],
        "diagnostic_weighted_sensitivity": (
            r["diagnostic_weighted_sensitivity"]
        ),
        "assessment": r["assessment"],
        "outputs": r["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
