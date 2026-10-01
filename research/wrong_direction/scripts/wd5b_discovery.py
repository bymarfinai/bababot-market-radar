from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.wrong_direction.wd5b_discovery import run_wd5b


def main() -> None:
    result = run_wd5b()
    compact = {
        "version": result["version"],
        "rows": result["rows"],
        "class_counts": result["class_counts"],
        "primary": result["variants"]["portable_market"],
        "output": "/app/data/wd5b_discriminator_results.json",
    }
    # Keep terminal output compact; full result is persisted to JSON.
    compact["primary"].pop("model", None)
    compact["primary"].pop("outer_validation", None)
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
