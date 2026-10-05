from __future__ import annotations

import json
import os
import time
import unittest
from unittest.mock import patch

import market_radar.paper_trading as paper
import market_radar.profit_protection_v4_observer as observer


class FakeObserverClient:
    def __init__(self, prices):
        self.prices = prices

    def ticker_prices(self):
        return dict(self.prices)


class FakePaperClient:
    def __init__(self, price=100.0):
        self.price = float(price)

    def ticker_price(self, symbol):
        return self.price


class ParallelProtectionShadowPS5AWiringTests(unittest.TestCase):
    def observer_position(self):
        return {
            "position_id": "PAPER:WIRE-OBS",
            "signal_id": "WIRE-OBS",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "entry_price": 100.0,
            "quantity": 5.0,
            "opened_at_ms": 2_000,
            "status": "OPEN",
            "mode": "PAPER",
            "raw_json": json.dumps(
                {
                    "initial_quantity": 5.0,
                    "initial_notional_usdt": 500.0,
                }
            ),
        }

    @patch("market_radar.profit_protection_v4_observer.process_parallel_protection_shadow_sample")
    def test_observer_forwards_inserted_5s_sample_to_ps5a(self, shadow):
        shadow.return_value = {
            "status": "COMPLETE",
            "execution_authority": "NONE",
        }
        position = self.observer_position()
        saved_rows = []
        with patch.dict(
            os.environ,
            {
                "PP_V4_STAGE1_ENABLED": "true",
                "PP_V4_STAGE1_START_MS": "1000",
            },
            clear=False,
        ), patch.object(observer, "initialize_pp_v4_store"),              patch.object(observer, "_eligible_positions", return_value=[position]),              patch.object(observer, "_last_cycle_receive_ms", return_value=None),              patch.object(observer, "_state_for", return_value=None),              patch.object(
                 observer,
                 "_save_observation",
                 side_effect=lambda row: saved_rows.append(dict(row)) or True,
             ),              patch.object(observer, "_save_cycle"),              patch.object(
                 observer,
                 "process_stage2d_shadow_observation",
                 return_value={"status": "OK"},
             ):
            result = observer.process_pp_v4_cycle(
                client=FakeObserverClient({"BTCUSDT": 100.5}),
                started_at_ms=10_000,
            )

        self.assertEqual(result["status"], "COMPLETE")
        shadow.assert_called_once()
        args, kwargs = shadow.call_args
        self.assertEqual(args[0]["position_id"], "PAPER:WIRE-OBS")
        self.assertEqual(kwargs["current_price"], 100.5)
        self.assertEqual(kwargs["cycle_id"], "PPV4:10000")
        self.assertIsInstance(kwargs["observed_at_ms"], int)
        self.assertEqual(
            result["rows"][0]["parallel_protection_shadow"]["status"],
            "COMPLETE",
        )

    @patch("market_radar.profit_protection_v4_observer.process_parallel_protection_shadow_sample")
    def test_observer_shadow_failure_is_isolated(self, shadow):
        shadow.side_effect = RuntimeError("shadow down")
        position = self.observer_position()
        with patch.dict(
            os.environ,
            {
                "PP_V4_STAGE1_ENABLED": "true",
                "PP_V4_STAGE1_START_MS": "1000",
            },
            clear=False,
        ), patch.object(observer, "initialize_pp_v4_store"),              patch.object(observer, "_eligible_positions", return_value=[position]),              patch.object(observer, "_last_cycle_receive_ms", return_value=None),              patch.object(observer, "_state_for", return_value=None),              patch.object(observer, "_save_observation", return_value=True),              patch.object(observer, "_save_cycle"),              patch.object(
                 observer,
                 "process_stage2d_shadow_observation",
                 return_value={"status": "OK"},
             ):
            result = observer.process_pp_v4_cycle(
                client=FakeObserverClient({"BTCUSDT": 100.5}),
                started_at_ms=10_001,
            )

        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["observed_positions"], 1)
        self.assertEqual(
            result["rows"][0]["parallel_protection_shadow"]["status"],
            "ERROR_FAIL_ISOLATED",
        )

    @patch("market_radar.paper_trading.register_protection_shadow_position")
    @patch("market_radar.paper_trading.get_position")
    @patch("market_radar.paper_trading.mark_order")
    @patch("market_radar.paper_trading.create_position")
    @patch("market_radar.paper_trading.has_open_paper_symbol", return_value=False)
    @patch("market_radar.paper_trading._at_open_capacity", return_value=False)
    def test_paper_open_registers_shadow_after_source_fill(
        self,
        capacity,
        open_symbol,
        create_position,
        mark_order,
        get_position,
        shadow_register,
    ):
        now_ms = int(time.time() * 1000)
        order = {
            "order_id": "O-OPEN",
            "position_id": "PAPER:WIRE-OPEN",
            "signal_id": "WIRE-OPEN",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "payload_json": json.dumps(
                {
                    "stage11c_checked_at_ms": now_ms,
                    "stage11c_version": "v1",
                    "stage11c_snapshot": {},
                }
            ),
        }
        created = {
            "position_id": "PAPER:WIRE-OPEN",
            "signal_id": "WIRE-OPEN",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "mode": "PAPER",
            "status": "OPEN",
            "opened_at_ms": now_ms,
            "entry_price": 100.02,
            "quantity": 4.999,
            "raw_json": "{}",
        }
        get_position.return_value = created
        shadow_register.return_value = {
            "status": "REGISTERED",
            "execution_authority": "NONE",
        }
        with patch.dict(
            os.environ,
            {
                "PAPER_NOTIONAL_USDT": "500",
                "PAPER_FEE_RATE": "0.00075",
                "PAPER_SLIPPAGE_BPS": "2",
            },
            clear=False,
        ):
            out = paper._execute_open(FakePaperClient(100.0), order)

        self.assertEqual(out["status"], "FILLED")
        create_position.assert_called_once()
        mark_order.assert_called_once()
        shadow_register.assert_called_once_with(created)
        self.assertEqual(out["shadow_runtime"]["status"], "REGISTERED")

    @patch("market_radar.paper_trading.register_protection_shadow_position")
    @patch("market_radar.paper_trading.get_position")
    @patch("market_radar.paper_trading.mark_order")
    @patch("market_radar.paper_trading.create_position")
    @patch("market_radar.paper_trading.has_open_paper_symbol", return_value=False)
    @patch("market_radar.paper_trading._at_open_capacity", return_value=False)
    def test_paper_open_shadow_failure_does_not_roll_back_source_fill(
        self,
        capacity,
        open_symbol,
        create_position,
        mark_order,
        get_position,
        shadow_register,
    ):
        now_ms = int(time.time() * 1000)
        order = {
            "order_id": "O-OPEN-FAIL",
            "position_id": "PAPER:WIRE-FAIL",
            "signal_id": "WIRE-FAIL",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "payload_json": json.dumps({"stage11c_checked_at_ms": now_ms}),
        }
        get_position.return_value = {
            "position_id": "PAPER:WIRE-FAIL",
            "mode": "PAPER",
        }
        shadow_register.side_effect = RuntimeError("shadow registration fail")

        out = paper._execute_open(FakePaperClient(100.0), order)

        self.assertEqual(out["status"], "FILLED")
        create_position.assert_called_once()
        mark_order.assert_called_once()
        self.assertEqual(out["shadow_runtime"]["status"], "ERROR_FAIL_ISOLATED")

    @patch("market_radar.paper_trading.process_protection_shadow_source_lifecycle")
    @patch("market_radar.paper_trading.mark_order")
    @patch("market_radar.paper_trading.update_position_reduce")
    @patch("market_radar.paper_trading.get_position")
    def test_paper_reduce_forwards_actual_fill_to_shadow(
        self,
        get_position,
        update_reduce,
        mark_order,
        shadow_lifecycle,
    ):
        position = {
            "position_id": "PAPER:WIRE-EXIT",
            "signal_id": "WIRE-EXIT",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "mode": "PAPER",
            "status": "OPEN",
            "entry_price": 100.0,
            "quantity": 5.0,
            "raw_json": json.dumps(
                {
                    "initial_quantity": 5.0,
                    "initial_notional_usdt": 500.0,
                    "entry_fee_total": 0.05,
                    "allocated_entry_fee": 0.0,
                    "exit_fees": 0.0,
                    "realized_gross": 0.0,
                    "realized_net": 0.0,
                    "closed_quantity": 0.0,
                }
            ),
        }
        get_position.return_value = position
        order = {
            "order_id": "O-REDUCE",
            "position_id": position["position_id"],
            "action": "REDUCE",
            "requested_quantity": 2.5,
            "reason": "stage12_reduce",
        }
        shadow_lifecycle.return_value = {
            "status": "COMPLETE",
            "execution_authority": "NONE",
        }
        out = paper._execute_exit(FakePaperClient(101.0), order)

        self.assertEqual(out["status"], "FILLED")
        update_reduce.assert_called_once()
        mark_order.assert_called_once()
        shadow_lifecycle.assert_called_once()
        kwargs = shadow_lifecycle.call_args.kwargs
        self.assertEqual(kwargs["action"], "REDUCE")
        self.assertAlmostEqual(kwargs["executed_quantity"], 2.5)
        self.assertEqual(kwargs["market_price"], 101.0)
        self.assertEqual(kwargs["source_event_id"], "paper:O-REDUCE:REDUCE")
        self.assertEqual(out["shadow_runtime"]["status"], "COMPLETE")

    @patch("market_radar.paper_trading.process_protection_shadow_source_lifecycle")
    @patch("market_radar.paper_trading.mark_order")
    @patch("market_radar.paper_trading.update_position_reduce")
    @patch("market_radar.paper_trading.get_position")
    def test_paper_exit_shadow_failure_is_isolated(
        self,
        get_position,
        update_reduce,
        mark_order,
        shadow_lifecycle,
    ):
        position = {
            "position_id": "PAPER:WIRE-EXIT-FAIL",
            "signal_id": "WIRE-EXIT-FAIL",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "mode": "PAPER",
            "status": "OPEN",
            "entry_price": 100.0,
            "quantity": 5.0,
            "raw_json": json.dumps(
                {
                    "initial_quantity": 5.0,
                    "initial_notional_usdt": 500.0,
                    "entry_fee_total": 0.05,
                }
            ),
        }
        get_position.return_value = position
        shadow_lifecycle.side_effect = RuntimeError("shadow lifecycle fail")
        order = {
            "order_id": "O-REDUCE-FAIL",
            "position_id": position["position_id"],
            "action": "REDUCE",
            "requested_quantity": 2.5,
            "reason": "stage12_reduce",
        }

        out = paper._execute_exit(FakePaperClient(101.0), order)

        self.assertEqual(out["status"], "FILLED")
        update_reduce.assert_called_once()
        mark_order.assert_called_once()
        self.assertEqual(out["shadow_runtime"]["status"], "ERROR_FAIL_ISOLATED")


if __name__ == "__main__":
    unittest.main()
