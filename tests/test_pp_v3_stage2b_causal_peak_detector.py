from __future__ import annotations

import unittest

from research.profit_protection_v3.stage2a_peak_continuation_anatomy import (
    FastObservation,
    PeakCandidate,
)
from research.profit_protection_v3.stage2b_causal_peak_detector import (
    DetectorConfig,
    _auc,
    _threshold_for_fpr,
    build_rule_configs,
    replay_candidate,
)


def obs(ms: int, pnl: float, **snapshot):
    return FastObservation(
        evaluated_at_ms=ms,
        current_pnl_pct=pnl,
        snapshot=snapshot,
    )


class PPV3Stage2BCausalPeakDetectorTests(unittest.TestCase):
    def test_higher_high_cancels_candidate_before_later_weakness(self) -> None:
        stream = [
            obs(0, 1.00),
            obs(15_000, 0.92),
            obs(30_000, 1.02),
            obs(45_000, 0.60),
        ]
        candidate = PeakCandidate("P1", 0, 1.00, "CONTINUED")
        config = DetectorConfig(None, 0.30, 0.10, 0.50, False)
        self.assertIsNone(replay_candidate(stream, candidate, config))

    def test_hard_first_can_fire_on_first_retracement(self) -> None:
        stream = [obs(0, 1.00), obs(15_000, 0.75)]
        candidate = PeakCandidate("P1", 0, 1.00, "TERMINAL")
        config = DetectorConfig(0.20, None, 0.15, 0.50, False)
        out = replay_candidate(stream, candidate, config)
        assert out is not None
        self.assertEqual(out.step, 1)
        self.assertEqual(out.reason, "HARD_FIRST")
        self.assertAlmostEqual(out.giveback_ratio, 0.25)

    def test_soft_recovery_rule_does_not_fire_on_step_one(self) -> None:
        stream = [obs(0, 1.00), obs(15_000, 0.80)]
        candidate = PeakCandidate("P1", 0, 1.00, "TERMINAL")
        config = DetectorConfig(None, None, 0.15, 0.50, False)
        self.assertIsNone(replay_candidate(stream, candidate, config))

    def test_soft_recovery_rule_can_fire_on_second_failed_poll(self) -> None:
        stream = [
            obs(0, 1.00),
            obs(15_000, 0.90),
            obs(30_000, 0.80),
        ]
        candidate = PeakCandidate("P1", 0, 1.00, "TERMINAL")
        config = DetectorConfig(None, None, 0.15, 0.25, False)
        out = replay_candidate(stream, candidate, config)
        assert out is not None
        self.assertEqual(out.step, 2)
        self.assertEqual(out.reason, "RECOVERY_FAIL")
        self.assertAlmostEqual(out.giveback_ratio, 0.20)

    def test_flow_alignment_can_block_soft_trigger(self) -> None:
        stream = [
            obs(0, 1.00),
            obs(15_000, 0.90),
            obs(30_000, 0.80, flow_aligned=True),
        ]
        candidate = PeakCandidate("P1", 0, 1.00, "TERMINAL")
        config = DetectorConfig(None, None, 0.15, 0.25, True)
        self.assertIsNone(replay_candidate(stream, candidate, config))

    def test_frozen_rule_grid_has_171_configs(self) -> None:
        self.assertEqual(len(build_rule_configs()), 171)

    def test_auc_is_one_for_perfect_ranking(self) -> None:
        self.assertAlmostEqual(
            _auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]),
            1.0,
        )

    def test_threshold_respects_training_false_positive_cap(self) -> None:
        labels = [0, 0, 0, 1, 1]
        scores = [0.1, 0.2, 0.3, 0.4, 0.9]
        threshold = _threshold_for_fpr(labels, scores, max_fpr=0.0)
        false_positive = sum(
            label == 0 and score >= threshold
            for label, score in zip(labels, scores)
        )
        self.assertEqual(false_positive, 0)


if __name__ == "__main__":
    unittest.main()
