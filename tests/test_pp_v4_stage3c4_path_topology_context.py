from __future__ import annotations

import unittest

from research.profit_protection_v4.stage3c4_path_topology_context import (
    topology_votes,
    topology_veto_signal,
)


def obs(ms: int, pnl: float) -> dict[str, float | int]:
    return {
        "observed_at_ms": ms,
        "current_pnl_pct": pnl,
        "current_price": 100.0,
    }


class PPV4Stage3C4TopologyContextTests(unittest.TestCase):
    def test_context_bonus_adds_exactly_one_vote(self):
        path = [
            obs(0, 1.00),
            obs(5000, 1.10),
            obs(10000, 1.20),
            obs(15000, 1.30),
            obs(20000, 1.40),
            obs(25000, 1.50),
            obs(30000, 1.60),
        ]
        base = topology_votes(
            path,
            len(path) - 1,
            running_peak=1.60,
            lookback_seconds=30,
            strong_entry_context=True,
            context_mode="PATH_ONLY",
        )
        context = topology_votes(
            path,
            len(path) - 1,
            running_peak=1.60,
            lookback_seconds=30,
            strong_entry_context=True,
            context_mode="CONTEXT_BONUS",
        )
        self.assertFalse(base["context_vote"])
        self.assertTrue(context["context_vote"])
        self.assertEqual(
            context["vote_count"],
            base["vote_count"] + 1,
        )

    def test_veto_success_requires_new_high(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(10000, 1.78),
            obs(15000, 1.76),
            obs(20000, 2.05),
            obs(25000, 2.04),
        ]
        signal, decisions = topology_veto_signal(
            path,
            lookback_seconds=30,
            required_votes=0,
            context_mode="PATH_ONLY",
            strong_entry_context=False,
        )
        self.assertIsNone(signal)
        self.assertTrue(
            any(
                item["veto_outcome"] == "SUCCESS_NEW_HIGH"
                for item in decisions
            )
        )

    def test_grace_timeout_closes_without_new_high(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(10000, 1.75),
            obs(15000, 1.70),
            obs(20000, 1.68),
            obs(25000, 1.65),
        ]
        signal, decisions = topology_veto_signal(
            path,
            lookback_seconds=30,
            required_votes=0,
            context_mode="PATH_ONLY",
            strong_entry_context=False,
        )
        self.assertIsNotNone(signal)
        self.assertEqual(
            signal["close_reason"],
            "GRACE_TIMEOUT_CLOSE",
        )
        self.assertTrue(
            any(
                item["veto_outcome"] == "GRACE_TIMEOUT_CLOSE"
                for item in decisions
            )
        )

    def test_no_veto_allows_v42_candidate_immediately(self):
        path = [
            obs(0, 1.50),
            obs(5000, 2.00),
            obs(10000, 1.75),
            obs(15000, 1.70),
        ]
        signal, decisions = topology_veto_signal(
            path,
            lookback_seconds=30,
            required_votes=99,
            context_mode="PATH_ONLY",
            strong_entry_context=False,
        )
        self.assertIsNotNone(signal)
        self.assertEqual(signal["signal_at_ms"], 15000)
        self.assertEqual(signal["close_reason"], "ALLOW_CLOSE")
        self.assertEqual(
            decisions[-1]["veto_outcome"],
            "ALLOW_CLOSE",
        )


if __name__ == "__main__":
    unittest.main()
