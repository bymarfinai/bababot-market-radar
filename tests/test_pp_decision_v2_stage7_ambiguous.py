from __future__ import annotations
import os, sqlite3, tempfile, unittest
from unittest.mock import patch

from market_radar.profit_discriminator_stage7 import (
    _READY, STAGE7_RECOVERY_MIN_PP, evaluate_stage7_ambiguous,
)

class PPDecisionV2Stage7AmbiguousTests(unittest.TestCase):
    def setUp(self) -> None:
        _READY.clear()

    def env(self, db: str) -> dict[str,str]:
        return {
            "DATABASE_URL":"",
            "BABABOT_DB_PATH":db,
            "PP_DECISION_V2_STAGE7_ENABLED":"true",
            "PP_DECISION_V2_STAGE7_START_MS":"900000",
        }

    def state(self, *, status="AMBIGUOUS", initial=.30, followup=.42) -> dict:
        return {
            "status":status,
            "classified_at_ms":1_030_000,
            "initial_mfe_pct":.65,
            "initial_current_pnl_pct":initial,
            "followup_mfe_pct":.70,
            "followup_current_pnl_pct":followup,
        }

    def test_disabled_is_noop(self) -> None:
        with patch.dict(os.environ, {"PP_DECISION_V2_STAGE7_ENABLED":"false"}, clear=False):
            out=evaluate_stage7_ambiguous(
                position_id="P0",opened_at_ms=900001,stage5_state=self.state()
            )
        self.assertIsNone(out)
    def test_strict_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ,self.env(os.path.join(tmp,"d.sqlite")),clear=False):
                out=evaluate_stage7_ambiguous(
                    position_id="P1",opened_at_ms=900000,stage5_state=self.state()
                )
        self.assertIsNone(out)

    def test_non_ambiguous_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ,self.env(os.path.join(tmp,"d.sqlite")),clear=False):
                out=evaluate_stage7_ambiguous(
                    position_id="P2",opened_at_ms=900001,
                    stage5_state=self.state(status="FAILURE_LIKELY"),
                )
        self.assertIsNone(out)

    def test_recovery_above_threshold_is_grace_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"d.sqlite")
            with patch.dict(os.environ,self.env(db),clear=False):
                out=evaluate_stage7_ambiguous(
                    position_id="P3",opened_at_ms=900001,
                    stage5_state=self.state(initial=.30,followup=.42),
                )
        self.assertEqual(out["decision"],"GRACE_CANDIDATE")
        self.assertAlmostEqual(out["recovery_pp"],.12)

    def test_recovery_below_threshold_is_protect_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"d.sqlite")
            with patch.dict(os.environ,self.env(db),clear=False):
                out=evaluate_stage7_ambiguous(
                    position_id="P4",opened_at_ms=900001,
                    stage5_state=self.state(initial=.30,followup=.36),
                )
        self.assertEqual(out["decision"],"PROTECT_CANDIDATE")
    def test_exact_threshold_is_grace_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"d.sqlite")
            with patch.dict(os.environ,self.env(db),clear=False):
                out=evaluate_stage7_ambiguous(
                    position_id="P5",opened_at_ms=900001,
                    stage5_state=self.state(initial=.30,followup=.40),
                )
        self.assertEqual(STAGE7_RECOVERY_MIN_PP,.10)
        self.assertEqual(out["decision"],"GRACE_CANDIDATE")

    def test_persists_one_row_per_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"d.sqlite")
            with patch.dict(os.environ,self.env(db),clear=False):
                for _ in range(2):
                    evaluate_stage7_ambiguous(
                        position_id="P6",opened_at_ms=900001,
                        stage5_state=self.state(initial=.20,followup=.35),
                    )
                with sqlite3.connect(db) as c:
                    row=c.execute(
                        "select count(*),decision from pp_decision_v2_stage7_ambiguous where position_id='P6'"
                    ).fetchone()
        self.assertEqual(row,(1,"GRACE_CANDIDATE"))

if __name__=="__main__":
    unittest.main()
