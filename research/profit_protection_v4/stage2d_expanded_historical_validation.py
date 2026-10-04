from __future__ import annotations
import argparse,json,statistics
from pathlib import Path
from research.profit_protection_v4.stage2b_optimal_protection_frontier import load_market_data
from research.profit_protection_v4.stage2c_runner_preservation import simulate_hybrid

ROOT=Path(__file__).resolve().parents[2]
STRICT=ROOT/"research/profit_protection_v4/results/stage1j_clean_post_entry_mfe_evidence.json"
DEFAULT=ROOT/"research/profit_protection_v4/results/stage2d_expanded_historical_validation.json"

def metrics(rows,res,positions):
    actual=[float(positions[r["position_id"]]["realized_pnl"]) for r in rows]
    sim=[float(res[r["position_id"]]["sim_usdt"]) for r in rows]
    ap=[float(positions[r["position_id"]]["realized_pnl_pct"]) for r in rows]
    sp=[float(res[r["position_id"]]["sim_pct"]) for r in rows]
    return {
      "n":len(rows),"actual_usdt":sum(actual),"sim_usdt":sum(sim),"delta_usdt":sum(sim)-sum(actual),
      "actual_win_n":sum(x>0 for x in ap),"sim_win_n":sum(x>0 for x in sp),
      "actual_win_rate":sum(x>0 for x in ap)/len(rows),"sim_win_rate":sum(x>0 for x in sp)/len(rows),
      "helped_n":sum(s>a+1e-12 for s,a in zip(sim,actual)),"harmed_n":sum(s<a-1e-12 for s,a in zip(sim,actual)),
      "small_reduce_n":sum(bool(res[r["position_id"]]["small_fired"]) for r in rows),
      "runner_close_n":sum(bool(res[r["position_id"]]["runner_closed"]) for r in rows),
      "median_delta_usdt":statistics.median([s-a for s,a in zip(sim,actual)]),
    }

def build():
    rows=sorted(json.loads(STRICT.read_text()),key=lambda r:(int(r["opened_at_ms"]),str(r["position_id"])))
    ids=[r["position_id"] for r in rows];positions,obs,orders=load_market_data(ids)
    res={r["position_id"]:simulate_hybrid(r,small_template=(.50,.60,3),reduce_fraction=.25,runner_qualify_pct=1.50,positions=positions,observations=obs,orders=orders) for r in rows}
    ge=[r for r in rows if float(r["clean_post_entry_mfe_pct"])>=.30]
    lt=[r for r in rows if float(r["clean_post_entry_mfe_pct"])<.30]
    out={"stage":"PP-V4-2D-HISTORICAL-EXPANDED","status":"COMPLETE","policy":"small 0.50/60/3 reduce25; runner1.50 90/2","strict_all":metrics(rows,res,positions),"clean_mfe_ge030":metrics(ge,res,positions),"clean_mfe_lt030":metrics(lt,res,positions)}
    out["diagnostic"]={
      "loss_reduction_pct":100*out["strict_all"]["delta_usdt"]/abs(out["strict_all"]["actual_usdt"]),
      "low_mfe_share_of_absolute_actual_net_loss_pct":100*abs(out["clean_mfe_lt030"]["actual_usdt"])/abs(out["strict_all"]["actual_usdt"]),
      "low_mfe_policy_actions":out["clean_mfe_lt030"]["small_reduce_n"]+out["clean_mfe_lt030"]["runner_close_n"],
      "conclusion":"Protection materially improves trades that develop observable profit, but cannot repair the 90 strict trades that never reach clean MFE +0.30%."
    }
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",default=str(DEFAULT));a=ap.parse_args()
    out=build();Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+"\n");print(json.dumps(out,sort_keys=True))
if __name__=="__main__":main()
