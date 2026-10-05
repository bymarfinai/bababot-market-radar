from __future__ import annotations

import json
import os
import tempfile
import unittest

import market_radar.parallel_protection_shadow as ps
import market_radar.parallel_protection_shadow_adapters as pa
import market_radar.parallel_protection_shadow_settlement as st
import market_radar.parallel_protection_shadow_ui as ui


class ParallelProtectionShadowPS4Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "ps4.sqlite3")
        ps._READY.clear()
        st._READY.clear()
        self.parent = ps.create_shadow_parent(
            source_position_id="PAPER:PS4-LONG",
            signal_id="PS4-LONG",
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

    def fan(self, event_type, price, payload=None, *, settle=True):
        self.seq += 1
        result = ps.fanout_shadow_event(
            parent_id=self.parent["parent_id"],
            source_event_id=f"E{self.seq}",
            event_time_ms=1_800_000_000_000 + self.seq * 100,
            event_type=event_type,
            market_price=price,
            payload=payload or {},
            path=self.db,
        )
        self.assertEqual(result["status"], "FANOUT_OK")
        if settle:
            out = st.process_shadow_event_with_settlement(
                self.parent["parent_id"],
                self.seq,
                path=self.db,
            )
            self.assertEqual(out["status"], "COMPLETE")
            return out
        out = pa.process_shadow_event(
            parent_id=self.parent["parent_id"],
            event_seq=self.seq,
            path=self.db,
        )
        self.assertIn(out["status"], {"ADAPTER_OK", "ALREADY_PROCESSED"})
        return out

    def branches(self):
        return {
            row["branch_key"]: row
            for row in ps.list_shadow_branches(
                self.parent["parent_id"],
                path=self.db,
            )
        }

    def state(self, key):
        return json.loads(self.branches()[key]["state_json"])

    def settlements(self, key=None):
        return st.list_shadow_settlements(
            self.parent["parent_id"],
            branch_key=key,
            path=self.db,
        )

    def test_contract_is_virtual_and_source_position_safe(self):
        c = st.settlement_contract()
        self.assertEqual(c["settlement_version"], "ps4-v1-shadow-settlement")
        self.assertEqual(c["execution_authority"], "NONE")
        self.assertTrue(c["branch_isolation"])
        self.assertFalse(c["source_position_mutation"])
        self.assertFalse(c["parent_auto_close"])

    def test_be018_close_settles_only_be018_branch(self):
        self.fan("AGG_TRADE", 100.20)
        self.fan("AGG_TRADE", 100.00)
        rows = self.branches()
        self.assertEqual(rows["BE018_AGGRESSIVE"]["status"], "CLOSED")
        self.assertAlmostEqual(rows["BE018_AGGRESSIVE"]["remaining_quantity"], 0.0)
        self.assertEqual(rows["V42_BASELINE"]["status"], "OPEN")
        self.assertEqual(rows["V43_LS"]["status"], "OPEN")
        self.assertEqual(rows["BE025_CONSERVATIVE"]["status"], "OPEN")
        bsettle = self.settlements("BE018_AGGRESSIVE")
        fills = [r for r in bsettle if r["status"] == "VIRTUAL_FILLED"]
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["action"], "CLOSE")
        self.assertEqual(fills[0]["intent_source"], "PROTECTION")
        parent = ps.get_shadow_parent("PAPER:PS4-LONG", path=self.db)
        self.assertEqual(parent["status"], "OPEN")
        self.assertEqual(parent["execution_authority"], "NONE")

    def test_v42_reduce25_settles_partial_and_keeps_branch_open(self):
        self.fan("PROTECTION_SAMPLE_5S", 100.60)
        self.fan("PROTECTION_SAMPLE_5S", 100.30)
        self.fan("PROTECTION_SAMPLE_5S", 100.30)
        self.fan("PROTECTION_SAMPLE_5S", 100.30)
        row = self.branches()["V42_BASELINE"]
        self.assertEqual(row["status"], "OPEN")
        self.assertEqual(row["current_state"], "REDUCED_MONITORING")
        self.assertAlmostEqual(row["remaining_quantity"], 3.75)
        fills = [
            r for r in self.settlements("V42_BASELINE")
            if r["status"] == "VIRTUAL_FILLED"
        ]
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["action"], "REDUCE")
        self.assertAlmostEqual(fills[0]["executed_quantity"], 1.25)
        self.assertAlmostEqual(fills[0]["quantity_after"], 3.75)
        s = self.state("V42_BASELINE")
        self.assertGreater(s["realized_quantity"], 0)
        self.assertNotEqual(s["current_pnl_usdt"], s["realized_pnl_usdt"])

    def test_reduce_then_runner_close_can_settle_from_intent_history(self):
        # Deliberately run PS-3 without PS-4 until the end to prove catch-up.
        for price in (100.60, 100.30, 100.30, 100.30, 101.60, 101.40, 101.40):
            self.fan("PROTECTION_SAMPLE_5S", price, settle=False)

        history = self.state("V42_BASELINE")["intent_history"]
        self.assertEqual(
            [(x["action"], x["event_seq"]) for x in history],
            [("REDUCE", 4), ("CLOSE", 7)],
        )

        out = st.settle_shadow_parent(
            self.parent["parent_id"],
            upto_event_seq=7,
            path=self.db,
        )
        self.assertEqual(out["status"], "SETTLEMENT_OK")
        row = self.branches()["V42_BASELINE"]
        self.assertEqual(row["status"], "CLOSED")
        self.assertAlmostEqual(row["remaining_quantity"], 0.0)
        fills = [
            r for r in self.settlements("V42_BASELINE")
            if r["status"] == "VIRTUAL_FILLED"
        ]
        self.assertEqual([r["action"] for r in fills], ["REDUCE", "CLOSE"])
        self.assertAlmostEqual(fills[0]["executed_quantity"], 1.25)
        self.assertAlmostEqual(fills[1]["executed_quantity"], 3.75)
        self.assertAlmostEqual(
            sum(float(r["executed_quantity"]) for r in fills),
            5.0,
        )

    def test_non_action_event_skips_settlement_scan_after_partial_reduce_but_updates_mark(self):
        for price in (100.60, 100.30, 100.30, 100.30):
            self.fan("PROTECTION_SAMPLE_5S", price)
        before = self.state("V42_BASELINE")
        self.assertAlmostEqual(
            self.branches()["V42_BASELINE"]["remaining_quantity"],
            3.75,
        )
        out = self.fan("PROTECTION_SAMPLE_5S", 100.40)
        self.assertEqual(out["settlement"]["status"], "NO_ACTION_REQUIRED")
        after = self.state("V42_BASELINE")
        self.assertAlmostEqual(
            self.branches()["V42_BASELINE"]["remaining_quantity"],
            3.75,
        )
        self.assertNotEqual(before["current_pnl_usdt"], after["current_pnl_usdt"])
        self.assertEqual(
            len(self.settlements("V42_BASELINE")),
            1,
        )

    def test_settlement_is_idempotent(self):
        self.fan("AGG_TRADE", 100.20)
        self.fan("AGG_TRADE", 100.00)
        before = self.settlements("BE018_AGGRESSIVE")
        state_before = self.state("BE018_AGGRESSIVE")
        again = st.settle_shadow_parent(
            self.parent["parent_id"],
            upto_event_seq=2,
            path=self.db,
        )
        self.assertEqual(again["status"], "SETTLEMENT_OK")
        after = self.settlements("BE018_AGGRESSIVE")
        state_after = self.state("BE018_AGGRESSIVE")
        self.assertEqual(len(before), len(after))
        self.assertAlmostEqual(
            state_before["realized_pnl_usdt"],
            state_after["realized_pnl_usdt"],
        )
        self.assertAlmostEqual(
            self.branches()["BE018_AGGRESSIVE"]["remaining_quantity"],
            0.0,
        )

    def test_closed_branch_remains_passive_event_consumer(self):
        self.fan("AGG_TRADE", 100.20)
        self.fan("AGG_TRADE", 100.00)
        closed_pnl = self.state("BE018_AGGRESSIVE")["realized_pnl_usdt"]
        self.fan("AGG_TRADE", 99.00)
        row = self.branches()["BE018_AGGRESSIVE"]
        s = self.state("BE018_AGGRESSIVE")
        self.assertEqual(row["status"], "CLOSED")
        self.assertEqual(row["current_state"], "CLOSED")
        self.assertEqual(s["processed_event_seq"], 3)
        self.assertAlmostEqual(s["realized_pnl_usdt"], closed_pnl)
        self.assertAlmostEqual(s["current_pnl_usdt"], closed_pnl)
        audit = ps.audit_shadow_parity(self.parent["parent_id"], path=self.db)
        self.assertTrue(audit["comparison_eligible"])

    def test_source_close_finishes_all_remaining_no_action_branches(self):
        self.fan("AGG_TRADE", 100.10)
        self.fan(
            "SOURCE_POSITION_CLOSE",
            99.50,
            {"reason": "source_health_close"},
        )
        rows = self.branches()
        self.assertEqual({r["status"] for r in rows.values()}, {"CLOSED"})
        for key in ps.BRANCH_KEYS:
            self.assertAlmostEqual(rows[key]["remaining_quantity"], 0.0)
            s = self.state(key)
            self.assertEqual(s["close_reason"], "source_health_close")
            self.assertEqual(s["close_event_seq"], 2)
        parent = ps.get_shadow_parent("PAPER:PS4-LONG", path=self.db)
        self.assertEqual(parent["status"], "OPEN")

    def test_source_reduce_mirrors_before_protection_divergence(self):
        self.fan(
            "SOURCE_POSITION_REDUCE",
            100.20,
            {"fraction": 0.20, "reason": "base_reduce"},
        )
        rows = self.branches()
        for key in ps.BRANCH_KEYS:
            self.assertAlmostEqual(rows[key]["remaining_quantity"], 4.0)
            fills = [
                r for r in self.settlements(key)
                if r["status"] == "VIRTUAL_FILLED"
            ]
            self.assertEqual(len(fills), 1)
            self.assertEqual(fills[0]["intent_source"], "SOURCE_LIFECYCLE")
            self.assertAlmostEqual(fills[0]["executed_quantity"], 1.0)

    def test_source_reduce_after_protection_divergence_is_skipped(self):
        for price in (100.60, 100.30, 100.30, 100.30):
            self.fan("PROTECTION_SAMPLE_5S", price)
        self.assertAlmostEqual(
            self.branches()["V42_BASELINE"]["remaining_quantity"],
            3.75,
        )
        self.fan(
            "SOURCE_POSITION_REDUCE",
            100.25,
            {"fraction": 0.20, "reason": "late_base_reduce"},
        )
        row = self.branches()["V42_BASELINE"]
        self.assertAlmostEqual(row["remaining_quantity"], 3.75)
        source_rows = [
            r for r in self.settlements("V42_BASELINE")
            if r["intent_source"] == "SOURCE_LIFECYCLE"
        ]
        self.assertEqual(len(source_rows), 1)
        self.assertEqual(source_rows[0]["status"], "VIRTUAL_SKIPPED")
        self.assertAlmostEqual(source_rows[0]["executed_quantity"], 0.0)

    def test_source_close_still_closes_remainder_after_protection_reduce(self):
        for price in (100.60, 100.30, 100.30, 100.30):
            self.fan("PROTECTION_SAMPLE_5S", price)
        self.assertAlmostEqual(
            self.branches()["V42_BASELINE"]["remaining_quantity"],
            3.75,
        )
        self.fan(
            "SOURCE_POSITION_CLOSE",
            99.80,
            {"reason": "source_final_close"},
        )
        row = self.branches()["V42_BASELINE"]
        self.assertEqual(row["status"], "CLOSED")
        self.assertAlmostEqual(row["remaining_quantity"], 0.0)
        fills = [
            r for r in self.settlements("V42_BASELINE")
            if r["status"] == "VIRTUAL_FILLED"
        ]
        self.assertEqual([r["action"] for r in fills], ["REDUCE", "CLOSE"])
        self.assertEqual(fills[-1]["intent_source"], "SOURCE_LIFECYCLE")

    def test_fee_accounting_allocates_entry_fee_once_across_full_close(self):
        self.fan("AGG_TRADE", 100.20)
        self.fan("AGG_TRADE", 100.00)
        fill = [
            r for r in self.settlements("BE018_AGGRESSIVE")
            if r["status"] == "VIRTUAL_FILLED"
        ][0]
        # Frozen research semantics treat metadata slippage_bps=0 as
        # fallback 2 bps: LONG fill=99.98. Gross=-0.10, entry fee=-0.05,
        # exit fee=-0.04999 => -0.19999 total.
        self.assertAlmostEqual(fill["realized_delta_usdt"], -0.19999, places=9)
        self.assertAlmostEqual(fill["entry_fee_allocated_usdt"], 0.05, places=9)
        self.assertAlmostEqual(fill["exit_fee_usdt"], 0.04999, places=9)
        self.assertAlmostEqual(
            self.state("BE018_AGGRESSIVE")["realized_pnl_usdt"],
            -0.19999,
            places=9,
        )

    def test_ui_open_partial_uses_total_current_pnl_not_partial_realized(self):
        for price in (100.60, 100.30, 100.30, 100.30):
            self.fan("PROTECTION_SAMPLE_5S", price)
        snap = ui.protection_shadow_snapshot(path=self.db)
        p = snap["positions"][0]
        by_key = {b["branch_key"]: b for b in p["branches"]}
        v42 = by_key["V42_BASELINE"]
        self.assertEqual(v42["status"], "OPEN")
        self.assertIsNotNone(v42["performance"]["realized_pnl_usdt"])
        self.assertIsNotNone(v42["performance"]["current_pnl_usdt"])
        # Delta is derived from effective open current PnL, not partial realized.
        self.assertAlmostEqual(
            v42["performance"]["delta_vs_v42_usdt"],
            0.0,
            places=9,
        )

    def test_parity_error_blocks_settlement(self):
        self.fan("AGG_TRADE", 100.20, settle=False)
        with ps._local_sqlite_connect(self.db) as conn:
            conn.execute(
                """delete from protection_shadow_branch_events
                   where parent_id=? and branch_key='V43_LS' and event_seq=1""",
                (self.parent["parent_id"],),
            )
        out = st.settle_shadow_parent(
            self.parent["parent_id"],
            upto_event_seq=1,
            path=self.db,
        )
        self.assertEqual(out["status"], "SETTLEMENT_BLOCKED")
        self.assertEqual(out["reason"], "PARITY_ERROR")
        self.assertEqual(self.settlements(), [])

    def test_pending_orchestrator_catches_up_decision_and_settlement(self):
        for i, (typ, price) in enumerate(
            [
                ("AGG_TRADE", 100.20),
                ("AGG_TRADE", 100.00),
                ("AGG_TRADE", 99.90),
            ],
            start=1,
        ):
            result = ps.fanout_shadow_event(
                parent_id=self.parent["parent_id"],
                source_event_id=f"P{i}",
                event_time_ms=1_800_000_000_000 + i * 100,
                event_type=typ,
                market_price=price,
                path=self.db,
            )
            self.assertEqual(result["status"], "FANOUT_OK")
        out = st.process_pending_with_settlement(
            self.parent["parent_id"],
            path=self.db,
        )
        self.assertEqual(out["status"], "COMPLETE")
        self.assertEqual(out["canonical_event_count"], 3)
        self.assertEqual(out["adapter_processed_n"], 3)
        self.assertEqual(
            self.branches()["BE018_AGGRESSIVE"]["status"],
            "CLOSED",
        )
        for key in ps.BRANCH_KEYS:
            self.assertEqual(self.state(key)["processed_event_seq"], 3)

    def test_short_close_math_is_directionally_correct(self):
        short = ps.create_shadow_parent(
            source_position_id="PAPER:PS4-SHORT",
            signal_id="PS4-SHORT",
            symbol="BTCUSDT",
            side="SHORT",
            opened_at_ms=1_800_000_100_000,
            entry_price=100.0,
            quantity=5.0,
            metadata={
                "fee_rate": 0.0001,
                "slippage_bps": 0.0,
                "entry_fee_total": 0.05,
            },
            path=self.db,
        )
        for seq, price in ((1, 99.80), (2, 100.00)):
            ps.fanout_shadow_event(
                parent_id=short["parent_id"],
                source_event_id=f"S{seq}",
                event_time_ms=1_800_000_100_000 + seq * 100,
                event_type="AGG_TRADE",
                market_price=price,
                path=self.db,
            )
            out = st.process_shadow_event_with_settlement(
                short["parent_id"],
                seq,
                path=self.db,
            )
            self.assertEqual(out["status"], "COMPLETE")
        rows = {
            r["branch_key"]: r
            for r in ps.list_shadow_branches(short["parent_id"], path=self.db)
        }
        self.assertEqual(rows["BE018_AGGRESSIVE"]["status"], "CLOSED")
        state = json.loads(rows["BE018_AGGRESSIVE"]["state_json"])
        self.assertLess(state["realized_pnl_usdt"], 0.0)

    def test_execution_authority_never_changes(self):
        self.fan("AGG_TRADE", 100.20)
        self.fan("AGG_TRADE", 100.00)
        for row in self.branches().values():
            self.assertEqual(row["execution_authority"], "NONE")
        parent = ps.get_shadow_parent("PAPER:PS4-LONG", path=self.db)
        self.assertEqual(parent["execution_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
