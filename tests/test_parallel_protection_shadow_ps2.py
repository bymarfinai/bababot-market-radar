from __future__ import annotations

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

import market_radar.parallel_protection_shadow as ps


class ParallelProtectionShadowPS2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "ps2.sqlite3")
        ps._READY.clear()
        self.parent = ps.create_shadow_parent(
            source_position_id="PAPER:SIG-PS2",
            signal_id="SIG-PS2",
            symbol="SOLUSDT",
            side="LONG",
            opened_at_ms=1_800_000_000_000,
            entry_price=150.0,
            quantity=2.0,
            path=self.db,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def fanout(self, event_id: str, event_time_ms: int, price: float, payload=None):
        return ps.fanout_shadow_event(
            parent_id=self.parent["parent_id"],
            source_event_id=event_id,
            event_time_ms=event_time_ms,
            event_type="AGG_TRADE",
            market_price=price,
            payload=payload or {"qty": 1.0},
            path=self.db,
        )

    def test_one_event_fans_out_identically_to_all_four_branches(self):
        out = self.fanout("E1", 1_800_000_000_100, 150.1)
        self.assertEqual(out["status"], "FANOUT_OK")
        self.assertEqual(out["event_seq"], 1)
        self.assertEqual(out["receipt_count"], 4)

        canonical = ps.list_shadow_events(self.parent["parent_id"], path=self.db)
        self.assertEqual(len(canonical), 1)
        event_hash = canonical[0]["event_hash"]

        for key in ps.BRANCH_KEYS:
            receipts = ps.list_shadow_branch_events(
                self.parent["parent_id"], key, path=self.db
            )
            self.assertEqual(len(receipts), 1)
            self.assertEqual(receipts[0]["source_event_id"], "E1")
            self.assertEqual(receipts[0]["event_seq"], 1)
            self.assertEqual(receipts[0]["event_hash"], event_hash)

        branches = ps.list_shadow_branches(self.parent["parent_id"], path=self.db)
        self.assertEqual({x["last_event_id"] for x in branches}, {"E1"})
        self.assertEqual(
            {x["last_event_time_ms"] for x in branches},
            {1_800_000_000_100},
        )

    def test_identical_duplicate_is_idempotent(self):
        first = self.fanout("E1", 1_800_000_000_100, 150.1)
        second = self.fanout("E1", 1_800_000_000_100, 150.1)
        self.assertEqual(first["status"], "FANOUT_OK")
        self.assertEqual(second["status"], "DUPLICATE")
        self.assertEqual(second["event_seq"], 1)
        self.assertEqual(len(ps.list_shadow_events(self.parent["parent_id"], path=self.db)), 1)
        summary = ps.shadow_event_summary(path=self.db)
        self.assertEqual(summary["canonical_events"], 1)
        self.assertEqual(summary["branch_receipts"], 4)
        self.assertEqual(summary["parity_issues"], 0)

    def test_same_source_id_with_different_payload_is_integrity_error(self):
        self.fanout("E1", 1_800_000_000_100, 150.1, {"qty": 1.0})
        conflict = self.fanout("E1", 1_800_000_000_100, 150.1, {"qty": 2.0})
        self.assertEqual(conflict["status"], "PARITY_ERROR")
        self.assertEqual(conflict["reason"], "SOURCE_EVENT_CONFLICT")
        self.assertEqual(len(ps.list_shadow_events(self.parent["parent_id"], path=self.db)), 1)
        audit = ps.audit_shadow_parity(self.parent["parent_id"], path=self.db)
        self.assertEqual(audit["status"], "PARITY_ERROR")
        self.assertFalse(audit["comparison_eligible"])
        self.assertIn("SOURCE_EVENT_CONFLICT", audit["issue_types"])

    def test_out_of_order_event_is_rejected_and_marks_parent_invalid_for_comparison(self):
        self.fanout("E1", 1_800_000_000_200, 150.2)
        out = self.fanout("E2", 1_800_000_000_150, 150.15)
        self.assertEqual(out["status"], "PARITY_ERROR")
        self.assertEqual(out["reason"], "OUT_OF_ORDER_EVENT")
        self.assertEqual(len(ps.list_shadow_events(self.parent["parent_id"], path=self.db)), 1)
        audit = ps.audit_shadow_parity(self.parent["parent_id"], path=self.db)
        self.assertEqual(audit["status"], "PARITY_ERROR")
        self.assertFalse(audit["comparison_eligible"])
        self.assertIn("OUT_OF_ORDER_EVENT", audit["issue_types"])

    def test_same_millisecond_distinct_events_are_allowed_and_sequenced(self):
        a = self.fanout("E1", 1_800_000_000_100, 150.1)
        b = self.fanout("E2", 1_800_000_000_100, 150.11)
        self.assertEqual(a["event_seq"], 1)
        self.assertEqual(b["event_seq"], 2)
        events = ps.list_shadow_events(self.parent["parent_id"], path=self.db)
        self.assertEqual([e["event_seq"] for e in events], [1, 2])
        self.assertEqual(ps.audit_shadow_parity(
            self.parent["parent_id"], path=self.db
        )["status"], "PARITY_OK")

    def test_event_before_entry_is_rejected(self):
        out = self.fanout("EARLY", 1_799_999_999_999, 149.0)
        self.assertEqual(out["status"], "PARITY_ERROR")
        self.assertEqual(out["reason"], "EVENT_BEFORE_OPEN")
        self.assertEqual(len(ps.list_shadow_events(self.parent["parent_id"], path=self.db)), 0)

    def test_audit_detects_missing_branch_receipt(self):
        self.fanout("E1", 1_800_000_000_100, 150.1)
        with ps._local_sqlite_connect(self.db) as conn:
            conn.execute(
                """delete from protection_shadow_branch_events
                   where parent_id=? and branch_key='V43_LS' and event_seq=1""",
                (self.parent["parent_id"],),
            )
        audit = ps.audit_shadow_parity(self.parent["parent_id"], path=self.db)
        self.assertEqual(audit["status"], "PARITY_ERROR")
        self.assertEqual(audit["branches"]["V43_LS"]["missing_seq"], [1])
        self.assertIn("AUDIT_PARITY_MISMATCH", audit["issue_types"])

    def test_duplicate_recheck_detects_corrupted_receipts(self):
        self.fanout("E1", 1_800_000_000_100, 150.1)
        with ps._local_sqlite_connect(self.db) as conn:
            conn.execute(
                """delete from protection_shadow_branch_events
                   where parent_id=? and branch_key='BE025_CONSERVATIVE' and event_seq=1""",
                (self.parent["parent_id"],),
            )
        out = self.fanout("E1", 1_800_000_000_100, 150.1)
        self.assertEqual(out["status"], "PARITY_ERROR")
        self.assertEqual(out["reason"], "DUPLICATE_RECEIPT_PARITY_FAILURE")
        self.assertEqual(out["receipt_count"], 3)
        audit = ps.audit_shadow_parity(self.parent["parent_id"], path=self.db)
        self.assertFalse(audit["comparison_eligible"])
        self.assertIn("DUPLICATE_RECEIPT_PARITY_FAILURE", audit["issue_types"])

    def test_fanout_refuses_incomplete_branch_set(self):
        with ps._local_sqlite_connect(self.db) as conn:
            conn.execute(
                """delete from protection_shadow_branches
                   where parent_id=? and branch_key='V43_LS'""",
                (self.parent["parent_id"],),
            )
        out = self.fanout("E1", 1_800_000_000_100, 150.1)
        self.assertEqual(out["status"], "PARITY_ERROR")
        self.assertEqual(out["reason"], "BRANCH_SET_MISMATCH")
        self.assertIn("V43_LS", out["missing"])
        self.assertEqual(len(ps.list_shadow_events(self.parent["parent_id"], path=self.db)), 0)

    def test_parents_have_independent_event_sequences(self):
        other = ps.create_shadow_parent(
            source_position_id="PAPER:SIG-PS2-B",
            signal_id="SIG-PS2-B",
            symbol="BTCUSDT",
            side="SHORT",
            opened_at_ms=1_800_000_000_000,
            entry_price=60_000.0,
            quantity=0.01,
            path=self.db,
        )
        a = self.fanout("SAME-ID", 1_800_000_000_100, 150.1)
        b = ps.fanout_shadow_event(
            parent_id=other["parent_id"],
            source_event_id="SAME-ID",
            event_time_ms=1_800_000_000_100,
            event_type="AGG_TRADE",
            market_price=59_990.0,
            payload={"qty": 0.1},
            path=self.db,
        )
        self.assertEqual(a["event_seq"], 1)
        self.assertEqual(b["event_seq"], 1)
        self.assertNotEqual(a["event_hash"], b["event_hash"])
        self.assertEqual(ps.audit_shadow_parity(
            other["parent_id"], path=self.db
        )["status"], "PARITY_OK")

    def test_payload_key_order_does_not_change_event_identity(self):
        a = ps._event_hash(
            parent_id=self.parent["parent_id"],
            source_event_id="E1",
            event_time_ms=1_800_000_000_100,
            event_type="AGG_TRADE",
            market_price=150.1,
            payload={"a": 1, "b": 2},
        )
        b = ps._event_hash(
            parent_id=self.parent["parent_id"],
            source_event_id="E1",
            event_time_ms=1_800_000_000_100,
            event_type="AGG_TRADE",
            market_price=150.1,
            payload={"b": 2, "a": 1},
        )
        self.assertEqual(a, b)

    def test_concurrent_same_millisecond_events_are_serialized_cleanly(self):
        event_time = 1_800_000_000_100
        def send(i):
            return self.fanout(f"C{i}", event_time, 150.0 + i / 1000.0)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(send, range(1, 5)))
        self.assertEqual({r["status"] for r in results}, {"FANOUT_OK"})
        self.assertEqual(
            sorted(r["event_seq"] for r in results),
            [1, 2, 3, 4],
        )
        audit = ps.audit_shadow_parity(self.parent["parent_id"], path=self.db)
        self.assertEqual(audit["status"], "PARITY_OK")
        self.assertTrue(audit["comparison_eligible"])
        self.assertEqual(audit["canonical_event_count"], 4)
        self.assertTrue(all(
            b["receipt_count"] == 4 for b in audit["branches"].values()
        ))

    def test_ps2_never_changes_execution_authority(self):
        self.fanout("E1", 1_800_000_000_100, 150.1)
        branches = ps.list_shadow_branches(self.parent["parent_id"], path=self.db)
        self.assertEqual({x["execution_authority"] for x in branches}, {"NONE"})
        audit = ps.audit_shadow_parity(self.parent["parent_id"], path=self.db)
        self.assertEqual(audit["execution_authority"], "NONE")
        self.assertEqual(ps.shadow_event_summary(path=self.db)["execution_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
