from __future__ import annotations

import unittest

from research.profit_protection_v3.stage2a_peak_continuation_anatomy import (
    FastObservation,
    PeakCandidate,
    candidate_metrics,
    first_horizon_index,
    record_local_peak_candidates,
)


def obs(ms: int, pnl: float, **snapshot):
    return FastObservation(
        evaluated_at_ms=ms,
        current_pnl_pct=pnl,
        snapshot=snapshot,
    )


class PPV3Stage2APeakContinuationAnatomyTests(unittest.TestCase):
    def test_record_local_peaks_label_only_last_terminal(self) -> None:
        stream = [
            obs(0, 0.20),
            obs(15_000, 0.40),
            obs(30_000, 0.35),
            obs(45_000, 0.55),
            obs(60_000, 0.50),
            obs(75_000, 0.70),
            obs(90_000, 0.60),
        ]
        out = record_local_peak_candidates("P1", stream, arm_pct=0.30)
        self.assertEqual([item.peak_pct for item in out], [0.40, 0.55, 0.70])
        self.assertEqual([item.label for item in out], ["CONTINUED", "CONTINUED", "TERMINAL"])

    def test_censored_final_high_without_retracement_is_not_candidate(self) -> None:
        stream = [
            obs(0, 0.30),
            obs(15_000, 0.40),
            obs(30_000, 0.50),
        ]
        out = record_local_peak_candidates("P1", stream, arm_pct=0.30)
        self.assertEqual(out, [])

    def test_last_local_peak_remains_continued_if_later_final_record_is_higher(self) -> None:
        stream = [
            obs(0, 0.40),
            obs(15_000, 0.35),
            obs(30_000, 0.50),
        ]
        out = record_local_peak_candidates("P1", stream, arm_pct=0.30)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].label, "CONTINUED")

    def test_first_horizon_index_uses_first_poll_at_or_after_target(self) -> None:
        stream = [
            obs(0, 0.50),
            obs(14_000, 0.48),
            obs(31_000, 0.44),
            obs(48_000, 0.46),
        ]
        self.assertEqual(first_horizon_index(stream, candidate_index=0, horizon_seconds=15), 2)
        self.assertEqual(first_horizon_index(stream, candidate_index=0, horizon_seconds=45), 3)

    def test_candidate_metrics_preserve_causal_horizon_snapshot(self) -> None:
        stream = [
            obs(0, 1.00),
            obs(15_000, 0.90, flow_aligned=True),
            obs(30_000, 0.80, flow_opposite=True, contradictions=["x"]),
        ]
        candidate = PeakCandidate("P1", 0, 1.00, "TERMINAL")
        out = candidate_metrics(stream, candidate, horizon_seconds=30)
        assert out is not None
        self.assertAlmostEqual(out["giveback_ratio"], 0.20)
        self.assertAlmostEqual(out["recovery_ratio"], 0.90)
        self.assertTrue(out["flow_opposite"])
        self.assertEqual(out["contradictions"], 1)

    def test_candidate_metrics_detect_new_high_by_recovery_ratio(self) -> None:
        stream = [
            obs(0, 1.00),
            obs(15_000, 0.92),
            obs(30_000, 1.05),
        ]
        candidate = PeakCandidate("P1", 0, 1.00, "CONTINUED")
        out = candidate_metrics(stream, candidate, horizon_seconds=30)
        assert out is not None
        self.assertGreater(out["recovery_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
