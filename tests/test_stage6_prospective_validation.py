[Reading 408 lines from start (total: 408 lines, 0 remaining)]

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_radar.stage6_validation import (
    DISCOVERY_CUTOFF_MS,
    POLICIES,
    _adaptive_lock,
    _evaluate_lane,
    _v5_sub1_decision,
    finalize_stage6_position,
    process_stage6_shadow_cycle,
    register_stage6_position,
    stage6_summary,
)


def _kline(open_ms: int, close_ms: int, price: float, *, volume: float = 100.0, taker_share: float = 0.5):
    return [
        open_ms,
        str(price),
        str(price * 1.001),
        str(price * 0.999),
        str(price),
        str(volume),
        close_ms,
        "0",
        100,
        str(volume * taker_share),
        "0",
        "0",
    ]


class FakeClient:
    def __init__(self, *, now_ms: int, klines: list[list], oi_rows: list[dict]):
        self._now_ms = now_ms
        self._klines = klines
        self._oi_rows = oi_rows

    def server_time_ms(self) -> int:
        return self._now_ms

    def klines(self, symbol: str, interval: str = "1m", limit: int = 1000):
        self.last_symbol = symbol
        self.last_interval = interval
        self.last_limit = limit
        return list(self._klines)

    def open_interest_hist(self, symbol: str, period: str = "5m", limit: int = 500):
        return list(self._oi_rows)


