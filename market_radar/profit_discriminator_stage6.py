from __future__ import annotations
import json, os, threading, time
from typing import Any
from .persistence import _postgres_connect, _sqlite_connect, database_path, persistence_backend
from .profit_protection_v2 import evaluate_pp_decision_v2

STAGE6_DISCRIMINATOR_VERSION = "pp-decision-v2-stage6-prospective-validation"
_LOCK = threading.Lock()
_READY: set[tuple[str, str]] = set()

SQLITE_SCHEMA = """
create table if not exists pp_decision_v2_stage6_validation (
 position_id text primary key, opened_at_ms integer not null, closed_at_ms integer not null,
 classifier_status text not null, classifier_confidence text, predicted_outcome text not null,
 actual_outcome text not null, prediction_correct integer, watch_started_at_ms integer not null,
 initial_mfe_pct real not null, initial_current_pnl_pct real not null,
 max_mfe_after_watch real, min_pnl_after_watch real, actual_control_net real not null,
 stage3_net real not null, grace15_net real not null, grace30_net real not null,
 delta_grace15_vs_stage3 real not null, delta_grace30_vs_stage3 real not null,
 stage3_actions integer not null, grace15_actions integer not null, grace30_actions integer not null,
 created_at_ms integer not null
);
"""
POSTGRES_SCHEMA = SQLITE_SCHEMA.replace(" integer", " bigint").replace(" real", " double precision")

def stage6_discriminator_enabled() -> bool:
    return os.environ.get("PP_DECISION_V2_STAGE6_VALIDATION_ENABLED","false").strip().lower() in {"1","true","yes","on"}
def stage6_discriminator_start_ms() -> int:
    try:
        return int(os.environ.get("PP_DECISION_V2_STAGE6_START_MS","0") or 0)
    except (TypeError, ValueError):
        return 0

def _fee_rate() -> float:
    return max(0.0, min(float(os.environ.get("PAPER_FEE_RATE","0.0005")), .01))

def _slip() -> float:
    return max(0.0, min(float(os.environ.get("PAPER_SLIPPAGE_BPS","2")),100.0))/10000.0

def initialize_stage6_discriminator_store() -> None:
    backend=persistence_backend()
    key=(backend,str(database_path()) if backend=="sqlite" else "postgres")
    with _LOCK:
        if key in _READY:
            return
        if backend=="sqlite":
            with _sqlite_connect(database_path()) as c:
                c.executescript(SQLITE_SCHEMA)
        else:
            with _postgres_connect() as c:
                with c.cursor() as cur:
                    cur.execute(POSTGRES_SCHEMA)
        _READY.add(key)

def _exit_fill(side: str, market: float) -> float:
    return float(market)*(1-_slip() if str(side).upper()=="LONG" else 1+_slip())

def _gross(side: str, q: float, entry: float, exitp: float) -> float:
    return q*(exitp-entry) if str(side).upper()=="LONG" else q*(entry-exitp)
