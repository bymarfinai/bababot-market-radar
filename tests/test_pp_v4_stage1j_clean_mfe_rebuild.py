from __future__ import annotations

import unittest

from research.profit_protection_v4.stage1j_clean_mfe_rebuild import (
    build_result,
    distribution,
    enrich,
)


class PPV4Stage1JCleanMFERebuildTests(unittest.TestCase):
    def row(
        self,
        *,
        pid: str,
        side: str = "LONG",
        clean_mfe: float = 1.0,
        old_mfe: float = 1.0,
        peak5: float = 0.9,
        peak15: float = 0.7,
        opened_at_ms: int = 1,
    ) -> dict:
        return {
            "position_id": pid,
            "symbol": "TESTUSDT",
            "side": side,
            "opened_at_ms": opened_at_ms,
            "closed_at_ms": opened_at_ms + 60_000,
            "entry_price": 100.0,
            "peak5": peak5,
            "peak15": peak15,
            "old_mfe": old_mfe,
            "clean_post_entry_mfe_pct": clean_mfe,
        }

    def test_enrich_uses_clean_mfe_for_eligibility(self) -> None:
        rows = [
            self.row(pid="A", clean_mfe=0.29, old_mfe=1.0),
            self.row(pid="B", clean_mfe=0.50, old_mfe=0.50, peak5=0.40, peak15=0.30),
        ]
        result = enrich(rows)
        self.assertEqual([row["position_id"] for row in result], ["B"])
        self.assertAlmostEqual(result[0]["capture_5s_ratio"], 0.80)

    def test_distribution_reports_tail_shares(self) -> None:
        result = distribution([0.50, 0.80, 0.90, 1.00])
        self.assertAlmostEqual(result["lt80_share_pct"], 25.0)
        self.assertAlmostEqual(result["ge90_share_pct"], 50.0)

    def test_build_result_counts_false_old_eligibility(self) -> None:
        rows = [
            self.row(pid="A", clean_mfe=0.20, old_mfe=1.0),
            self.row(pid="B", clean_mfe=1.0, old_mfe=1.0, peak5=0.95, peak15=0.80),
        ]
        result = build_result(rows)
        self.assertEqual(
            result["population"]["old_mfe_ge_0_30_but_clean_lt_0_30"],
            1,
        )
        self.assertEqual(result["population"]["clean_mfe_ge_0_30"], 1)

    def test_build_result_detects_5s_uplift(self) -> None:
        rows = [
            self.row(
                pid=f"P{i}",
                clean_mfe=1.0,
                old_mfe=1.0,
                peak5=0.95,
                peak15=0.75,
                opened_at_ms=i + 1,
            )
            for i in range(120)
        ]
        result = build_result(rows)
        self.assertGreater(
            result["overall"]["delta"]["median_capture_pp"],
            0.0,
        )
        self.assertGreater(
            result["overall"]["delta"]["ge90_share_pp"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
