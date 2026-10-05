from __future__ import annotations

import json
import os
import tempfile
import unittest

import market_radar.parallel_protection_shadow as ps
import market_radar.parallel_protection_shadow_adapters as pa
import market_radar.parallel_protection_shadow_ui as ui


class ParallelProtectionShadowPS3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "ps3.sqlite3")
        ps._READY.clear()
        self.parent = ps.create_shadow_parent(
            source_position_id="PAPER:PS3-LONG",
            signal_id="PS3-LONG",
            symbol="SOLUSDT",
            side="LONG",
            opened_at_ms=1_800_000_000_000,
            entry_price=100.0,
            quantity=5.0,
            metadata={
                "fee_rate": 0.0001,
                "slippage_bps": 0.0,
                "entry_fee_total": 0.05,
            },
            path=self.db,
        )
        self.seq = 0

    def tearDown(self):
        self.tmp.cleanup()

    def event(self, event_type: str, price: float, *, dt: int = 100, event_id=None):
        self.seq += 1
        eid = event_id or f"E{self.seq}"
        fan = ps.fanout_shadow_event(
            parent_id=self.parent["parent_id"],
            source_event_id=eid,
            event_time_ms=1_800_000_000_000 + self.seq * dt,
            event_type=event_type,
            market_price=price,
            payload={"test_seq": self.seq},
            path=self.db,
        )
        self.assertEqual(fan["status"], "FANOUT_OK")
        out = pa.process_shadow_event(
            parent_id=self.parent["parent_id"],
            event_seq=self.seq,
            path=self.db,
        )
        self.assertEqual(out["status"], "ADAPTER_OK")
        return out

    def branches(self):
        return {
            r["branch_key"]: r
            for r in ps.list_shadow_branches(self.parent["parent_id"], path=self.db)
        }

    def state(self, key):
        return json.loads(self.branches()[key]["state_json"])

    def test_contract_matches_frozen_research_settings(self):
        c = pa.adapter_contract()
        self.assertEqual(c["adapter_version"], "ps3-v1-protection-adapters")
        self.assertEqual(c["execution_authority"], "NONE")
        self.assertEqual(c["v42"]["small_arm_pct"], 0.50)
        self.assertEqual(c["v42"]["small_retain"], 0.60)
        self.assertEqual(c["v42"]["small_confirm"], 3)
        self.assertEqual(c["v42"]["reduce_fraction"], 0.25)
        self.assertEqual(c["v43_ls"]["long_retain"], 0.97)
        self.assertEqual(c["v43_ls"]["short_retain"], 0.75)
        self.assertEqual(c["v43_ls"]["small_confirm"], 1)
        self.assertEqual(c["be018"]["gross_arm_pct"], 0.18)
        self.assertEqual(c["be025"]["gross_arm_pct"], 0.25)
        self.assertEqual(c["v42"]["runner_qualify_pct"], 1.50)
        self.assertEqual(c["v42"]["runner_retain"], 0.90)
        self.assertEqual(c["v42"]["runner_confirm"], 2)

    def test_raw_event_drives_be_but_not_v42_v43_logic(self):
        out = self.event("AGG_TRADE", 100.20)
        self.assertEqual(out["branches"]["BE018_AGGRESSIVE"]["current_state"], "BE_ARMED")
        self.assertFalse(out["branches"]["BE025_CONSERVATIVE"]["be_armed"])
        self.assertEqual(self.state("V42_BASELINE")["logic_event_count"], 0)
        self.assertEqual(self.state("V43_LS")["logic_event_count"], 0)
        self.assertEqual(self.state("BE018_AGGRESSIVE")["logic_event_count"], 1)

    def test_be018_arms_then_emits_close_only_on_later_raw_cross(self):
        first = self.event("AGG_TRADE", 100.20)
        self.assertEqual(first["branches"]["BE018_AGGRESSIVE"]["action"], "HOLD")
        second = self.event("AGG_TRADE", 100.00)
        b = second["branches"]["BE018_AGGRESSIVE"]
        self.assertEqual(b["action"], "CLOSE")
        self.assertTrue(b["decision_terminal"])
        s = self.state("BE018_AGGRESSIVE")
        self.assertEqual(s["virtual_intent"]["action"], "CLOSE")
        self.assertEqual(s["virtual_intent"]["event_seq"], 2)
        self.assertEqual(s["virtual_intent"]["settlement_authority"], "PS4_NOT_AVAILABLE")

    def test_be025_does_not_arm_at_020_but_arms_at_026(self):
        self.event("AGG_TRADE", 100.20)
        self.assertFalse(self.state("BE025_CONSERVATIVE")["be_armed"])
        self.event("AGG_TRADE", 100.26)
        self.assertTrue(self.state("BE025_CONSERVATIVE")["be_armed"])

    def test_be_requires_executable_net_nonnegative_not_only_gross_touch(self):
        high_cost = ps.create_shadow_parent(
            source_position_id="PAPER:HIGH-COST",
            signal_id="HIGH-COST",
            symbol="ETHUSDT",
            side="LONG",
            opened_at_ms=1_800_000_010_000,
            entry_price=100.0,
            quantity=5.0,
            metadata={
                "fee_rate": 0.001,
                "slippage_bps": 5.0,
                "entry_fee_total": 0.5,
            },
            path=self.db,
        )
        ps.fanout_shadow_event(
            parent_id=high_cost["parent_id"],
            source_event_id="H1",
            event_time_ms=1_800_000_010_100,
            event_type="AGG_TRADE",
            market_price=100.18,
            path=self.db,
        )
        pa.process_shadow_event(parent_id=high_cost["parent_id"], event_seq=1, path=self.db)
        rows = {r["branch_key"]: r for r in ps.list_shadow_branches(high_cost["parent_id"], path=self.db)}
        s = json.loads(rows["BE018_AGGRESSIVE"]["state_json"])
        self.assertTrue(s["be_gross_touched"])
        self.assertFalse(s["be_armed"])
        self.assertLess(s["executable_net_pct"], 0)

    def test_v43_long_full_close_uses_retain97_confirm1(self):
        self.event("PROTECTION_SAMPLE_5S", 100.60)
        out = self.event("PROTECTION_SAMPLE_5S", 100.58)
        b = out["branches"]["V43_LS"]
        self.assertEqual(b["action"], "CLOSE")
        self.assertTrue(b["decision_terminal"])
        s = self.state("V43_LS")
        self.assertEqual(s["reason"], "v43_ls_long_retain97_full_close")
        self.assertEqual(s["virtual_intent"]["fraction"], 1.0)

    def test_v42_reduce_requires_three_confirmations_and_is_nonterminal(self):
        self.event("PROTECTION_SAMPLE_5S", 100.60)
        a = self.event("PROTECTION_SAMPLE_5S", 100.30)
        b = self.event("PROTECTION_SAMPLE_5S", 100.30)
        c = self.event("PROTECTION_SAMPLE_5S", 100.30)
        self.assertEqual(a["branches"]["V42_BASELINE"]["action"], "HOLD")
        self.assertEqual(b["branches"]["V42_BASELINE"]["action"], "HOLD")
        self.assertEqual(c["branches"]["V42_BASELINE"]["action"], "REDUCE")
        self.assertFalse(c["branches"]["V42_BASELINE"]["decision_terminal"])
        s = self.state("V42_BASELINE")
        self.assertTrue(s["reduce_triggered"])
        self.assertEqual(s["virtual_intent"]["fraction"], 0.25)
        self.assertEqual(s["virtual_intent"]["settlement_authority"], "PS4_NOT_AVAILABLE")

    def test_runner_takes_precedence_and_closes_after_two_retain90_confirms(self):
        self.event("PROTECTION_SAMPLE_5S", 101.60)
        a = self.event("PROTECTION_SAMPLE_5S", 101.40)
        b = self.event("PROTECTION_SAMPLE_5S", 101.40)
        for key in ps.BRANCH_KEYS:
            self.assertTrue(a["branches"][key]["runner_qualified"])
            self.assertEqual(a["branches"][key]["action"], "HOLD")
            self.assertEqual(b["branches"][key]["action"], "CLOSE")
            self.assertTrue(b["branches"][key]["decision_terminal"])
            self.assertEqual(self.state(key)["lane"], "V4.2_RUNNER")

    def test_be_is_superseded_by_observed_active_protector_then_v43_controls(self):
        self.event("AGG_TRADE", 100.20)
        self.assertTrue(self.state("BE018_AGGRESSIVE")["be_armed"])
        self.event("PROTECTION_SAMPLE_5S", 100.55)
        s = self.state("BE018_AGGRESSIVE")
        self.assertTrue(s["be_superseded"])
        self.assertFalse(s["be_armed"])
        raw = self.event("AGG_TRADE", 100.00)
        self.assertNotEqual(raw["branches"]["BE018_AGGRESSIVE"]["action"], "CLOSE")
        sample = self.event("PROTECTION_SAMPLE_5S", 100.53)
        self.assertEqual(sample["branches"]["BE018_AGGRESSIVE"]["action"], "CLOSE")
        self.assertEqual(
            self.state("BE018_AGGRESSIVE")["reason"],
            "v43_ls_long_retain97_full_close",
        )

    def test_terminal_close_signal_freezes_decision_performance_until_ps4(self):
        self.event("AGG_TRADE", 100.20)
        self.event("AGG_TRADE", 100.00)
        before = self.state("BE018_AGGRESSIVE")
        frozen_pnl = before["current_pnl_usdt"]
        self.event("AGG_TRADE", 99.00)
        after = self.state("BE018_AGGRESSIVE")
        self.assertEqual(after["current_pnl_usdt"], frozen_pnl)
        self.assertEqual(after["virtual_intent"]["event_seq"], 2)
        self.assertTrue(after["decision_terminal"])

    def test_ps3_does_not_settle_status_or_quantity(self):
        self.event("PROTECTION_SAMPLE_5S", 100.60)
        self.event("PROTECTION_SAMPLE_5S", 100.30)
        self.event("PROTECTION_SAMPLE_5S", 100.30)
        self.event("PROTECTION_SAMPLE_5S", 100.30)
        rows = self.branches()
        for row in rows.values():
            self.assertEqual(row["status"], "OPEN")
            self.assertEqual(row["remaining_quantity"], 5.0)
            self.assertEqual(row["execution_authority"], "NONE")
        parent = ps.get_shadow_parent("PAPER:PS3-LONG", path=self.db)
        self.assertEqual(parent["execution_authority"], "NONE")
        self.assertEqual(parent["status"], "OPEN")

    def test_adapter_is_idempotent_for_already_processed_event(self):
        self.event("AGG_TRADE", 100.20)
        again = pa.process_shadow_event(
            parent_id=self.parent["parent_id"],
            event_seq=1,
            path=self.db,
        )
        self.assertEqual(again["status"], "ALREADY_PROCESSED")
        self.assertEqual(again["processed_event_seq"], 1)

    def test_sequence_gap_is_rejected_and_marks_comparison_ineligible(self):
        ps.fanout_shadow_event(
            parent_id=self.parent["parent_id"],
            source_event_id="G1",
            event_time_ms=1_800_000_000_100,
            event_type="AGG_TRADE",
            market_price=100.1,
            path=self.db,
        )
        ps.fanout_shadow_event(
            parent_id=self.parent["parent_id"],
            source_event_id="G2",
            event_time_ms=1_800_000_000_200,
            event_type="AGG_TRADE",
            market_price=100.2,
            path=self.db,
        )
        out = pa.process_shadow_event(
            parent_id=self.parent["parent_id"],
            event_seq=2,
            path=self.db,
        )
        self.assertEqual(out["status"], "ADAPTER_ERROR")
        self.assertEqual(out["reason"], "ADAPTER_SEQUENCE_GAP")
        audit = ps.audit_shadow_parity(self.parent["parent_id"], path=self.db)
        self.assertFalse(audit["comparison_eligible"])
        self.assertIn("ADAPTER_SEQUENCE_GAP", audit["issue_types"])

    def test_process_pending_catches_up_sequentially(self):
        for i, price in enumerate((100.10, 100.20, 100.30), start=1):
            ps.fanout_shadow_event(
                parent_id=self.parent["parent_id"],
                source_event_id=f"P{i}",
                event_time_ms=1_800_000_000_000 + i * 100,
                event_type="AGG_TRADE",
                market_price=price,
                path=self.db,
            )
        out = pa.process_pending_shadow_events(self.parent["parent_id"], path=self.db)
        self.assertEqual(out["status"], "COMPLETE")
        self.assertEqual(out["processed_n"], 3)
        for key in ps.BRANCH_KEYS:
            self.assertEqual(self.state(key)["processed_event_seq"], 3)

    def test_ui_contract_remains_stable_and_populated(self):
        self.event("AGG_TRADE", 100.20)
        snap = ui.protection_shadow_snapshot(path=self.db)
        p = snap["positions"][0]
        self.assertEqual(snap["contract_version"], "ps2.5-v1-shadow-ui-contract")
        self.assertEqual([b["branch_key"] for b in p["branches"]], list(ps.BRANCH_KEYS))
        self.assertTrue(p["comparison"]["performance_ready"])
        by_key = {b["branch_key"]: b for b in p["branches"]}
        self.assertTrue(by_key["BE018_AGGRESSIVE"]["decision"]["be_armed"])
        self.assertEqual(by_key["BE018_AGGRESSIVE"]["decision"]["action"], "HOLD")
        self.assertIsNotNone(by_key["BE018_AGGRESSIVE"]["performance"]["current_pnl_usdt"])
        self.assertEqual(by_key["V42_BASELINE"]["execution_authority"], "NONE")

    def test_short_v43_uses_retain75(self):
        short = ps.create_shadow_parent(
            source_position_id="PAPER:PS3-SHORT",
            signal_id="PS3-SHORT",
            symbol="BTCUSDT",
            side="SHORT",
            opened_at_ms=1_800_000_020_000,
            entry_price=100.0,
            quantity=5.0,
            metadata={"fee_rate": 0.0001, "slippage_bps": 0.0, "entry_fee_total": 0.05},
            path=self.db,
        )
        for i, price in enumerate((99.40, 99.50, 99.60), start=1):
            ps.fanout_shadow_event(
                parent_id=short["parent_id"],
                source_event_id=f"S{i}",
                event_time_ms=1_800_000_020_000 + i * 100,
                event_type="PROTECTION_SAMPLE_5S",
                market_price=price,
                path=self.db,
            )
            out = pa.process_shadow_event(parent_id=short["parent_id"], event_seq=i, path=self.db)
            if i == 2:
                self.assertEqual(out["branches"]["V43_LS"]["action"], "HOLD")
            if i == 3:
                self.assertEqual(out["branches"]["V43_LS"]["action"], "CLOSE")
        rows = {r["branch_key"]: r for r in ps.list_shadow_branches(short["parent_id"], path=self.db)}
        state = json.loads(rows["V43_LS"]["state_json"])
        self.assertEqual(state["reason"], "v43_ls_short_retain75_full_close")


if __name__ == "__main__":
    unittest.main()
