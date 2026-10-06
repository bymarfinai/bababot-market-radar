from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import market_radar.paper_store as store
import market_radar.paper_trading as paper
import market_radar.persistence as persistence
from market_radar.parallel_protection_shadow import BRANCH_KEYS


def evaluation(*, action: str = "CLOSE", hard_risk: bool = False) -> dict:
    return {
        "evaluation_id": "EVAL:PTL3:1",
        "position_id": "PAPER:PTL3:LONG",
        "evaluated_at_ms": 2_100,
        "candle_close_time_ms": 2_000,
        "current_price": 99.4,
        "unrealized_pnl_pct": -0.60,
        "mfe_pct": 0.72,
        "mae_pct": -0.65,
        "health_score": 31.0,
        "deterministic_action": action,
        "ai_action": None,
        "ai_confidence": None,
        "final_action": action,
        "hard_risk_triggered": hard_risk,
        "reasons_json": json.dumps(["structure_break"]),
        "contradictions_json": json.dumps(["momentum"]),
        "snapshot_json": "{}",
        "ai_json": None,
        "lifecycle_version": "stage12-v3.1-entry-boundary",
    }


def position(*, side: str = "LONG", policy: str = "stage3c7a") -> dict:
    return {
        "position_id": "PAPER:PTL3:LONG",
        "signal_id": "SIG:PTL3",
        "symbol": "BTCUSDT",
        "side": side,
        "mode": "PAPER",
        "status": "OPEN",
        "quantity": 5.0,
        "raw_json": json.dumps(
            {
                "paper_entry_policy": policy,
                "initial_quantity": 5.0,
                "initial_notional_usdt": 500.0,
            }
        ),
    }


def branches(*, terminal: bool = False) -> list[dict]:
    return [
        {
            "branch_key": key,
            "status": "CLOSED" if terminal else "OPEN",
            "execution_authority": "NONE",
        }
        for key in BRANCH_KEYS
    ]


class PTL3IsolationEligibilityTests(unittest.TestCase):
    def test_exact_shadow_cohort_is_observer_only(self):
        env = {"PTL3_HEALTH_OBSERVER_ONLY_ENABLED": "true"}
        with patch.dict(os.environ, env, clear=False),              patch.object(
                 paper,
                 "get_shadow_parent",
                 return_value={
                     "parent_id": "PSP:1",
                     "status": "OPEN",
                     "execution_authority": "NONE",
                 },
             ),              patch.object(paper, "list_shadow_branches", return_value=branches()),              patch.object(
                 paper,
                 "audit_shadow_parity",
                 return_value={
                     "status": "PARITY_OK",
                     "comparison_eligible": True,
                     "issue_types": [],
                 },
             ):
            out = paper._health_observer_isolation_target(position())

        self.assertTrue(out["isolate"])
        self.assertEqual(out["shadow_parent_id"], "PSP:1")
        self.assertEqual(out["open_branch_count"], 4)
        self.assertEqual(out["parity_status"], "PARITY_OK")

    def test_missing_shadow_parent_fails_open_to_health(self):
        env = {"PTL3_HEALTH_OBSERVER_ONLY_ENABLED": "true"}
        with patch.dict(os.environ, env, clear=False),              patch.object(paper, "get_shadow_parent", return_value=None):
            out = paper._health_observer_isolation_target(position())
        self.assertFalse(out["isolate"])
        self.assertEqual(out["reason"], "shadow_parent_missing")

    def test_generic_or_short_source_is_never_isolated(self):
        env = {"PTL3_HEALTH_OBSERVER_ONLY_ENABLED": "true"}
        with patch.dict(os.environ, env, clear=False),              patch.object(paper, "get_shadow_parent") as get_parent:
            generic = paper._health_observer_isolation_target(
                position(policy="generic")
            )
            short = paper._health_observer_isolation_target(
                position(side="SHORT")
            )
        self.assertFalse(generic["isolate"])
        self.assertFalse(short["isolate"])
        get_parent.assert_not_called()

    def test_partial_or_parity_invalid_shadow_fails_open(self):
        env = {"PTL3_HEALTH_OBSERVER_ONLY_ENABLED": "true"}
        parent = {
            "parent_id": "PSP:1",
            "status": "OPEN",
            "execution_authority": "NONE",
        }
        with patch.dict(os.environ, env, clear=False),              patch.object(paper, "get_shadow_parent", return_value=parent),              patch.object(
                 paper,
                 "list_shadow_branches",
                 return_value=branches()[:-1],
             ):
            partial = paper._health_observer_isolation_target(position())
        self.assertFalse(partial["isolate"])
        self.assertEqual(partial["reason"], "shadow_branch_contract_incomplete")

        with patch.dict(os.environ, env, clear=False),              patch.object(paper, "get_shadow_parent", return_value=parent),              patch.object(paper, "list_shadow_branches", return_value=branches()),              patch.object(
                 paper,
                 "audit_shadow_parity",
                 return_value={
                     "status": "PARITY_ERROR",
                     "comparison_eligible": False,
                     "issue_types": ["RAW_FEED_GAP"],
                 },
             ):
            invalid = paper._health_observer_isolation_target(position())
        self.assertFalse(invalid["isolate"])
        self.assertEqual(invalid["reason"], "shadow_parity_invalid")

    def test_terminal_branches_restore_health_authority(self):
        env = {"PTL3_HEALTH_OBSERVER_ONLY_ENABLED": "true"}
        with patch.dict(os.environ, env, clear=False),              patch.object(
                 paper,
                 "get_shadow_parent",
                 return_value={
                     "parent_id": "PSP:1",
                     "status": "OPEN",
                     "execution_authority": "NONE",
                 },
             ),              patch.object(
                 paper,
                 "list_shadow_branches",
                 return_value=branches(terminal=True),
             ):
            out = paper._health_observer_isolation_target(position())
        self.assertFalse(out["isolate"])
        self.assertEqual(out["reason"], "shadow_branches_terminal")


