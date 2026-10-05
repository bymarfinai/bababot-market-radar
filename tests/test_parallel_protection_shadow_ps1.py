from __future__ import annotations

import json
import os
import tempfile
import unittest

import market_radar.parallel_protection_shadow as ps


class ParallelProtectionShadowPS1Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "ps1.sqlite3")
        ps._READY.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def create_parent(self, source_position_id: str = "PAPER:SIG-1"):
        return ps.create_shadow_parent(
            source_position_id=source_position_id,
            signal_id="SIG-1",
            symbol="solusdt",
            side="long",
            opened_at_ms=1_800_000_000_000,
            entry_price=150.0,
            quantity=2.0,
            metadata={"source": "unit-test"},
            path=self.db,
        )

    def test_branch_contract_is_exactly_four(self):
        self.assertEqual(
            ps.BRANCH_KEYS,
            (
                "V42_BASELINE",
                "V43_LS",
                "BE025_CONSERVATIVE",
                "BE018_AGGRESSIVE",
            ),
        )
        self.assertTrue(all(x.execution_authority == "NONE" for x in ps.BRANCH_SPECS))

    def test_parent_clones_identical_entry_into_four_isolated_branches(self):
        created = self.create_parent()
        self.assertTrue(created["created"])
        self.assertEqual(created["branch_count"], 4)
        self.assertEqual(created["execution_authority"], "NONE")

        branches = ps.list_shadow_branches(created["parent_id"], path=self.db)
        self.assertEqual([x["branch_key"] for x in branches], list(ps.BRANCH_KEYS))
        self.assertEqual({x["entry_price"] for x in branches}, {150.0})
        self.assertEqual({x["initial_quantity"] for x in branches}, {2.0})
        self.assertEqual({x["remaining_quantity"] for x in branches}, {2.0})
        self.assertEqual({x["opened_at_ms"] for x in branches}, {1_800_000_000_000})
        self.assertEqual({x["execution_authority"] for x in branches}, {"NONE"})
        self.assertEqual({x["current_state"] for x in branches}, {"ENTRY_OPEN"})

    def test_branch_state_update_is_isolated(self):
        created = self.create_parent()
        ps.update_shadow_branch_state(
            parent_id=created["parent_id"],
            branch_key="BE018_AGGRESSIVE",
            current_state="BE_ARMED",
            mfe_pct=0.31,
            mae_pct=-0.12,
            remaining_quantity=1.75,
            state={"be_armed": True, "arm_pct": 0.18},
            path=self.db,
        )
        branches = {
            x["branch_key"]: x
            for x in ps.list_shadow_branches(created["parent_id"], path=self.db)
        }
        target = branches["BE018_AGGRESSIVE"]
        self.assertEqual(target["current_state"], "BE_ARMED")
        self.assertAlmostEqual(target["mfe_pct"], 0.31)
        self.assertAlmostEqual(target["remaining_quantity"], 1.75)
        self.assertEqual(json.loads(target["state_json"])["arm_pct"], 0.18)

        for key in ("V42_BASELINE", "V43_LS", "BE025_CONSERVATIVE"):
            self.assertEqual(branches[key]["current_state"], "ENTRY_OPEN")
            self.assertEqual(json.loads(branches[key]["state_json"]), {})
            self.assertEqual(branches[key]["remaining_quantity"], 2.0)

    def test_create_is_idempotent_for_same_entry_identity(self):
        first = self.create_parent()
        second = self.create_parent()
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["parent_id"], second["parent_id"])
        self.assertEqual(
            len(ps.list_shadow_branches(first["parent_id"], path=self.db)),
            4,
        )
        summary = ps.shadow_core_summary(path=self.db)
        self.assertEqual(summary["parents"], 1)
        self.assertEqual(summary["branches"], 4)
        self.assertEqual(summary["non_none_authority"], 0)

    def test_conflicting_duplicate_source_position_is_rejected(self):
        self.create_parent()
        with self.assertRaisesRegex(ValueError, "identity conflict"):
            ps.create_shadow_parent(
                source_position_id="PAPER:SIG-1",
                signal_id="SIG-1",
                symbol="SOLUSDT",
                side="LONG",
                opened_at_ms=1_800_000_000_000,
                entry_price=151.0,
                quantity=2.0,
                path=self.db,
            )

    def test_invalid_entry_identity_is_rejected_before_persistence(self):
        with self.assertRaises(ValueError):
            ps.create_shadow_parent(
                source_position_id="",
                signal_id=None,
                symbol="SOLUSDT",
                side="LONG",
                opened_at_ms=1,
                entry_price=150,
                quantity=1,
                path=self.db,
            )
        with self.assertRaises(ValueError):
            ps.create_shadow_parent(
                source_position_id="P",
                signal_id=None,
                symbol="SOLUSDT",
                side="BUY",
                opened_at_ms=1,
                entry_price=150,
                quantity=1,
                path=self.db,
            )
        with self.assertRaises(ValueError):
            ps.create_shadow_parent(
                source_position_id="P",
                signal_id=None,
                symbol="SOLUSDT",
                side="LONG",
                opened_at_ms=1,
                entry_price=0,
                quantity=1,
                path=self.db,
            )

    def test_parent_and_branches_do_not_expose_execution_authority(self):
        created = self.create_parent()
        parent = ps.get_shadow_parent("PAPER:SIG-1", path=self.db)
        self.assertEqual(parent["execution_authority"], "NONE")
        self.assertEqual(ps.EXECUTION_AUTHORITY, "NONE")
        for row in ps.list_shadow_branches(created["parent_id"], path=self.db):
            self.assertEqual(row["execution_authority"], "NONE")
            spec = json.loads(row["spec_json"])
            self.assertEqual(spec["execution_authority"], "NONE")

    def test_remaining_quantity_cannot_exceed_entry_quantity(self):
        created = self.create_parent()
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            ps.update_shadow_branch_state(
                parent_id=created["parent_id"],
                branch_key="BE018_AGGRESSIVE",
                current_state="OPEN",
                remaining_quantity=2.01,
                path=self.db,
            )

    def test_unknown_branch_cannot_be_updated(self):
        created = self.create_parent()
        with self.assertRaisesRegex(ValueError, "unknown branch_key"):
            ps.update_shadow_branch_state(
                parent_id=created["parent_id"],
                branch_key="NOT_A_BRANCH",
                current_state="OPEN",
                path=self.db,
            )

    def test_two_parents_do_not_share_branch_state(self):
        first = self.create_parent("PAPER:SIG-1")
        second = ps.create_shadow_parent(
            source_position_id="PAPER:SIG-2",
            signal_id="SIG-2",
            symbol="BTCUSDT",
            side="SHORT",
            opened_at_ms=1_800_000_001_000,
            entry_price=60_000.0,
            quantity=0.01,
            path=self.db,
        )
        ps.update_shadow_branch_state(
            parent_id=first["parent_id"],
            branch_key="V43_LS",
            current_state="REDUCE25_QUALIFIED",
            state={"reduce": True},
            path=self.db,
        )
        second_states = {
            x["current_state"]
            for x in ps.list_shadow_branches(second["parent_id"], path=self.db)
        }
        self.assertEqual(second_states, {"ENTRY_OPEN"})
        summary = ps.shadow_core_summary(path=self.db)
        self.assertEqual(summary["parents"], 2)
        self.assertEqual(summary["branches"], 8)


if __name__ == "__main__":
    unittest.main()