def _replay(position: dict[str,Any], obs: list[dict[str,Any]], grace_seconds: float) -> tuple[float,int]:
    raw=json.loads(position.get("raw_json") or "{}")
    side=str(position["side"]).upper()
    entry=float(position["entry_price"])
    iq=float(raw.get("initial_quantity") or 0.0)
    entry_fee=float(raw.get("entry_fee_total") or 0.0)
    rem, allocated, net, status, actions = iq, 0.0, 0.0, "OPEN", 0
    watch_started=None
    for o in obs:
        rr=evaluate_pp_decision_v2(
            mfe_pct=float(o["mfe_pct"]),
            current_pnl_pct=float(o["current_pnl_pct"]),
            previous_pnl_pct=None if o.get("previous_pnl_pct") is None else float(o["previous_pnl_pct"]),
            elapsed_seconds=None if o.get("elapsed_seconds") is None else float(o["elapsed_seconds"]),
            danger_score=int(o.get("danger_score") or 0),
            status=status,
        )
        action=str(rr["final_action"])
        mfe=float(o["mfe_pct"])
        if watch_started is None and .5 <= mfe < 1 and action in {"REDUCE","CLOSE"}:
            watch_started=int(o["evaluated_at_ms"])
        if watch_started is not None and grace_seconds>0:
            if int(o["evaluated_at_ms"]) < watch_started+int(grace_seconds*1000):
                continue
        if action not in {"REDUCE","CLOSE"} or rem<=0:
            continue
        px=_exit_fill(side,float(o["current_price"]))
        q=rem*.5 if action=="REDUCE" else rem
        ent=entry_fee*(q/iq) if action=="REDUCE" and iq>0 else max(0.0,entry_fee-allocated)
        fee=q*px*_fee_rate()
        net += _gross(side,q,entry,px)-ent-fee
        allocated += ent
        rem -= q
        actions += 1
        status="REDUCED" if action=="REDUCE" else "CLOSED"
        if status=="CLOSED":
            break
    if rem>0:
        px=float(position["exit_price"])
        ent=max(0.0,entry_fee-allocated)
        fee=rem*px*_fee_rate()
        net += _gross(side,rem,entry,px)-ent-fee
    return net, actions

def _fetch_position(cur: Any, position_id: str) -> dict[str,Any] | None:
    cur.execute("""select position_id,symbol,side,status,opened_at_ms,closed_at_ms,
                          entry_price,exit_price,realized_pnl,raw_json
                   from positions where position_id=%s""",(position_id,))
    row=cur.fetchone()
    if row is None:
        return None
    keys=["position_id","symbol","side","status","opened_at_ms","closed_at_ms",
          "entry_price","exit_price","realized_pnl","raw_json"]
    return dict(zip(keys,row))