class PTL3LifecycleOrderTests(unittest.TestCase):
    def test_health_close_is_recorded_but_not_ordered(self):
        item = evaluation(action="CLOSE", hard_risk=True)
        with patch.object(paper, "paper_trading_enabled", return_value=True),              patch.object(
                 paper, "list_unacted_lifecycle_actions", return_value=[item]
             ),              patch.object(paper, "get_position", return_value=position()),              patch.object(
                 paper,
                 "_health_observer_isolation_target",
                 return_value={
                     "isolate": True,
                     "shadow_parent_id": "PSP:1",
                     "open_branch_count": 4,
                     "parity_status": "PARITY_OK",
                 },
             ),              patch.object(
                 paper, "record_health_observer_decision", return_value={}
             ) as record,              patch.object(paper, "create_order") as create:
            out = paper.sync_lifecycle_orders()

        self.assertEqual(out["queued"], 0)
        self.assertEqual(out["health_observer_only"], 1)
        self.assertEqual(out["health_observer_hard_risk"], 1)
        self.assertEqual(out["health_isolation_fail_open"], 0)
        record.assert_called_once()
        self.assertEqual(
            record.call_args.kwargs["evaluation"]["evaluation_id"],
            item["evaluation_id"],
        )
        create.assert_not_called()

    def test_observer_ledger_failure_restores_health_order_authority(self):
        item = evaluation(action="REDUCE")
        with patch.object(paper, "paper_trading_enabled", return_value=True),              patch.object(
                 paper, "list_unacted_lifecycle_actions", return_value=[item]
             ),              patch.object(paper, "get_position", return_value=position()),              patch.object(
                 paper,
                 "_health_observer_isolation_target",
                 return_value={
                     "isolate": True,
                     "shadow_parent_id": "PSP:1",
                     "open_branch_count": 4,
                     "parity_status": "PARITY_OK",
                 },
             ),              patch.object(
                 paper,
                 "record_health_observer_decision",
                 side_effect=RuntimeError("db down"),
             ),              patch.object(paper, "record_shadow_integrity_issue"),              patch.object(paper, "create_order") as create:
            out = paper.sync_lifecycle_orders()

        self.assertEqual(out["queued"], 1)
        self.assertEqual(out["health_observer_only"], 0)
        self.assertEqual(out["health_isolation_fail_open"], 1)
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["action"], "REDUCE")

    def test_non_experiment_trade_keeps_legacy_health_order(self):
        item = evaluation(action="CLOSE")
        with patch.object(paper, "paper_trading_enabled", return_value=True),              patch.object(
                 paper, "list_unacted_lifecycle_actions", return_value=[item]
             ),              patch.object(
                 paper,
                 "get_position",
                 return_value=position(policy="generic"),
             ),              patch.object(
                 paper,
                 "_health_observer_isolation_target",
                 return_value={"isolate": False, "reason": "not_experiment"},
             ),              patch.object(paper, "create_order") as create:
            out = paper.sync_lifecycle_orders()

        self.assertEqual(out["queued"], 1)
        self.assertEqual(out["health_observer_only"], 0)
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs["action"], "CLOSE")


