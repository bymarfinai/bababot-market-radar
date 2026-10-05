from __future__ import annotations

import json
import os
import tempfile
import time
import unittest

import market_radar.parallel_protection_shadow as ps
import market_radar.parallel_protection_shadow_runtime as rt


class FakeAggClient:
    def __init__(self, rows_by_symbol=None):
        self.rows_by_symbol = rows_by_symbol or {}
        self.calls = []

    def agg_trades(
        self,
        symbol,
        *,
        from_id=None,
        start_time=None,
        end_time=None,
        limit=1000,
    ):
        self.calls.append(
            {
                "symbol": symbol,
                "from_id": from_id,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            }
        )
        rows = list(self.rows_by_symbol.get(symbol.upper(), []))
        if from_id is not None:
            rows = [r for r in rows if int(r["a"]) >= int(from_id)]
        elif start_time is not None:
            rows = [r for r in rows if int(r["T"]) >= int(start_time)]
            if end_time is not None:
                rows = [r for r in rows if int(r["T"]) <= int(end_time)]
        rows.sort(key=lambda r: (int(r["a"]), int(r["T"])))
        return rows[: int(limit)]


def agg(a, price, ts, qty=1.0):
    return {
        "a": int(a),
        "p": str(price),
        "q": str(qty),
        "f": int(a) * 10,
        "l": int(a) * 10,
        "T": int(ts),
        "m": False,
    }