def finalize_stage6_discriminator_position(position_id: str) -> bool:
    if not stage6_discriminator_enabled():
        return False
    initialize_stage6_discriminator_store()
    with _postgres_connect() as c:
        with c.cursor() as cur:
            p=_fetch_position(cur,position_id)
            if p is None or str(p["status"]).upper()!="CLOSED":
                return False
            if int(p["opened_at_ms"])<=stage6_discriminator_start_ms():
                return False
            cur.execute("""select status,confidence,watch_started_at_ms,
                                  initial_mfe_pct,initial_current_pnl_pct
                           from pp_decision_v2_discriminator where position_id=%s""",(position_id,))
            drow=cur.fetchone()
            if drow is None:
                return False
            cur.execute("select 1 from pp_decision_v2_stage6_validation where position_id=%s",(position_id,))
            if cur.fetchone() is not None:
                return False
            cur.execute("""select evaluated_at_ms,current_price,current_pnl_pct,mfe_pct,
                                  previous_pnl_pct,elapsed_seconds,danger_score
                           from pp_decision_v2_observations
                           where position_id=%s and evaluated_at_ms<=%s
                           order by evaluated_at_ms""",(position_id,int(p["closed_at_ms"])))
            cols=[x[0] for x in cur.description]
            obs=[dict(zip(cols,x)) for x in cur.fetchall()]
            if not obs:
                return False
            cls,conf,watch,m0,c0=drow
            watch=int(watch)
            post=[o for o in obs if int(o["evaluated_at_ms"])>=watch]
            maxm=max([float(o["mfe_pct"]) for o in post],default=float(m0))
            minp=min([float(o["current_pnl_pct"]) for o in post],default=float(c0))
            actual="RUNNER" if maxm>=1.0 else ("FAILURE" if minp<=0 or float(p["realized_pnl"] or 0)<=0 else "AMBIGUOUS")
            predicted="RUNNER" if str(cls) in {"TRANSIENT_LIKELY","TRANSIENT_CONFIRMED"} else (
                "FAILURE" if str(cls)=="FAILURE_LIKELY" else "UNRESOLVED"
            )
            correct=None if predicted=="UNRESOLVED" or actual=="AMBIGUOUS" else int(predicted==actual)
            s3,a3=_replay(p,obs,0)
            g15,a15=_replay(p,obs,15)
            g30,a30=_replay(p,obs,30)
            now=int(time.time()*1000)
            cur.execute("""insert into pp_decision_v2_stage6_validation(
                position_id,opened_at_ms,closed_at_ms,classifier_status,classifier_confidence,
                predicted_outcome,actual_outcome,prediction_correct,watch_started_at_ms,
                initial_mfe_pct,initial_current_pnl_pct,max_mfe_after_watch,min_pnl_after_watch,
                actual_control_net,stage3_net,grace15_net,grace30_net,
                delta_grace15_vs_stage3,delta_grace30_vs_stage3,
                stage3_actions,grace15_actions,grace30_actions,created_at_ms
            ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",(
                position_id,int(p["opened_at_ms"]),int(p["closed_at_ms"]),str(cls),conf,
                predicted,actual,correct,watch,float(m0),float(c0),maxm,minp,
                float(p["realized_pnl"] or 0),s3,g15,g30,g15-s3,g30-s3,a3,a15,a30,now
            ))
    return True
def process_stage6_discriminator_cycle() -> dict[str,Any]:
    if not stage6_discriminator_enabled():
        return {"status":"DISABLED","finalized":0,"errors":[]}
    initialize_stage6_discriminator_store()
    finalized, errors = 0, []
    with _postgres_connect() as c:
        with c.cursor() as cur:
            cur.execute("""select p.position_id from positions p
                join pp_decision_v2_discriminator d on d.position_id=p.position_id
                left join pp_decision_v2_stage6_validation v on v.position_id=p.position_id
                where p.status='CLOSED' and p.opened_at_ms>%s and v.position_id is null
                order by p.closed_at_ms limit 100""",(stage6_discriminator_start_ms(),))
            ids=[r[0] for r in cur.fetchall()]
    for pid in ids:
        try:
            finalized += int(finalize_stage6_discriminator_position(str(pid)))
        except Exception as exc:
            errors.append(f"{pid}: {type(exc).__name__}: {str(exc)[:180]}")
    return {"status":"COMPLETE","finalized":finalized,"errors":errors}

def stage6_discriminator_summary() -> dict[str,Any]:
    initialize_stage6_discriminator_store()
    with _postgres_connect() as c:
        with c.cursor() as cur:
            cur.execute("""select classifier_status,count(*),
                sum(case when prediction_correct=1 then 1 else 0 end),
                sum(case when prediction_correct is not null then 1 else 0 end),
                sum(stage3_net),sum(grace15_net),sum(grace30_net),
                sum(delta_grace15_vs_stage3),sum(delta_grace30_vs_stage3)
                from pp_decision_v2_stage6_validation group by classifier_status order by classifier_status""")
            rows=cur.fetchall()
            cur.execute("""select count(*),sum(stage3_net),sum(grace15_net),sum(grace30_net),
                                  sum(delta_grace15_vs_stage3),sum(delta_grace30_vs_stage3)
                           from pp_decision_v2_stage6_validation""")
            total=cur.fetchone()
    by_status={}
    for s,n,ok,den,s3,g15,g30,d15,d30 in rows:
        by_status[str(s)]={
            "n":int(n),
            "precision_pct":None if not den else 100*int(ok or 0)/int(den),
            "stage3_net":float(s3 or 0),
            "grace15_net":float(g15 or 0),
            "grace30_net":float(g30 or 0),
            "delta15_vs_stage3":float(d15 or 0),
            "delta30_vs_stage3":float(d30 or 0),
        }
    return {
        "version":STAGE6_DISCRIMINATOR_VERSION,
        "enabled":stage6_discriminator_enabled(),
        "start_ms":stage6_discriminator_start_ms(),
        "authority":"NONE_SHADOW_VALIDATION",
        "trades":int(total[0] or 0),
        "stage3_net":float(total[1] or 0),
        "grace15_net":float(total[2] or 0),
        "grace30_net":float(total[3] or 0),
        "delta15_vs_stage3":float(total[4] or 0),
        "delta30_vs_stage3":float(total[5] or 0),
        "by_classifier_status":by_status,
    }