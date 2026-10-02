from __future__ import annotations

import unittest

from market_radar.stage6_validation import (
    POLICIES,
    _evidence,
    _evaluate_lane,
    _feature_rows,
    _pp_decision_unified,
)


class PPDecisionV1RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.policy = POLICIES["PP-DECISION-V1"]

    def _decision(self, peak_roi, giveback, danger, status="OPEN"):
        peak = 100.0
        economic = peak * (1.0 - giveback)
        return _pp_decision_unified(
            self.policy,
            peak_roi=peak_roi,
            economic=economic,
            peak=peak,
            evidence={"danger_score": danger},
            status=status,
        )

    def test_sub1_exact_threshold_matrix(self):
        action, meta = self._decision(0.80, 0.2999, 6)
        self.assertEqual((meta["zone"], meta["gate"], action), ("SUB1", "ARMED_SUB1", "HOLD"))
        action, meta = self._decision(0.80, 0.30, 3)
        self.assertEqual((meta["gate"], action), ("WATCH", "HOLD"))
        action, meta = self._decision(0.80, 0.30, 4)
        self.assertEqual((meta["gate"], action), ("WATCH", "REDUCE"))
        action, meta = self._decision(0.80, 0.50, 1)
        self.assertEqual((meta["gate"], action), ("MANDATORY_DECISION", "HOLD"))
        action, meta = self._decision(0.80, 0.50, 2)
        self.assertEqual(action, "REDUCE")
        action, meta = self._decision(0.80, 0.50, 4)
        self.assertEqual(action, "CLOSE")
        action, meta = self._decision(0.80, 1.00, 0)
        self.assertEqual((meta["gate"], action), ("HARD_STOP", "CLOSE"))

    def test_ge1_exact_threshold_matrix(self):
        action, meta = self._decision(1.58, 0.2499, 6)
        self.assertEqual((meta["zone"], meta["gate"], action), ("GE1", "ARMED_GE1", "HOLD"))
        action, meta = self._decision(1.58, 0.25, 3)
        self.assertEqual((meta["gate"], action), ("WATCH", "HOLD"))
        action, meta = self._decision(1.58, 0.25, 4)
        self.assertEqual((meta["gate"], action), ("WATCH", "REDUCE"))
        action, meta = self._decision(1.58, 0.35, 1)
        self.assertEqual((meta["gate"], action), ("MANDATORY_DECISION", "HOLD"))
        action, meta = self._decision(1.58, 0.35, 2)
        self.assertEqual(action, "REDUCE")
        action, meta = self._decision(1.58, 0.35, 4)
        self.assertEqual(action, "CLOSE")
        action, meta = self._decision(1.58, 0.50, 0)
        self.assertEqual((meta["gate"], action), ("FORCE_PROTECT", "REDUCE"))
        action, meta = self._decision(1.58, 0.60, 0)
        self.assertEqual((meta["gate"], action), ("HARD_CLOSE", "CLOSE"))

    def test_peak_zone_is_sticky_after_crossing_one_percent(self):
        action, meta = self._decision(1.00001, 0.35, 2)
        self.assertEqual(meta["zone"], "GE1")
        self.assertEqual(action, "REDUCE")
        action, meta = self._decision(0.99999, 0.35, 2)
        self.assertEqual(meta["zone"], "SUB1")
        self.assertEqual(action, "HOLD")

    def test_missing_optional_evidence_is_safe(self):
        ev = _evidence(
            {"side_ret3": None, "micro_against": False, "taker_strength": None, "oi_change": None, "rv15": None},
            10.0,
        )
        self.assertEqual(ev["danger_score"], 0)
        action, meta = _pp_decision_unified(
            self.policy, peak_roi=1.58, economic=65.0, peak=100.0,
            evidence=ev, status="OPEN",
        )
        self.assertEqual(meta["gate"], "MANDATORY_DECISION")
        self.assertEqual(action, "HOLD")

    def test_high_volatility_alone_does_not_force_exit(self):
        ev = _evidence(
            {"side_ret3": 0.20, "micro_against": False, "taker_strength": 0.20, "oi_change": 0.20, "rv15": 10.0},
            4.0,
        )
        self.assertEqual(ev["vol_extreme"], 1)
        self.assertEqual(ev["danger_score"], 0)
        action, meta = _pp_decision_unified(
            self.policy, peak_roi=1.58, economic=65.0, peak=100.0,
            evidence=ev, status="OPEN",
        )
        self.assertEqual((meta["gate"], action), ("MANDATORY_DECISION", "HOLD"))

    def test_long_short_feature_symmetry(self):
        base=1_000_000
        long_prices=[100.0, 101.0, 102.0, 101.0]
        short_prices=[100.0, 99.0, 98.0, 99.0]
        def rows(prices, taker_share):
            out=[]
            for i,p in enumerate(prices):
                out.append([base+i*60_000,str(p),str(p*1.001),str(p*0.999),str(p),"100",base+i*60_000+59_999,"0",100,str(100*taker_share),"0","0"])
            return out
        long = _feature_rows(side="LONG", opened_at_ms=base, klines=rows(long_prices,0.40), oi_rows=[], now_ms=base+300_000)[-1]
        short = _feature_rows(side="SHORT", opened_at_ms=base, klines=rows(short_prices,0.60), oi_rows=[], now_ms=base+300_000)[-1]
        self.assertAlmostEqual(long["side_ret3"], short["side_ret3"], places=2)
        self.assertAlmostEqual(long["taker_strength"], short["taker_strength"], places=9)
        self.assertEqual(long["micro_against"], short["micro_against"])
        self.assertEqual(_evidence(long, 4.0)["danger_score"], _evidence(short, 4.0)["danger_score"])

    def test_reduced_lane_cannot_reduce_twice_at_decision_or_force_zone(self):
        for giveback in (0.35, 0.50):
            action, meta = self._decision(1.58, giveback, 2 if giveback == 0.35 else 0, status="REDUCED")
            self.assertEqual(action, "CLOSE", msg=(giveback, meta))

    def test_closed_lane_is_idempotent(self):
        trade = {"side":"LONG","entry_price":100.0,"initial_quantity":5.0,"initial_notional":500.0,"entry_fee_total":0.375}
        lane = {
            "policy_id":"PP-DECISION-V1","status":"CLOSED","remaining_quantity":0.0,
            "realized_gross":6.0,"realized_net":5.0,"allocated_entry_fee":0.375,"exit_fees":0.5,
            "policy_peak_pnl":8.0,"policy_peak_at_ms":1_000_000,"profit_floor":3.2,
            "action_count":2,"trigger_count":2,"closed_at_ms":1_000_000,"exit_price":101.0,
            "close_reason":"PP_DECISION_V1_UNIFIED_GATE",
        }
        updated, event = _evaluate_lane(
            trade=trade, lane=lane,
            feature={"candle_close_ms":1_060_000,"close":90.0,"side_ret3":-5.0,"taker_strength":-0.5,"micro_against":True,"oi_change":1.0,"rv15":1.0},
        )
        self.assertEqual(updated["status"], "CLOSED")
        self.assertEqual(updated["action_count"], 2)
        self.assertEqual(updated["remaining_quantity"], 0.0)
        self.assertEqual(event["action"], "HOLD")

    def test_deterministic_state_space_sweep(self):
        peak_rois = [0.0, 0.49, 0.50, 0.75, 0.9999, 1.0, 1.58, 2.0, 5.0, 10.0]
        givebacks = [0.0, 0.2499, 0.25, 0.2999, 0.30, 0.3499, 0.35, 0.4999, 0.50, 0.5999, 0.60, 0.9999, 1.0, 1.25]
        actions = {"HOLD", "REDUCE", "CLOSE"}
        cases = 0
        for peak_roi in peak_rois:
            for giveback in givebacks:
                for danger in range(7):
                    for status in ("OPEN", "REDUCED"):
                        action, meta = self._decision(peak_roi, giveback, danger, status=status)
                        cases += 1
                        self.assertIn(action, actions)
                        self.assertIn(meta["zone"], {"SUB1", "GE1"})
                        self.assertGreaterEqual(meta["giveback_ratio"], 0.0)
                        self.assertEqual(meta["danger_score"], danger)
                        if peak_roi >= 1.0 and giveback >= 0.60:
                            self.assertEqual(action, "CLOSE")
                        if 0.50 <= peak_roi < 1.0 and giveback >= 1.0:
                            self.assertEqual(action, "CLOSE")
                        if status == "REDUCED":
                            self.assertNotEqual(action, "REDUCE")
        self.assertEqual(cases, 1960)

    def test_action_severity_never_decreases_with_more_danger(self):
        severity = {"HOLD": 0, "REDUCE": 1, "CLOSE": 2}
        for peak_roi, giveback in ((0.80, 0.30), (0.80, 0.50), (1.58, 0.25), (1.58, 0.35), (1.58, 0.50)):
            prior = -1
            for danger in range(7):
                action, _ = self._decision(peak_roi, giveback, danger, status="OPEN")
                current = severity[action]
                self.assertGreaterEqual(current, prior, msg=(peak_roi, giveback, danger, action))
                prior = current

    def test_extreme_negative_current_after_profitable_peak_closes(self):
        action, meta = _pp_decision_unified(
            self.policy, peak_roi=1.58, economic=-20.0, peak=7.9,
            evidence={"danger_score":0}, status="OPEN",
        )
        self.assertEqual(meta["zone"], "GE1")
        self.assertEqual(meta["gate"], "HARD_CLOSE")
        self.assertEqual(action, "CLOSE")


if __name__ == "__main__":
    unittest.main()
