from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.wrong_direction.wd5e_multihead import run_wd5e


def main() -> None:
    result = run_wd5e()
    compact = {
        "version": result["version"],
        "micro_feature_count": result["micro_feature_count"],
        "micro_coverage": result["micro_coverage"],
        "heads": {
            name: {
                "n": head["n"],
                "selected_variant": head["selected_variant"],
                "validation": head["selected"]["validation"],
                "test": head["selected"]["test"],
                "validation_triage": head["selected"]["validation_triage"]["selected"],
                "test_triage": head["selected"]["test_triage"],
                "features": head["selected"]["selected_features"],
            }
            for name, head in result["heads"].items()
        },
        "outputs": result["outputs"],
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
