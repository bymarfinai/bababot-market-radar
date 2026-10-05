from __future__ import annotations

import os
import tempfile
import unittest

import market_radar.parallel_protection_shadow as ps
import market_radar.parallel_protection_shadow_ui as ui


class ParallelProtectionShadowPS25Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "ps25.sqlite3")
        ps._READY.clear()
        self.parent = ps.create_shadow_parent(
            source_position_id="PAPER:UI-1",
            signal_id="UI-1",
            symbol="SOLUSDT",
            side="LONG",
            opened_at_ms=1_800_000_000_000,
            entry_price=100.0,
            quantity=2.0,
            path=self.db,
        )
        ps.fanout_shadow_event(
            parent_id=self.parent["parent_id"],
            source_event_id="E1",
            event_time_ms=1_800_000_000_100,
            event_type="AGG_TRADE",
            market_price=101.0,
            payload={"qty": 10},
            path=self.db,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_contract_freezes_branch_order_and_labels(self):
        c = ui.contract_definition()
        self.assertEqual(c["contract_version"], "ps2.5-v1-shadow-ui-contract")
        self.assertEqual(c["baseline_branch_key"], "V42_BASELINE")
        self.assertEqual(c["branch_order"], list(ps.BRANCH_KEYS))
        self.assertEqual(
            [b["short_label"] for b in c["branches"]],
            ["V4.2", "V4.3", "BE0.25", "BE0.18"],
        )
        self.assertEqual(c["execution_authority"], "NONE")

    def test_snapshot_has_one_parent_four_ordered_branches(self):
        out = ui.protection_shadow_snapshot(path=self.db)
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["comparison_eligible_count"], 1)
        p = out["positions"][0]
        self.assertEqual(p["parent"]["symbol"], "SOLUSDT")
        self.assertEqual(p["parent"]["side"], "LONG")
        self.assertEqual(
            [b["branch_key"] for b in p["branches"]],
            list(ps.BRANCH_KEYS),
        )
        self.assertEqual(len(p["branches"]), 4)

    def test_market_observation_is_separate_from_protector_performance(self):
        p = ui.protection_shadow_snapshot(path=self.db)["positions"][0]
        self.assertAlmostEqual(p["market"]["current_price"], 101.0)
        self.assertAlmostEqual(p["market"]["gross_move_pct"], 1.0)
        self.assertAlmostEqual(p["market"]["gross_mark_pnl_usdt"], 2.0)
        self.assertIn("not protector performance", p["market"]["note"])
        for branch in p["branches"]:
            self.assertFalse(branch["performance"]["available"])
            self.assertIsNone(branch["performance"]["current_pnl_usdt"])
            self.assertIsNone(branch["settlement"]["close_reason"])
        self.assertFalse(p["comparison"]["performance_ready"])
        self.assertIsNone(p["comparison"]["current_best_branch_key"])

    def test_protector_configs_match_frozen_research_contract(self):
        p = ui.protection_shadow_snapshot(path=self.db)["positions"][0]
        by_key = {b["branch_key"]: b for b in p["branches"]}
        self.assertIsNone(
            by_key["V42_BASELINE"]["protector_config"]["no_action_be_arm_pct"]
        )
        self.assertEqual(
            by_key["V43_LS"]["protector_config"]["reduce25_logic"],
            "V4.3_LS",
        )
        self.assertEqual(
            by_key["BE025_CONSERVATIVE"]["protector_config"]["no_action_be_arm_pct"],
            0.25,
        )
        self.assertEqual(
            by_key["BE018_AGGRESSIVE"]["protector_config"]["no_action_be_arm_pct"],
            0.18,
        )
        self.assertEqual(
            {b["protector_config"]["runner_logic"] for b in p["branches"]},
            {"V4.2"},
        )

    def test_branch_state_reserved_fields_flow_into_stable_ui_shape(self):
        values = {
            "V42_BASELINE": -1.0,
            "V43_LS": -0.5,
            "BE025_CONSERVATIVE": 0.1,
            "BE018_AGGRESSIVE": 0.4,
        }
        for key, pnl in values.items():
            ps.update_shadow_branch_state(
                parent_id=self.parent["parent_id"],
                branch_key=key,
                current_state="MONITORING",
                state={
                    "lane": "NO_ACTION",
                    "action": "HOLD",
                    "reason": "unit_test",
                    "current_pnl_usdt": pnl,
                    "current_pnl_pct": pnl / 2.0,
                },
                path=self.db,
            )
        p = ui.protection_shadow_snapshot(path=self.db)["positions"][0]
        self.assertTrue(p["comparison"]["performance_ready"])
        self.assertEqual(
            p["comparison"]["current_best_branch_key"],
            "BE018_AGGRESSIVE",
        )
        self.assertAlmostEqual(
            p["comparison"]["current_best_delta_vs_v42_usdt"],
            1.4,
        )
        by_key = {b["branch_key"]: b for b in p["branches"]}
        self.assertEqual(by_key["BE018_AGGRESSIVE"]["decision"]["lane"], "NO_ACTION")
        self.assertTrue(by_key["BE018_AGGRESSIVE"]["performance"]["available"])
        self.assertAlmostEqual(
            by_key["BE018_AGGRESSIVE"]["performance"]["delta_vs_v42_usdt"],
            1.4,
        )
        self.assertAlmostEqual(
            by_key["V43_LS"]["performance"]["delta_vs_v42_usdt"],
            0.5,
        )

    def test_parity_failure_is_exposed_to_ui_and_disables_comparison(self):
        with ps._local_sqlite_connect(self.db) as conn:
            conn.execute(
                """delete from protection_shadow_branch_events
                   where parent_id=? and branch_key='V43_LS' and event_seq=1""",
                (self.parent["parent_id"],),
            )
        out = ui.protection_shadow_snapshot(path=self.db)
        p = out["positions"][0]
        self.assertEqual(p["parity"]["status"], "PARITY_ERROR")
        self.assertFalse(p["parity"]["comparison_eligible"])
        self.assertEqual(out["comparison_ineligible_count"], 1)

    def test_filters_are_normalized_and_applied(self):
        other = ps.create_shadow_parent(
            source_position_id="PAPER:UI-2",
            signal_id="UI-2",
            symbol="BTCUSDT",
            side="SHORT",
            opened_at_ms=1_800_000_001_000,
            entry_price=60_000.0,
            quantity=0.01,
            path=self.db,
        )
        ps.fanout_shadow_event(
            parent_id=other["parent_id"],
            source_event_id="B1",
            event_time_ms=1_800_000_001_100,
            event_type="AGG_TRADE",
            market_price=59_900.0,
            path=self.db,
        )
        out = ui.protection_shadow_snapshot(
            symbol="btcusdt",
            side="short",
            status="open",
            path=self.db,
        )
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["positions"][0]["parent"]["symbol"], "BTCUSDT")
        self.assertEqual(out["filters"]["side"], "SHORT")

    def test_short_market_gross_move_is_directionally_correct(self):
        other = ps.create_shadow_parent(
            source_position_id="PAPER:UI-SHORT",
            signal_id="UI-SHORT",
            symbol="BTCUSDT",
            side="SHORT",
            opened_at_ms=1_800_000_002_000,
            entry_price=100.0,
            quantity=3.0,
            path=self.db,
        )
        ps.fanout_shadow_event(
            parent_id=other["parent_id"],
            source_event_id="S1",
            event_time_ms=1_800_000_002_100,
            event_type="AGG_TRADE",
            market_price=99.0,
            path=self.db,
        )
        out = ui.protection_shadow_snapshot(symbol="BTCUSDT", path=self.db)
        p = out["positions"][0]
        self.assertAlmostEqual(p["market"]["gross_move_pct"], 1.0)
        self.assertAlmostEqual(p["market"]["gross_mark_pnl_usdt"], 3.0)

    def test_invalid_filter_is_rejected(self):
        with self.assertRaises(ValueError):
            ui.protection_shadow_snapshot(side="BUY", path=self.db)
        with self.assertRaises(ValueError):
            ui.protection_shadow_snapshot(status="CLOSED", path=self.db)

    def test_authority_is_none_at_all_ui_levels(self):
        out = ui.protection_shadow_snapshot(path=self.db)
        self.assertEqual(out["execution_authority"], "NONE")
        for p in out["positions"]:
            for b in p["branches"]:
                self.assertEqual(b["execution_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
