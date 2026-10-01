from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research.wrong_direction.wd5h_stage3a import run_wd5h_stage3a


def main() -> None:
    r = run_wd5h_stage3a()
    print(json.dumps({
        "version": r["version"],
        "method": r["method"],
        "coverage": r["coverage"],
        "primary_label_summary": r["primary_label_summary"],
        "key_relabeling": r["key_relabeling"],
        "overlap_uniqueness": r["overlap_uniqueness"],
        "primary_by_wd1": r["primary_by_wd1"],
        "sensitivity_summary": {
            name: value["label_summary"]
            for name, value in r["sensitivity"].items()
        },
        "stage_conclusion": r["stage_conclusion"],
        "outputs": r["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