class ParallelProtectionShadowPS5ATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "ps5a.sqlite3")
        ps._READY.clear()
        rt._READY.clear()
        self.base = int(time.time() * 1000) - 2_000
        self.start = self.base
        self.position = {
            "position_id": "PAPER:PS5A-1",
            "signal_id": "PS5A-1",
            "symbol": "SOLUSDT",
            "side": "LONG",
            "mode": "PAPER",
            "status": "OPEN",
            "opened_at_ms": self.base + 100,
            "entry_price": 100.0,
            "quantity": 5.0,
            "raw_json": json.dumps(
                {
                    "initial_notional_usdt": 500.0,
                    "initial_quantity": 5.0,
                    "entry_fee_total": 0.05,
                    "fee_rate": 0.0001,
                    "slippage_bps": 0.000001,
                }
            ),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, rows):
        return FakeAggClient({"SOLUSDT": rows})

    def parent(self):
        return ps.get_shadow_parent(self.position["position_id"], path=self.db)

    def state(self, key):
        parent = self.parent()
        rows = {
            r["branch_key"]: r
            for r in ps.list_shadow_branches(parent["parent_id"], path=self.db)
        }
        return rows[key], json.loads(rows[key]["state_json"])

    def test_epoch_boundary_rejects_pre_boundary_position(self):
        old = dict(self.position)
        old["opened_at_ms"] = self.start - 1
        out = rt.register_paper_position(
            old,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "PRE_BOUNDARY")
        self.assertIsNone(ps.get_shadow_parent(old["position_id"], path=self.db))

    def test_epoch_is_persistent_and_conflicting_boundary_fails_closed(self):
        a = rt.ensure_runtime_epoch(start_ms=self.start, path=self.db)
        b = rt.ensure_runtime_epoch(start_ms=self.start, path=self.db)
        c = rt.ensure_runtime_epoch(start_ms=self.start + 1, path=self.db)
        self.assertEqual(a["status"], "ACTIVE")
        self.assertEqual(b["epoch_id"], a["epoch_id"])
        self.assertEqual(c["status"], "BOUNDARY_CONFLICT")
        self.assertEqual(c["active_started_at_ms"], self.start)

    def test_register_creates_one_parent_four_branches_and_active_cursor(self):
        out = rt.register_paper_position(
            self.position,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "REGISTERED")
        self.assertEqual(out["raw_feed_state"], "ACTIVE")
        parent = self.parent()
        self.assertEqual(parent["execution_authority"], "NONE")
        branches = ps.list_shadow_branches(parent["parent_id"], path=self.db)
        self.assertEqual(len(branches), 4)
        self.assertEqual({b["execution_authority"] for b in branches}, {"NONE"})
        again = rt.register_paper_position(
            self.position,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(again["status"], "EXISTING")

    def test_sample_catches_raw_before_5s_sample_and_settles_be018(self):
        t0 = self.position["opened_at_ms"]
        client = self.client(
            [
                agg(100, 100.20, t0 + 100),
                agg(101, 100.00, t0 + 200),
            ]
        )
        out = rt.process_protection_sample(
            self.position,
            current_price=100.05,
            observed_at_ms=t0 + 500,
            cycle_id="C1",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "COMPLETE")
        self.assertEqual(out["raw_event_count"], 2)
        parent = self.parent()
        events = ps.list_shadow_events(parent["parent_id"], path=self.db)
        self.assertEqual(
            [e["event_type"] for e in events],
            ["AGG_TRADE", "AGG_TRADE", "PROTECTION_SAMPLE_5S"],
        )
        row, state = self.state("BE018_AGGRESSIVE")
        self.assertEqual(row["status"], "CLOSED")
        self.assertEqual(state["close_event_seq"], 2)
        self.assertEqual(state["processed_event_seq"], 3)

    def test_cursor_uses_from_id_and_does_not_replay_old_raw_trade(self):
        t0 = self.position["opened_at_ms"]
        client = self.client([agg(10, 100.10, t0 + 100)])
        a = rt.process_protection_sample(
            self.position,
            current_price=100.11,
            observed_at_ms=t0 + 300,
            cycle_id="A",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(a["raw_event_count"], 1)
        client.rows_by_symbol["SOLUSDT"].append(agg(11, 100.12, t0 + 400))
        b = rt.process_protection_sample(
            self.position,
            current_price=100.12,
            observed_at_ms=t0 + 600,
            cycle_id="B",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(b["raw_event_count"], 1)
        self.assertEqual(client.calls[-1]["from_id"], 11)
        parent = self.parent()
        agg_events = [
            e for e in ps.list_shadow_events(parent["parent_id"], path=self.db)
            if e["event_type"] == "AGG_TRADE"
        ]
        self.assertEqual([e["source_event_id"] for e in agg_events], [
            "agg:SOLUSDT:10",
            "agg:SOLUSDT:11",
        ])

    def test_source_close_flushes_raw_then_closes_and_archives(self):
        t0 = self.position["opened_at_ms"]
        client = self.client([agg(20, 100.10, t0 + 100)])
        rt.process_protection_sample(
            self.position,
            current_price=100.10,
            observed_at_ms=t0 + 300,
            cycle_id="A",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        client.rows_by_symbol["SOLUSDT"].append(agg(21, 99.90, t0 + 400))
        out = rt.process_source_lifecycle(
            self.position,
            action="CLOSE",
            executed_at_ms=t0 + 500,
            market_price=99.90,
            fill_price=99.88,
            executed_quantity=5.0,
            fee=0.05,
            reason="stage12_close",
            source_event_id="paper-order-close-1",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "COMPLETE")
        parent = self.parent()
        self.assertEqual(parent["status"], "ARCHIVED")
        events = ps.list_shadow_events(parent["parent_id"], path=self.db)
        self.assertEqual(events[-2]["source_event_id"], "agg:SOLUSDT:21")
        self.assertEqual(events[-1]["event_type"], "SOURCE_POSITION_CLOSE")
        for row in ps.list_shadow_branches(parent["parent_id"], path=self.db):
            self.assertEqual(row["status"], "CLOSED")
            self.assertAlmostEqual(float(row["remaining_quantity"]), 0.0)

    def test_source_reduce_mirrors_and_parent_stays_open(self):
        t0 = self.position["opened_at_ms"]
        client = self.client([])
        out = rt.process_source_lifecycle(
            self.position,
            action="REDUCE",
            executed_at_ms=t0 + 500,
            market_price=100.0,
            fill_price=99.98,
            executed_quantity=2.5,
            fee=0.025,
            reason="stage12_reduce",
            source_event_id="paper-order-reduce-1",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "COMPLETE")
        parent = self.parent()
        self.assertEqual(parent["status"], "OPEN")
        for row in ps.list_shadow_branches(parent["parent_id"], path=self.db):
            self.assertAlmostEqual(float(row["remaining_quantity"]), 2.5)

    def test_capacity_guard_keeps_source_safe_and_excludes_overflow_comparison(self):
        first = rt.register_paper_position(
            self.position,
            start_ms=self.start,
            raw_capacity=1,
            path=self.db,
        )
        self.assertEqual(first["raw_feed_state"], "ACTIVE")
        other = dict(self.position)
        other["position_id"] = "PAPER:PS5A-2"
        other["signal_id"] = "PS5A-2"
        other["symbol"] = "BTCUSDT"
        other["opened_at_ms"] += 1
        second = rt.register_paper_position(
            other,
            start_ms=self.start,
            raw_capacity=1,
            path=self.db,
        )
        self.assertEqual(second["raw_feed_state"], "CAPACITY_EXCEEDED")
        parent = ps.get_shadow_parent(other["position_id"], path=self.db)
        audit = ps.audit_shadow_parity(parent["parent_id"], path=self.db)
        self.assertFalse(audit["comparison_eligible"])
        self.assertIn("RAW_FEED_CAPACITY_EXCEEDED", audit["issue_types"])

    def test_agg_id_gap_marks_feed_error_and_comparison_invalid(self):
        t0 = self.position["opened_at_ms"]
        client = self.client([agg(30, 100.10, t0 + 100)])
        rt.process_protection_sample(
            self.position,
            current_price=100.10,
            observed_at_ms=t0 + 300,
            cycle_id="A",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        client.rows_by_symbol["SOLUSDT"].append(agg(32, 100.12, t0 + 400))
        out = rt.process_protection_sample(
            self.position,
            current_price=100.12,
            observed_at_ms=t0 + 600,
            cycle_id="B",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "COMPARISON_INVALID")
        self.assertEqual(out["raw_feed_state"], "FEED_ERROR")
        parent = self.parent()
        audit = ps.audit_shadow_parity(parent["parent_id"], path=self.db)
        self.assertFalse(audit["comparison_eligible"])
        self.assertIn("RAW_FEED_ERROR", audit["issue_types"])

    def test_invalid_comparison_source_close_still_archives_parent(self):
        t0 = self.position["opened_at_ms"]
        client = self.client([agg(40, 100.10, t0 + 100)])
        rt.process_protection_sample(
            self.position,
            current_price=100.10,
            observed_at_ms=t0 + 300,
            cycle_id="A",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        client.rows_by_symbol["SOLUSDT"].append(agg(42, 100.12, t0 + 400))
        invalid = rt.process_protection_sample(
            self.position,
            current_price=100.12,
            observed_at_ms=t0 + 600,
            cycle_id="B",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(invalid["status"], "COMPARISON_INVALID")
        closed = rt.process_source_lifecycle(
            self.position,
            action="CLOSE",
            executed_at_ms=t0 + 700,
            market_price=100.0,
            fill_price=99.98,
            executed_quantity=5.0,
            fee=0.05,
            reason="source_close_after_invalid",
            source_event_id="paper:invalid-close:CLOSE",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(closed["status"], "COMPARISON_INVALID")
        self.assertEqual(self.parent()["status"], "ARCHIVED")
        summary = rt.runtime_summary(path=self.db)
        self.assertEqual(summary["raw_feed_states"]["SOURCE_CLOSED"], 1)

    def test_raw_feed_stops_after_be_is_superseded(self):
        t0 = self.position["opened_at_ms"]
        client = self.client([])
        first = rt.process_protection_sample(
            self.position,
            current_price=100.60,
            observed_at_ms=t0 + 500,
            cycle_id="A",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(first["status"], "COMPLETE")
        calls_after_first = len(client.calls)
        second = rt.process_protection_sample(
            self.position,
            current_price=100.61,
            observed_at_ms=t0 + 1_000,
            cycle_id="B",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(second["status"], "COMPLETE")
        self.assertEqual(len(client.calls), calls_after_first)
        self.assertEqual(second["raw_feed_state"], "NOT_NEEDED")

    def test_many_raw_events_are_batched_but_all_processed_in_order(self):
        t0 = self.position["opened_at_ms"]
        rows = [
            agg(1000 + i, 100.01 + i * 0.0001, t0 + 10 + i)
            for i in range(250)
        ]
        client = self.client(rows)
        out = rt.process_protection_sample(
            self.position,
            current_price=100.04,
            observed_at_ms=t0 + 500,
            cycle_id="BATCH",
            client=client,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "COMPLETE")
        self.assertEqual(out["raw_event_count"], 250)
        self.assertEqual(out["decision"]["processed_n"], 251)
        parent = self.parent()
        self.assertEqual(
            len(ps.list_shadow_events(parent["parent_id"], path=self.db)),
            251,
        )

    def test_reconcile_recovers_missed_source_close_after_restart(self):
        reg = rt.register_paper_position(
            self.position,
            start_ms=self.start,
            path=self.db,
        )
        parent_id = reg["parent_id"]
        t0 = self.position["opened_at_ms"]
        with ps._local_sqlite_connect(self.db) as conn:
            conn.executescript(
                """
                create table positions (
                    position_id text primary key,
                    signal_id text,
                    symbol text,
                    side text,
                    mode text,
                    status text,
                    opened_at_ms integer,
                    closed_at_ms integer,
                    entry_price real,
                    quantity real,
                    raw_json text
                );
                create table paper_orders (
                    order_id text primary key,
                    position_id text,
                    status text,
                    action text,
                    executed_at_ms integer,
                    created_at_ms integer,
                    market_price real,
                    fill_price real,
                    executed_quantity real,
                    fee real,
                    reason text
                );
                """
            )
            conn.execute(
                """insert into positions (
                    position_id,signal_id,symbol,side,mode,status,opened_at_ms,
                    closed_at_ms,entry_price,quantity,raw_json
                ) values (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    self.position["position_id"],
                    self.position["signal_id"],
                    self.position["symbol"],
                    self.position["side"],
                    "PAPER",
                    "CLOSED",
                    t0,
                    t0 + 500,
                    100.0,
                    0.0,
                    self.position["raw_json"],
                ),
            )
            conn.execute(
                """insert into paper_orders (
                    order_id,position_id,status,action,executed_at_ms,created_at_ms,
                    market_price,fill_price,executed_quantity,fee,reason
                ) values (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "RECOVER-CLOSE",
                    self.position["position_id"],
                    "FILLED",
                    "CLOSE",
                    t0 + 500,
                    t0 + 490,
                    99.9,
                    99.88,
                    5.0,
                    0.05,
                    "recovered_source_close",
                ),
            )

        out = rt.reconcile_source_lifecycle(
            client=self.client([]),
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "COMPLETE")
        self.assertEqual(out["recovered_events"], 1)
        parent = ps.get_shadow_parent(self.position["position_id"], path=self.db)
        self.assertEqual(parent["parent_id"], parent_id)
        self.assertEqual(parent["status"], "ARCHIVED")
        self.assertIsNotNone(
            ps.get_shadow_event_by_source_id(
                parent_id,
                "paper:RECOVER-CLOSE:CLOSE",
                path=self.db,
            )
        )
        again = rt.reconcile_source_lifecycle(
            client=self.client([]),
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(again["recovered_events"], 0)

    def test_runtime_summary_exposes_epoch_and_authority(self):
        rt.register_paper_position(
            self.position,
            start_ms=self.start,
            path=self.db,
        )
        summary = rt.runtime_summary(path=self.db)
        self.assertEqual(summary["epoch"]["started_at_ms"], self.start)
        self.assertEqual(summary["parents"], 1)
        self.assertEqual(summary["active_source_parents"], 1)
        self.assertEqual(summary["execution_authority"], "NONE")
        self.assertEqual(summary["source_mode"], "PAPER_ONLY")

    def test_live_source_mode_is_never_registered(self):
        live = dict(self.position)
        live["mode"] = "LIVE"
        out = rt.register_paper_position(
            live,
            start_ms=self.start,
            path=self.db,
        )
        self.assertEqual(out["status"], "SOURCE_MODE_SKIPPED")
        self.assertIsNone(ps.get_shadow_parent(live["position_id"], path=self.db))


if __name__ == "__main__":
    unittest.main()
