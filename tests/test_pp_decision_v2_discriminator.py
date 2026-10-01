from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from market_radar.profit_discriminator_v2 import (
    _STATE_CACHE,
    _STORE_READY,
    evaluate_stage5_discriminator,
)


def result(*, base: str = "HOLD", final: str = "REDUCE", giveback: float = 0.40) -> dict:
    return {
        "base_v1_action": base,
        "final_action": final,
        "fast_gate": "FAST_FORCE_PROTECT",
        "giveback_ratio": giveback,
        "danger_score": 0,
    }


class PPDecisionV2Stage5DiscriminatorTests(unittest.TestCase):
    def setUp(self) -> None:
        _STATE_CACHE.clear()
        _STORE_READY.clear()

    def env(self, db: str) -> dict[str, str]:
        return {
            "DATABASE_URL": "",
            "BABABOT_DB_PATH": db,
            "PP_DECISION_V2_STAGE5_DISCRIMINATOR_ENABLED": "true",
            "PP_DECISION_V2_STAGE5_START_MS": "900000",
        }

    def test_disabled_is_noop(self) -> None:
        with patch.dict(os.environ, {"PP_DECISION_V2_STAGE5_DISCRIMINATOR_ENABLED": "false"}, clear=False):
            out = evaluate_stage5_discriminator(
                position_id="P0", opened_at_ms=900001, evaluated_at_ms=1_000_000,
                mfe_pct=.75, current_pnl_pct=.50, v2_result=result(),
            )
        self.assertIsNone(out)

    def test_strict_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, self.env(os.path.join(tmp, "d.sqlite")), clear=False):
                out = evaluate_stage5_discriminator(
                    position_id="P0", opened_at_ms=900000, evaluated_at_ms=1_000_000,
                    mfe_pct=.75, current_pnl_pct=.50, v2_result=result(),
                )
        self.assertIsNone(out)

    def test_non_actionable_does_not_start_watch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, self.env(os.path.join(tmp, "d.sqlite")), clear=False):
                out = evaluate_stage5_discriminator(
                    position_id="P1", opened_at_ms=900001, evaluated_at_ms=1_000_000,
                    mfe_pct=.75, current_pnl_pct=.50, v2_result=result(final="HOLD"),
                )
        self.assertIsNone(out)

    def test_actionable_sub1_starts_watch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "d.sqlite")
            with patch.dict(os.environ, self.env(db), clear=False):
                out = evaluate_stage5_discriminator(
                    position_id="P2", opened_at_ms=900001, evaluated_at_ms=1_000_000,
                    mfe_pct=.75, current_pnl_pct=.50, v2_result=result(),
                )
                with sqlite3.connect(db) as conn:
                    row = conn.execute("select status from pp_decision_v2_discriminator where position_id='P2'").fetchone()
        self.assertEqual(out["status"], "WATCHING")
        self.assertEqual(row, ("WATCHING",))

    def test_failure_likely_after_30_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "d.sqlite")
            with patch.dict(os.environ, self.env(db), clear=False):
                evaluate_stage5_discriminator(
                    position_id="PF", opened_at_ms=900001, evaluated_at_ms=1_000_000,
                    mfe_pct=.75, current_pnl_pct=.50, v2_result=result(),
                )
                out = evaluate_stage5_discriminator(
                    position_id="PF", opened_at_ms=900001, evaluated_at_ms=1_031_000,
                    mfe_pct=.82, current_pnl_pct=.10, v2_result=result(final="HOLD"),
                )
        self.assertEqual(out["status"], "FAILURE_LIKELY")
        self.assertEqual(out["confidence"], "HIGH")

    def test_transient_likely_requires_strong_initial_and_followup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "d.sqlite")
            with patch.dict(os.environ, self.env(db), clear=False):
                evaluate_stage5_discriminator(
                    position_id="PT", opened_at_ms=900001, evaluated_at_ms=1_000_000,
                    mfe_pct=.75, current_pnl_pct=.50, v2_result=result(base="HOLD"),
                )
                out = evaluate_stage5_discriminator(
                    position_id="PT", opened_at_ms=900001, evaluated_at_ms=1_031_000,
                    mfe_pct=.90, current_pnl_pct=.35, v2_result=result(final="HOLD"),
                )
        self.assertEqual(out["status"], "TRANSIENT_LIKELY")
        self.assertEqual(out["confidence"], "MEDIUM_HIGH")

    def test_ambiguous_middle_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "d.sqlite")
            with patch.dict(os.environ, self.env(db), clear=False):
                evaluate_stage5_discriminator(
                    position_id="PA", opened_at_ms=900001, evaluated_at_ms=1_000_000,
                    mfe_pct=.62, current_pnl_pct=.30, v2_result=result(base="HOLD"),
                )
                out = evaluate_stage5_discriminator(
                    position_id="PA", opened_at_ms=900001, evaluated_at_ms=1_031_000,
                    mfe_pct=.80, current_pnl_pct=.25, v2_result=result(final="HOLD"),
                )
        self.assertEqual(out["status"], "AMBIGUOUS")
        self.assertEqual(out["confidence"], "LOW")

    def test_crossing_one_percent_is_confirmed_transient(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "d.sqlite")
            with patch.dict(os.environ, self.env(db), clear=False):
                evaluate_stage5_discriminator(
                    position_id="PC", opened_at_ms=900001, evaluated_at_ms=1_000_000,
                    mfe_pct=.80, current_pnl_pct=.55, v2_result=result(),
                )
                out = evaluate_stage5_discriminator(
                    position_id="PC", opened_at_ms=900001, evaluated_at_ms=1_015_000,
                    mfe_pct=1.02, current_pnl_pct=.82, v2_result=result(final="HOLD"),
                )
        self.assertEqual(out["status"], "TRANSIENT_CONFIRMED")
        self.assertEqual(out["confidence"], "CONFIRMED")

    def test_does_not_mutate_v2_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "d.sqlite")
            payload = result(base="HOLD", final="REDUCE")
            original = dict(payload)
            with patch.dict(os.environ, self.env(db), clear=False):
                evaluate_stage5_discriminator(
                    position_id="PM", opened_at_ms=900001, evaluated_at_ms=1_000_000,
                    mfe_pct=.80, current_pnl_pct=.55, v2_result=payload,
                )
            self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
