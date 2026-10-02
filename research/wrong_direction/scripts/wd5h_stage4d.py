from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research.wrong_direction.wd5h_stage4d import run_wd5h_stage4d


def main() -> None:
    print(json.dumps(run_wd5h_stage4d(), indent=2))


if __name__ == "__main__":
    main()
