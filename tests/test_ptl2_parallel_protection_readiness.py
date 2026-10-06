import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import market_radar.parallel_protection_shadow as ps
import market_radar.parallel_protection_shadow_runtime as rt


class PTL2ParallelProtectionReadinessTests(unittest.TestCase):
    def setUp(self):
        ps._READY.clear()
        rt._READY.clear()
        self.td = tempfile.TemporaryDirectory()
        self.db = str(Path(self.td.name) / "ptl2.sqlite3")
        self.env = {
            "PROTECTION_SHADOW_RUNTIME_ENABLED": "true",
            "PROTECTION_SHADOW_START_MS": "1000",
            "PROTECTION_SHADOW_MAX_RAW_SYMBOLS": "6",
            "PROTECTION_SHADOW_RAW_MAX_PAGES": "5",
            "PP_V4_STAGE1_ENABLED": "true",
            "PP_V4_STAGE1_START_MS": "1000",
            "PAPER_TRADING_ENABLED": "true",
            "PAPER_LONG_DETECTOR_POLICY": "stage3c7a",
            "PTL3_HEALTH_OBSERVER_ONLY_ENABLED": "true",
            "LIVE_TRADING_ENABLED": "false",
        }

    def tearDown(self):
        self.td.cleanup()

    def position(self, *, pid="PAPER:PTL2:LONG", side="LONG", policy="stage3c7a"):
        qty = 4.998
        return {
            "position_id": pid,
            "signal_id": pid.replace("PAPER:", ""),
            "symbol": "BTCUSDT",
            "side": side,
            "mode": "PAPER",
            "status": "OPEN",
            "opened_at_ms": 2000,
            "entry_price": 100.04,
            "quantity": qty,
            "raw_json": json.dumps(
                {
                    "paper_entry_policy": policy,
                    "initial_quantity": qty,
                    "initial_notional_usdt": 500.0,
                    "entry_market_price": 100.02,
                    "entry_fill_price": 100.04,
                    "entry_fee_total": 0.375,
                    "slippage_bps": 2.0,
                    "fee_rate": 0.00075,
                    "long_detector_version": "stage3c7a-runtime-compat-v1",
                    "long_detector_policy_hash": "frozen-test-hash",
                }
            ),
        }

    def test_preflight_requires_one_shared_5s_boundary(self):
        with patch.dict(os.environ, self.env, clear=False):
            ready = rt.runtime_preflight()
            self.assertTrue(ready["ready"])
            self.assertEqual(ready["production_cohort"], "STAGE3C7A_LONG")
            self.assertEqual(
                ready["shadow_start_ms"], ready["pp_v4_observer_start_ms"]
            )
            self.assertEqual(ready["execution_authority"], "NONE")

            broken = dict(self.env)
            broken["PP_V4_STAGE1_START_MS"] = "1001"
            with patch.dict(os.environ, broken, clear=False):
                blocked = rt.runtime_preflight()
                self.assertFalse(blocked["ready"])
                self.assertIn(
                    "observer_shadow_boundary_mismatch", blocked["reasons"]
                )

    def test_preflight_requires_ptl3_health_isolation(self):
        broken = dict(self.env)
        broken["PTL3_HEALTH_OBSERVER_ONLY_ENABLED"] = "false"
        with patch.dict(os.environ, broken, clear=False):
            out = rt.runtime_preflight()
        self.assertFalse(out["ready"])
        self.assertIn("ptl3_health_isolation_disabled", out["reasons"])

    def test_production_registers_only_stage3c7a_long(self):
        with patch.dict(os.environ, self.env, clear=False):
            skipped_generic = rt.register_paper_position(
                self.position(pid="PAPER:GENERIC", policy="generic"),
                path=self.db,
            )
            self.assertEqual(skipped_generic["status"], "COHORT_SKIPPED")
            self.assertIsNone(
                ps.get_shadow_parent("PAPER:GENERIC", path=self.db)
            )

            skipped_short = rt.register_paper_position(
                self.position(pid="PAPER:SHORT", side="SHORT"),
                path=self.db,
            )
            self.assertEqual(skipped_short["status"], "COHORT_SKIPPED")
            self.assertIsNone(
                ps.get_shadow_parent("PAPER:SHORT", path=self.db)
            )

            registered = rt.register_paper_position(
                self.position(),
                path=self.db,
            )
            self.assertEqual(registered["status"], "REGISTERED")
            self.assertEqual(registered["execution_authority"], "NONE")

            parent = ps.get_shadow_parent("PAPER:PTL2:LONG", path=self.db)
            self.assertIsNotNone(parent)
            self.assertEqual(parent["side"], "LONG")
            self.assertAlmostEqual(parent["entry_price"], 100.04)
            self.assertAlmostEqual(parent["initial_quantity"], 4.998)
            self.assertEqual(parent["execution_authority"], "NONE")

            branches = ps.list_shadow_branches(parent["parent_id"], path=self.db)
            by_key = {row["branch_key"]: row for row in branches}
            self.assertEqual(
                set(by_key),
                {
                    "V42_BASELINE",
                    "V43_LS",
                    "BE025_CONSERVATIVE",
                    "BE018_AGGRESSIVE",
                },
            )
            for branch in by_key.values():
                self.assertEqual(branch["execution_authority"], "NONE")
                self.assertEqual(branch["status"], "OPEN")
                self.assertAlmostEqual(branch["entry_price"], 100.04)
                self.assertAlmostEqual(branch["initial_quantity"], 4.998)
                self.assertAlmostEqual(branch["remaining_quantity"], 4.998)

    def test_preflight_blocks_epoch_creation_when_observer_is_off(self):
        bad = dict(self.env)
        bad["PP_V4_STAGE1_ENABLED"] = "false"
        with patch.dict(os.environ, bad, clear=False):
            out = rt.ensure_runtime_epoch(path=self.db)
            self.assertEqual(out["status"], "CONFIG_BLOCKED")
            self.assertIn("pp_v4_5s_observer_disabled", out["preflight"]["reasons"])
            self.assertIsNone(rt._active_epoch(self.db))


if __name__ == "__main__":
    unittest.main()
