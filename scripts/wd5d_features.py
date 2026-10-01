from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_radar.wd5d_features import run_wd5d


def main() -> None:
    result = run_wd5d()
    compact = {
        "version": result["version"],
        "rows": result["rows"],
        "new_feature_count": result["new_feature_count"],
        "model_comparison": {
            task: {
                name: {
                    "validation": data["selected"]["validation"],
                    "test": data["selected"]["test"],
                    "features": data["selected"]["features"],
                }
                for name, data in payload["variants"].items()
            }
            for task, payload in result["model_comparison"].items()
        },
        "output": result["outputs"],
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
