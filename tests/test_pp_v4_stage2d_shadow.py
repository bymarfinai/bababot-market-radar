from __future__ import annotations
import os,tempfile,unittest
from unittest.mock import patch
import market_radar.profit_protection_v4_stage2d_shadow as s

class PPV4Stage2DShadowTests(unittest.TestCase):
    def test_small_reduce_after_three_confirmations(self):
        st=s.ShadowState("P",1000)
        st,act,_=s.advance(st,.60,.60,2000);self.assertIsNone(act)
        st,act,_=s.advance(st,.30,.60,3000);self.assertIsNone(act)
        st,act,_=s.advance(st,.30,.60,4000);self.assertIsNone(act)
        st,act,_=s.advance(st,.30,.60,5000)
        self.assertEqual(act["action_type"],"SHADOW_REDUCE_25")
        self.assertAlmostEqual(st.remaining_fraction,.75)
        self.assertTrue(st.small_fired)

    def test_runner_preempts_small_and_closes_after_two(self):
        st=s.ShadowState("P",1000)
        st,act,_=s.advance(st,1.60,1.60,2000);self.assertTrue(st.runner_qualified);self.assertIsNone(act)
        st,act,_=s.advance(st,1.40,1.60,3000);self.assertIsNone(act)
        st,act,_=s.advance(st,1.30,1.60,4000)
        self.assertEqual(act["action_type"],"SHADOW_CLOSE_REMAINDER")
        self.assertEqual(st.remaining_fraction,0.0);self.assertTrue(st.shadow_closed);self.assertFalse(st.small_fired)

    def test_duplicate_and_out_of_order_are_counted(self):
        st=s.ShadowState("P",1000,last_observed_at_ms=5000)
        st,_,status=s.advance(st,.1,.2,5000);self.assertEqual(status,"DUPLICATE");self.assertEqual(st.duplicate_count,1)
        st,_,status=s.advance(st,.1,.2,4000);self.assertEqual(status,"OUT_OF_ORDER");self.assertEqual(st.out_of_order_count,1)

    def test_sqlite_roundtrip_and_idempotent_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"s2d.sqlite3");s._READY.clear()
            env={"PP_V4_STAGE2D_SHADOW_ENABLED":"true","PP_V4_STAGE2D_START_MS":"1000"}
            with patch.dict(os.environ,env,clear=False),patch.object(s,"persistence_backend",return_value="sqlite"),patch.object(s,"database_path",return_value=db):
                row={"position_id":"P","opened_at_ms":2000,"observed_at_ms":3000,"observation_id":"O1","current_pnl_pct":.6,"running_observed_peak_pct":.6}
                self.assertEqual(s.process_observation(row)["status"],"OBSERVED")
                for i in range(3):
                    row={**row,"observed_at_ms":4000+i*1000,"observation_id":f"O{i+2}","current_pnl_pct":.3}
                    out=s.process_observation(row)
                self.assertEqual(out["action"],"SHADOW_REDUCE_25")
                sm=s.summary();self.assertEqual(sm["shadow_reduces"],1);self.assertEqual(sm["authority"],"NONE")

if __name__=="__main__":unittest.main()
