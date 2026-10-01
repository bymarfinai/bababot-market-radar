from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research.wrong_direction.wd5g_replay import run_wd5g


def main() -> None:
    r = run_wd5g()
    print(json.dumps({
        "version": r["version"],
        "coverage": r["coverage"],
        "baseline": r["baseline"],
        "health_only": r["health_only_ablation"],
        "primary": r["wd5g_primary"],
        "delta": r["deltas_vs_baseline"],
        "incremental_reverse": r["incremental_reverse_vs_health_only"],
        "wrong_direction": r["wrong_direction"],
        "runner_preservation": r["runner_preservation"],
        "winner_preservation": r["realized_winner_preservation"],
        "reverse_execution": r["reverse_execution"],
        "outputs": r["outputs"],
    }, indent=2))


if __name__ == "__main__":
    main()
