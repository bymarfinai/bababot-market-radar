from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.wrong_direction.wd5a_features import build_dataset


def main() -> None:
    manifest = build_dataset()
    print(json.dumps({
        "version": manifest["version"],
        "rows": manifest["rows"],
        "feature_count": manifest["feature_count"],
        "numeric_feature_count": manifest["numeric_feature_count"],
        "categorical_feature_count": manifest["categorical_feature_count"],
        "target_counts": manifest["target_counts"],
        "causal_audit": manifest["causal_audit"],
        "outputs": manifest["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
