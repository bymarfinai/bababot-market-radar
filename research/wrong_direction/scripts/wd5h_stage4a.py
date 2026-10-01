from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research.wrong_direction.wd5h_stage4a import run_wd5h_stage4a


def main() -> None:
    print(json.dumps(run_wd5h_stage4a(), indent=2))


if __name__ == "__main__":
    main()
