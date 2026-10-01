from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_radar.fresh_entry_gate import STAGE11C_VERSION
from market_radar.pipeline_cohort import (
    POST_COHORT,
    backfill_position_cohorts,
    cohort_summary,
)


def main() -> None:
    counts = backfill_position_cohorts()
    summary = cohort_summary()

    post_rows = [
        row
        for row in summary.get("cohorts", [])
        if row.get("cohort") == POST_COHORT
    ]
    current_rows = [
        row
        for row in post_rows
        if row.get("fresh_gate_version") == STAGE11C_VERSION
    ]
    unknown_rows = [
        row
        for row in post_rows
        if row.get("fresh_gate_version") == "unknown"
    ]
    other_known_rows = [
        row
        for row in post_rows
        if row.get("fresh_gate_version") not in {STAGE11C_VERSION, "unknown"}
    ]

    output = {
        "wd0_status": "READY_FOR_WD1" if not unknown_rows else "READY_WITH_QUARANTINE",
        "cohort_version": summary.get("cohort_version"),
        "boundary_ms": summary.get("boundary_ms"),
        "stage11c_current_version": STAGE11C_VERSION,
        "backfill_counts": counts,
        "wd1_eligible_current_v2": {
            "trades": sum(int(row.get("trades") or 0) for row in current_rows),
            "closed": sum(int(row.get("closed") or 0) for row in current_rows),
        },
        "quarantined_unknown": {
            "trades": sum(int(row.get("trades") or 0) for row in unknown_rows),
            "closed": sum(int(row.get("closed") or 0) for row in unknown_rows),
        },
        "historical_known_other_versions": other_known_rows,
        "cohort_summary": post_rows,
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()

[executed on device: core-prod (c128f313-5bdb-41c3-a53a-0590e5cfa134)]