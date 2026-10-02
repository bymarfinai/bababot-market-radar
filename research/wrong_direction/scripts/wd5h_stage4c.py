from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research.wrong_direction.wd5h_stage4c import run_wd5h_stage4c


def main() -> None:
    r = run_wd5h_stage4c()
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