class Stage6ProspectiveValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "radar.sqlite3"
        self.start = DISCOVERY_CUTOFF_MS + 1000
        self.env = patch.dict(
            os.environ,
            {
                "BABABOT_DB_PATH": str(self.db),
                "DATABASE_URL": "",
                "STAGE6_VALIDATION_ENABLED": "true",
                "STAGE6_START_MS": str(self.start),
                "STAGE6_RUN_ID": "test-stage6",
                "V5_0_SHADOW_ENABLED": "true",
                "V5_0_START_MS": str(self.start),
                "PAPER_FEE_RATE": "0.00075",
                "PAPER_SLIPPAGE_BPS": "2",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _register(self, *, opened_at_ms: int | None = None) -> bool:
        return register_stage6_position(
            position_id="PAPER:TEST:1",
            signal_id="TEST:1",
            symbol="TESTUSDT",
            side="LONG",
            opened_at_ms=opened_at_ms or self.start + 1,
            entry_price=100.0,
            initial_quantity=5.0,
            initial_notional=500.0,
            entry_fee_total=0.375,
        )

    def test_policy_contract_is_frozen_to_stage5_frontier(self):
        self.assertEqual(POLICIES["S5-A"]["base2"], 0.25)
        self.assertEqual(POLICIES["S5-A"]["base3"], 0.50)
        self.assertEqual(POLICIES["S5-A"]["tight2"], 0.30)
        self.assertEqual(POLICIES["S5-A"]["oi_tight"], 0.125)
        self.assertEqual(POLICIES["S5-A"]["vol_mod"], 0.025)
        self.assertEqual(POLICIES["S5-B"]["tight3"], 0.20)
        self.assertEqual(POLICIES["S5-C"]["tight3"], 0.05)
        self.assertEqual(POLICIES["STATIC_NET"]["arm_roi_pct"], 5.0)
        self.assertEqual(POLICIES["STATIC_BALANCED"]["lock_ratio"], 0.70)
        self.assertEqual(POLICIES["STATIC_CAPTURE"]["mode"], "REDUCE_THEN_CLOSE")
        self.assertEqual(POLICIES["V5-0"]["arm_min_roi_pct"], 0.50)
        self.assertEqual(POLICIES["V5-0"]["handoff_roi_pct"], 1.00)
        self.assertEqual(POLICIES["V5-0"]["decision_giveback_ratio"], 0.50)
        self.assertEqual(POLICIES["V5-0"]["close_score"], 4)

    def test_only_entries_strictly_after_stage6_start_are_registered(self):
        self.assertFalse(self._register(opened_at_ms=self.start))
        self.assertTrue(self._register(opened_at_ms=self.start + 1))
        self.assertFalse(self._register(opened_at_ms=self.start + 2))  # same position id, idempotent

        with sqlite3.connect(self.db) as conn:
            trades = conn.execute("select count(*) from stage6_validation_trades").fetchone()[0]
            lanes = conn.execute("select count(*) from stage6_validation_lanes").fetchone()[0]
        self.assertEqual(trades, 1)
        self.assertEqual(lanes, len(POLICIES))

    def test_adaptive_lock_uses_stage4_evidence_stack(self):
        base = _adaptive_lock(
            POLICIES["S5-A"],
            3.0,
            {
                "core_count": 0,
                "oi_adverse": 0,
                "vol_extreme": 0,
            },
        )
        tightened = _adaptive_lock(
            POLICIES["S5-A"],
            3.0,
            {
                "core_count": 2,
                "oi_adverse": 1,
                "vol_extreme": 1,
            },
        )
        self.assertAlmostEqual(base, 0.25)
        self.assertAlmostEqual(tightened, 0.70)

    def test_profit_floor_ratchets_and_close_first_executes(self):
        trade = {
            "side": "LONG",
            "entry_price": 100.0,
            "initial_quantity": 5.0,
            "initial_notional": 500.0,
            "entry_fee_total": 0.375,
        }
        lane = {
            "policy_id": "S5-A",
            "status": "OPEN",
            "remaining_quantity": 5.0,
            "realized_gross": 0.0,
            "realized_net": 0.0,
            "allocated_entry_fee": 0.0,
            "exit_fees": 0.0,
            "policy_peak_pnl": 0.0,
            "policy_peak_at_ms": None,
            "profit_floor": None,
            "action_count": 0,
            "trigger_count": 0,
            "closed_at_ms": None,
            "exit_price": None,
            "close_reason": None,
        }
        first, ev1 = _evaluate_lane(
            trade=trade,
            lane=lane,
            feature={
                "candle_close_ms": 1_000_000,
                "close": 103.0,
                "side_ret3": 0.5,
                "taker_strength": 0.10,
                "micro_against": False,
                "oi_change": 0.02,
                "rv15": 0.10,
            },
        )
        self.assertEqual(first["status"], "OPEN")
        self.assertEqual(ev1["action"], "HOLD")
        floor1 = first["profit_floor"]
        self.assertIsNotNone(floor1)

        second, ev2 = _evaluate_lane(
            trade=trade,
            lane=first,
            feature={
                "candle_close_ms": 1_240_000,
                "close": 101.0,
                "side_ret3": -0.30,
                "taker_strength": -0.10,
                "micro_against": True,
                "oi_change": 0.10,
                "rv15": 0.25,
            },
        )
        self.assertGreaterEqual(second["profit_floor"], floor1)
        self.assertEqual(ev2["action"], "CLOSE")
        self.assertEqual(second["status"], "CLOSED")
        self.assertEqual(second["remaining_quantity"], 0.0)

    def test_v5_sub1_decision_gate_contract(self):
        policy = POLICIES["V5-0"]
        base_ev = {"danger_score": 0}

        action, meta = _v5_sub1_decision(
            policy, peak_roi=0.80, economic=3.2, peak=4.0,
            evidence=base_ev, status="OPEN",
        )
        self.assertEqual(action, "HOLD")
        self.assertEqual(meta["gate"], "ARMED_SUB1")

        action, meta = _v5_sub1_decision(
            policy, peak_roi=0.80, economic=2.4, peak=4.0,
            evidence={"danger_score": 4}, status="OPEN",
        )
        self.assertEqual(action, "REDUCE")
        self.assertEqual(meta["gate"], "WATCH")

        action, meta = _v5_sub1_decision(
            policy, peak_roi=0.80, economic=1.8, peak=4.0,
            evidence={"danger_score": 2}, status="OPEN",
        )
        self.assertEqual(action, "REDUCE")
        self.assertEqual(meta["gate"], "MANDATORY_DECISION")

        action, meta = _v5_sub1_decision(
            policy, peak_roi=0.80, economic=1.8, peak=4.0,
            evidence={"danger_score": 4}, status="OPEN",
        )
        self.assertEqual(action, "CLOSE")

        action, meta = _v5_sub1_decision(
            policy, peak_roi=0.80, economic=0.0, peak=4.0,
            evidence={"danger_score": 0}, status="OPEN",
        )
        self.assertEqual(action, "CLOSE")
        self.assertEqual(meta["gate"], "HARD_STOP")

        action, meta = _v5_sub1_decision(
            policy, peak_roi=1.05, economic=3.0, peak=5.25,
            evidence={"danger_score": 6}, status="OPEN",
        )
        self.assertEqual(action, "HOLD")
        self.assertEqual(meta["gate"], "HANDOFF_GE1")

    def test_v5_sub1_lane_executes_reduce_then_close(self):
        trade = {
            "side": "LONG",
            "entry_price": 100.0,
            "initial_quantity": 5.0,
            "initial_notional": 500.0,
            "entry_fee_total": 0.375,
        }
        lane = {
            "policy_id": "V5-0",
            "status": "OPEN",
            "remaining_quantity": 5.0,
            "realized_gross": 0.0,
            "realized_net": 0.0,
            "allocated_entry_fee": 0.0,
            "exit_fees": 0.0,
            "policy_peak_pnl": 0.0,
            "policy_peak_at_ms": None,
            "profit_floor": None,
            "action_count": 0,
            "trigger_count": 0,
            "closed_at_ms": None,
            "exit_price": None,
            "close_reason": None,
        }
        peak, _ = _evaluate_lane(
            trade=trade, lane=lane,
            feature={
                "candle_close_ms": 1_000_000, "close": 100.95,
                "side_ret3": 0.20, "taker_strength": 0.10,
                "micro_against": False, "oi_change": 0.0, "rv15": 0.05,
            },
        )
        reduced, ev = _evaluate_lane(
            trade=trade, lane=peak,
            feature={
                "candle_close_ms": 1_060_000, "close": 100.65,
                "side_ret3": -0.20, "taker_strength": -0.10,
                "micro_against": True, "oi_change": 0.0, "rv15": 0.05,
            },
        )
        self.assertEqual(ev["evidence"]["gate"], "WATCH")
        self.assertEqual(ev["action"], "REDUCE")
        self.assertEqual(reduced["status"], "REDUCED")
        self.assertAlmostEqual(reduced["remaining_quantity"], 2.5)

        closed, ev2 = _evaluate_lane(
            trade=trade, lane=reduced,
            feature={
                "candle_close_ms": 1_120_000, "close": 100.20,
                "side_ret3": -0.30, "taker_strength": -0.10,
                "micro_against": True, "oi_change": 0.10, "rv15": 0.05,
            },
        )
        self.assertEqual(ev2["action"], "CLOSE")
        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(closed["close_reason"], "V5_SUB1_DECISION_GATE")

    def test_closed_1m_shadow_cycle_and_v3_censor_are_persisted(self):
        self.assertTrue(self._register())
        opened = self.start + 1
        base = opened - (opened % 60_000)
        prices = [100.2, 100.8, 101.5, 102.8, 102.0, 101.2]
        klines = []
        for i, px in enumerate(prices):
            open_ms = base + i * 60_000
            close_ms = open_ms + 59_999
            klines.append(
                _kline(
                    open_ms,
                    close_ms,
                    px,
                    taker_share=0.60 if i < 4 else 0.35,
                )
            )
        oi_rows = [
            {"timestamp": base, "sumOpenInterest": "1000"},
            {"timestamp": base + 300_000, "sumOpenInterest": "1002"},
        ]
        client = FakeClient(
            now_ms=klines[-1][6] + 1,
            klines=klines,
            oi_rows=oi_rows,
        )
        result = process_stage6_shadow_cycle(client)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertGreater(result["processed_candles"], 0)
        self.assertEqual(result["errors"], [])

        with sqlite3.connect(self.db) as conn:
            event_count = conn.execute(
                "select count(*) from stage6_validation_events"
            ).fetchone()[0]
            last_candle = conn.execute(
                "select last_candle_close_ms from stage6_validation_trades"
            ).fetchone()[0]
        self.assertGreater(event_count, 0)
        self.assertEqual(last_candle, klines[-1][6])

        self.assertTrue(
            finalize_stage6_position(
                position_id="PAPER:TEST:1",
                closed_at_ms=klines[-1][6] + 10_000,
                actual_exit_price=101.0,
                actual_realized_pnl=4.0,
                actual_realized_pnl_pct=0.8,
                actual_close_reason="stage12_close",
            )
        )
        summary = stage6_summary()
        self.assertEqual(summary["registered_trades"], 1)
        self.assertEqual(summary["closed_trades"], 1)
        self.assertEqual(summary["actual_v3"]["trades"], 1)
        self.assertAlmostEqual(summary["actual_v3"]["net_pnl"], 4.0)
        self.assertEqual(set(summary["policies"]), set(POLICIES))
        for item in summary["policies"].values():
            self.assertEqual(item["trades"], 1)

    def test_finalize_does_not_overwrite_policy_that_already_closed(self):
        self.assertTrue(self._register())
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                update stage6_validation_lanes
                set status='CLOSED', remaining_quantity=0,
                    realized_net=12.5, closed_at_ms=?, exit_price=104,
                    close_reason='POLICY_FLOOR'
                where policy_id='S5-A'
                """,
                (self.start + 120_000,),
            )
            conn.commit()

        self.assertTrue(
            finalize_stage6_position(
                position_id="PAPER:TEST:1",
                closed_at_ms=self.start + 300_000,
                actual_exit_price=101.0,
                actual_realized_pnl=3.0,
                actual_realized_pnl_pct=0.6,
                actual_close_reason="stage12_close",
            )
        )
        with sqlite3.connect(self.db) as conn:
            row = conn.execute(
                "select status,realized_net,exit_price,close_reason "
                "from stage6_validation_lanes where policy_id='S5-A'"
            ).fetchone()
        self.assertEqual(row[0], "CLOSED")
        self.assertAlmostEqual(row[1], 12.5)
        self.assertAlmostEqual(row[2], 104.0)
        self.assertEqual(row[3], "POLICY_FLOOR")


if __name__ == "__main__":
    unittest.main()

[executed on device: core-prod (c128f313-5bdb-41c3-a53a-0590e5cfa134)]