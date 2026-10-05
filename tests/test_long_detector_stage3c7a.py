import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.long_detector_stage3c7a import (
    LONG_DETECTOR_VERSION,
    POLICY_HASH,
    ROUTER_VERSION,
    TEMPORAL_THRESHOLD_PCT,
    _INITIALIZED,
    _save_state,
    counterflow_veto,
    evaluate_stage3c7a,
    get_stage3c7a_state,
    route_t0,
    stage3c7a_enabled,
)


class Stage3C7ALongDetectorTests(unittest.TestCase):
    def test_policy_is_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(stage3c7a_enabled())
        with patch.dict(
            os.environ,
            {"PAPER_LONG_DETECTOR_POLICY": "stage3c7a"},
            clear=True,
        ):
            self.assertTrue(stage3c7a_enabled())

    def test_frozen_policy_identity(self):
        self.assertEqual(LONG_DETECTOR_VERSION, "stage3c7a-runtime-compat-v1")
        self.assertEqual(ROUTER_VERSION, "stage3c7a-router-recovered-compat-v1")
        self.assertEqual(
            POLICY_HASH,
            "ada659086dc0b573ab1d70cd61b9c7dadc11161c35d371b54dcfd2345a76e383",
        )
        self.assertAlmostEqual(TEMPORAL_THRESHOLD_PCT, 0.158514)

    def test_router_and_counterflow_veto_are_deterministic(self):
        flow = {
            "f_gate_flow_family": "ALIGNED",
            "f_gate_taker_share_for_selected": 0.75,
            "f_gate_side_ret_1m_pct": 0.45,
            "f_new_flow_support": 1.0,
            "f_new_micro_accel_1_vs_3": 0.20,
            "f_f_coin_minus_market_30m": 1.0,
            "f_f_oi_change_30m_pct": 0.5,
            "f_micro_volume_ratio_last_vs_prev10": 2.0,
        }
        route, probability = route_t0(flow)
        self.assertEqual(route, "FLOW_ALIGNED")
        self.assertGreaterEqual(probability, 0.5)

        veto = dict(flow)
        veto.update(
            {
                "f_new_accel_5_vs_15": 0.50,
                "f_f_selected_slope5_norm": 0.20,
                "f_f_coin_minus_market_30m": 0.0,
                "f_f_coin_minus_market_15m": 1.0,
            }
        )
        self.assertTrue(counterflow_veto(veto))
        veto["f_f_coin_minus_market_15m"] = 3.0
        self.assertFalse(counterflow_veto(veto))

    def test_first_stage11c_enter_is_frozen_across_t0_fetch_retry(self):
        with tempfile.TemporaryDirectory() as td:
            db = str(Path(td) / "ptl1-retry.sqlite3")
            candidate = {
                "signal_id": "TEST:RETRY:LONG",
                "side": "LONG",
                "symbol": "TESTUSDT",
            }
            gate = {
                "checked_at_ms": 1000,
                "verdict": "ENTER",
                "version": "stage11c-test",
                "reasons": [],
                "snapshot": {"current_price": 100.0},
            }
            flow_features = {
                "f_gate_flow_family": "ALIGNED",
                "f_gate_taker_share_for_selected": 0.75,
                "f_gate_side_ret_1m_pct": 0.45,
                "f_new_flow_support": 1.0,
                "f_new_micro_accel_1_vs_3": 0.20,
                "f_f_coin_minus_market_30m": 1.0,
                "f_f_oi_change_30m_pct": 0.5,
                "f_micro_volume_ratio_last_vs_prev10": 2.0,
                "f_new_accel_5_vs_15": 1.0,
                "f_f_selected_slope5_norm": 1.0,
                "f_f_coin_minus_market_15m": 3.0,
            }
            with patch.dict(
                os.environ,
                {"BABABOT_DB_PATH": db, "DATABASE_URL": ""},
                clear=False,
            ):
                _INITIALIZED.clear()
                with patch(
                    "market_radar.long_detector_stage3c7a.build_t0_features",
                    side_effect=RuntimeError("temporary fetch failure"),
                ):
                    with self.assertRaises(RuntimeError):
                        evaluate_stage3c7a(object(), candidate, gate=gate)
                pending = get_stage3c7a_state(candidate["signal_id"])
                self.assertEqual(pending["route"], "INIT_PENDING")
                self.assertEqual(pending["gate_checked_at_ms"], 1000)
                self.assertEqual(pending["gate_price"], 100.0)

                later_gate = {
                    **gate,
                    "checked_at_ms": 9999,
                    "snapshot": {"current_price": 999.0},
                }
                with patch(
                    "market_radar.long_detector_stage3c7a.build_t0_features",
                    return_value=flow_features,
                ), patch(
                    "market_radar.long_detector_stage3c7a._evaluate_flow_temporal",
                    side_effect=lambda client, cand, state: {
                        "verdict": "WAIT",
                        "gate_checked_at_ms": state["gate_checked_at_ms"],
                    },
                ):
                    out = evaluate_stage3c7a(object(), candidate, gate=later_gate)
                self.assertEqual(out["gate_checked_at_ms"], 1000)
                frozen = get_stage3c7a_state(candidate["signal_id"])
                self.assertEqual(frozen["gate_checked_at_ms"], 1000)
                self.assertEqual(frozen["gate_price"], 100.0)
                self.assertEqual(frozen["route"], "FLOW_ALIGNED")

    def test_state_round_trip_keeps_frozen_t0(self):
        with tempfile.TemporaryDirectory() as td:
            db = str(Path(td) / "ptl1.sqlite3")
            with patch.dict(
                os.environ,
                {"BABABOT_DB_PATH": db, "DATABASE_URL": ""},
                clear=False,
            ):
                _INITIALIZED.clear()
                first = _save_state(
                    signal_id="TEST:1:LONG",
                    gate_checked_at_ms=1000,
                    gate_price=100.0,
                    route="FLOW_ALIGNED",
                    router_probability=0.9,
                    status="WAIT",
                    terminal_reason=None,
                    t0_features={"x": 1.0},
                    gate={"checked_at_ms": 1000, "snapshot": {"current_price": 100.0}},
                )
                self.assertEqual(first["t0_features"], {"x": 1.0})
                _save_state(
                    signal_id="TEST:1:LONG",
                    gate_checked_at_ms=9999,
                    gate_price=999.0,
                    route="COUNTERFLOW",
                    router_probability=0.1,
                    status="ENTER",
                    terminal_reason="test",
                    t0_features={"x": 999.0},
                    gate={"checked_at_ms": 9999},
                    last_temporal_horizon=1,
                    last_temporal_return_pct=0.2,
                )
                got = get_stage3c7a_state("TEST:1:LONG")
                self.assertIsNotNone(got)
                # ON CONFLICT intentionally updates only mutable lifecycle fields.
                self.assertEqual(got["gate_checked_at_ms"], 1000)
                self.assertEqual(got["gate_price"], 100.0)
                self.assertEqual(got["route"], "FLOW_ALIGNED")
                self.assertEqual(got["t0_features"], {"x": 1.0})
                self.assertEqual(got["status"], "ENTER")
                self.assertEqual(got["last_temporal_horizon"], 1)


if __name__ == "__main__":
    unittest.main()