class PTL3ObserverLedgerStoreTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.db = str(Path(self.td.name) / "ptl3.sqlite3")
        self.env = patch.dict(
            os.environ,
            {"DATABASE_URL": "", "BABABOT_DB_PATH": self.db},
            clear=False,
        )
        self.env.start()
        persistence._SCHEMA_INITIALIZED.clear()
        store._PAPER_INITIALIZED.clear()
        store.initialize_paper_store()

        with persistence._sqlite_connect(self.db) as conn:
            conn.execute(
                """insert into positions (
                    position_id,signal_id,symbol,side,status,opened_at_ms,
                    entry_price,quantity,mode,raw_json
                ) values (?,?,?,?,?,?,?,?,?,?)""",
                (
                    "PAPER:PTL3:LONG",
                    None,
                    "BTCUSDT",
                    "LONG",
                    "OPEN",
                    1_000,
                    100.0,
                    5.0,
                    "PAPER",
                    json.dumps({"paper_entry_policy": "stage3c7a"}),
                ),
            )
            e = evaluation(action="CLOSE", hard_risk=True)
            fields = (
                "evaluation_id", "position_id", "evaluated_at_ms",
                "candle_close_time_ms", "current_price",
                "unrealized_pnl_pct", "mfe_pct", "mae_pct", "health_score",
                "deterministic_action", "ai_action", "ai_confidence",
                "final_action", "hard_risk_triggered", "reasons_json",
                "contradictions_json", "snapshot_json", "ai_json",
                "lifecycle_version",
            )
            conn.execute(
                f"""insert into position_evaluations ({",".join(fields)})
                    values ({",".join("?" for _ in fields)})""",
                tuple(e[name] for name in fields),
            )

    def tearDown(self):
        self.env.stop()
        self.td.cleanup()
        persistence._SCHEMA_INITIALIZED.clear()
        store._PAPER_INITIALIZED.clear()

    def test_observer_decision_is_idempotent_and_removes_action_from_order_queue(self):
        before = store.list_unacted_lifecycle_actions()
        self.assertEqual(len(before), 1)

        first = store.record_health_observer_decision(
            evaluation=before[0],
            shadow_parent_id="PSP:1",
            isolation_version=paper.PTL3_HEALTH_ISOLATION_VERSION,
            reason="stage12_health_observer_only",
            payload={"would_action": "CLOSE"},
        )
        second = store.record_health_observer_decision(
            evaluation=before[0],
            shadow_parent_id="PSP:1",
            isolation_version=paper.PTL3_HEALTH_ISOLATION_VERSION,
            reason="stage12_health_observer_only",
            payload={"would_action": "CLOSE"},
        )

        self.assertEqual(first["evaluation_id"], second["evaluation_id"])
        rows = store.list_health_observer_decisions()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["would_action"], "CLOSE")
        self.assertTrue(bool(rows[0]["hard_risk_triggered"]))
        self.assertEqual(store.list_unacted_lifecycle_actions(), [])

        summary = store.paper_summary()
        self.assertEqual(summary["health_observer_decisions"], 1)
        self.assertEqual(summary["health_would_close"], 1)
        self.assertEqual(summary["health_would_reduce"], 0)
        self.assertEqual(summary["health_hard_risk_observed"], 1)


if __name__ == "__main__":
    unittest.main()
