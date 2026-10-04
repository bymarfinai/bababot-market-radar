from __future__ import annotations
import json,os,threading,time
from dataclasses import dataclass
from typing import Any
from .persistence import _postgres_connect,_sqlite_connect,database_path,persistence_backend

VERSION="pp-v4-stage2d-shadow-v1"
SMALL_ARM=.50; SMALL_RETAIN=.60; SMALL_CONFIRM=3; REDUCE_FRAC=.25
RUNNER_QUALIFY=1.50; RUNNER_RETAIN=.90; RUNNER_CONFIRM=2
_LOCK=threading.Lock(); _READY:set[tuple[str,str]]=set()

@dataclass(frozen=True)
class ShadowState:
    position_id:str
    opened_at_ms:int
    runner_qualified:bool=False
    small_fired:bool=False
    small_consecutive:int=0
    runner_consecutive:int=0
    remaining_fraction:float=1.0
    shadow_closed:bool=False
    last_observed_at_ms:int=0
    duplicate_count:int=0
    out_of_order_count:int=0
    invariant_error_count:int=0

SQLITE_SCHEMA="""
create table if not exists pp_v4_stage2d_shadow_state(
 position_id text primary key,opened_at_ms integer not null,runner_qualified integer not null,
 small_fired integer not null,small_consecutive integer not null,runner_consecutive integer not null,
 remaining_fraction real not null,shadow_closed integer not null,last_observed_at_ms integer not null,
 duplicate_count integer not null,out_of_order_count integer not null,invariant_error_count integer not null,
 updated_at_ms integer not null);
create table if not exists pp_v4_stage2d_shadow_actions(
 action_id text primary key,position_id text not null,observed_at_ms integer not null,
 action_type text not null,current_pnl_pct real not null,running_peak_pct real not null,
 action_fraction_of_remaining real not null,remaining_before real not null,remaining_after real not null,
 source_observation_id text not null,authority text not null,params_json text not null,created_at_ms integer not null);
create index if not exists idx_pp_v4_s2d_action_position_time on pp_v4_stage2d_shadow_actions(position_id,observed_at_ms);
"""
POSTGRES_SCHEMA="""
create table if not exists pp_v4_stage2d_shadow_state(
 position_id text primary key,opened_at_ms bigint not null,runner_qualified boolean not null,
 small_fired boolean not null,small_consecutive integer not null,runner_consecutive integer not null,
 remaining_fraction double precision not null,shadow_closed boolean not null,last_observed_at_ms bigint not null,
 duplicate_count integer not null,out_of_order_count integer not null,invariant_error_count integer not null,
 updated_at_ms bigint not null);
create table if not exists pp_v4_stage2d_shadow_actions(
 action_id text primary key,position_id text not null,observed_at_ms bigint not null,
 action_type text not null,current_pnl_pct double precision not null,running_peak_pct double precision not null,
 action_fraction_of_remaining double precision not null,remaining_before double precision not null,remaining_after double precision not null,
 source_observation_id text not null,authority text not null,params_json text not null,created_at_ms bigint not null);
create index if not exists idx_pp_v4_s2d_action_position_time on pp_v4_stage2d_shadow_actions(position_id,observed_at_ms);
"""

def enabled()->bool:
    return os.environ.get("PP_V4_STAGE2D_SHADOW_ENABLED","false").strip().lower() in {"1","true","yes","on"}
def start_ms()->int:
    try:return int(os.environ.get("PP_V4_STAGE2D_START_MS","0") or 0)
    except (TypeError,ValueError):return 0

def initialize_store()->None:
    backend=persistence_backend();key=(backend,str(database_path()) if backend=="sqlite" else "postgres")
    with _LOCK:
        if key in _READY:return
        if backend=="sqlite":
            with _sqlite_connect(database_path()) as c:c.executescript(SQLITE_SCHEMA)
        else:
            with _postgres_connect() as c:
                with c.cursor() as cur:cur.execute(POSTGRES_SCHEMA)
        _READY.add(key)

def advance(state:ShadowState,current_pnl_pct:float,running_peak_pct:float,observed_at_ms:int)->tuple[ShadowState,dict[str,Any]|None,str]:
    ts=int(observed_at_ms);pnl=float(current_pnl_pct);peak=float(running_peak_pct)
    if ts==state.last_observed_at_ms:
        return ShadowState(**{**state.__dict__,"duplicate_count":state.duplicate_count+1}),None,"DUPLICATE"
    if ts<state.last_observed_at_ms:
        return ShadowState(**{**state.__dict__,"out_of_order_count":state.out_of_order_count+1}),None,"OUT_OF_ORDER"
    if state.shadow_closed:
        return ShadowState(**{**state.__dict__,"last_observed_at_ms":ts}),None,"CLOSED"

    runner=state.runner_qualified or peak>=RUNNER_QUALIFY
    sc=state.small_consecutive;rc=state.runner_consecutive
    small=state.small_fired;remaining=state.remaining_fraction;closed=False;action=None
    if runner:
        sc=0
        rc=rc+1 if pnl<=peak*RUNNER_RETAIN else 0
        if rc>=RUNNER_CONFIRM:
            before=remaining;remaining=0.0;closed=True
            action={"action_type":"SHADOW_CLOSE_REMAINDER","action_fraction_of_remaining":1.0,"remaining_before":before,"remaining_after":0.0}
    elif not small:
        sc=sc+1 if peak>=SMALL_ARM and pnl<=peak*SMALL_RETAIN else 0
        if sc>=SMALL_CONFIRM:
            before=remaining;after=before*(1.0-REDUCE_FRAC);remaining=after;small=True;sc=0
            action={"action_type":"SHADOW_REDUCE_25","action_fraction_of_remaining":REDUCE_FRAC,"remaining_before":before,"remaining_after":after}
    new=ShadowState(position_id=state.position_id,opened_at_ms=state.opened_at_ms,runner_qualified=runner,small_fired=small,small_consecutive=sc,runner_consecutive=rc,remaining_fraction=remaining,shadow_closed=closed,last_observed_at_ms=ts,duplicate_count=state.duplicate_count,out_of_order_count=state.out_of_order_count,invariant_error_count=state.invariant_error_count)
    return new,action,"ACTION" if action else "OBSERVED"

def _load(pid:str,opened:int)->ShadowState:
    initialize_store()
    if persistence_backend()=="sqlite":
        with _sqlite_connect(database_path()) as c:
            r=c.execute("select position_id,opened_at_ms,runner_qualified,small_fired,small_consecutive,runner_consecutive,remaining_fraction,shadow_closed,last_observed_at_ms,duplicate_count,out_of_order_count,invariant_error_count from pp_v4_stage2d_shadow_state where position_id=?",(pid,)).fetchone()
            if not r:return ShadowState(pid,opened)
            return ShadowState(str(r[0]),int(r[1]),bool(r[2]),bool(r[3]),int(r[4]),int(r[5]),float(r[6]),bool(r[7]),int(r[8]),int(r[9]),int(r[10]),int(r[11]))
    with _postgres_connect() as c:
        with c.cursor() as cur:
            cur.execute("select position_id,opened_at_ms,runner_qualified,small_fired,small_consecutive,runner_consecutive,remaining_fraction,shadow_closed,last_observed_at_ms,duplicate_count,out_of_order_count,invariant_error_count from pp_v4_stage2d_shadow_state where position_id=%s",(pid,));r=cur.fetchone()
            if not r:return ShadowState(pid,opened)
            return ShadowState(str(r[0]),int(r[1]),bool(r[2]),bool(r[3]),int(r[4]),int(r[5]),float(r[6]),bool(r[7]),int(r[8]),int(r[9]),int(r[10]),int(r[11]))

def _save_state(s:ShadowState)->None:
    now=int(time.time()*1000);v=(s.position_id,s.opened_at_ms,s.runner_qualified,s.small_fired,s.small_consecutive,s.runner_consecutive,s.remaining_fraction,s.shadow_closed,s.last_observed_at_ms,s.duplicate_count,s.out_of_order_count,s.invariant_error_count,now)
    if persistence_backend()=="sqlite":
        vv=list(v);vv[2]=int(vv[2]);vv[3]=int(vv[3]);vv[7]=int(vv[7])
        with _sqlite_connect(database_path()) as c:c.execute("insert or replace into pp_v4_stage2d_shadow_state values(?,?,?,?,?,?,?,?,?,?,?,?,?)",tuple(vv))
    else:
        with _postgres_connect() as c:
            with c.cursor() as cur:cur.execute("insert into pp_v4_stage2d_shadow_state values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(position_id) do update set runner_qualified=excluded.runner_qualified,small_fired=excluded.small_fired,small_consecutive=excluded.small_consecutive,runner_consecutive=excluded.runner_consecutive,remaining_fraction=excluded.remaining_fraction,shadow_closed=excluded.shadow_closed,last_observed_at_ms=excluded.last_observed_at_ms,duplicate_count=excluded.duplicate_count,out_of_order_count=excluded.out_of_order_count,invariant_error_count=excluded.invariant_error_count,updated_at_ms=excluded.updated_at_ms",v)

def _save_action(row:dict[str,Any],action:dict[str,Any])->bool:
    params=json.dumps({"small":[SMALL_ARM,SMALL_RETAIN,SMALL_CONFIRM,REDUCE_FRAC],"runner":[RUNNER_QUALIFY,RUNNER_RETAIN,RUNNER_CONFIRM]},sort_keys=True);now=int(time.time()*1000)
    aid=f"{row['position_id']}:{action['action_type']}";v=(aid,str(row["position_id"]),int(row["observed_at_ms"]),action["action_type"],float(row["current_pnl_pct"]),float(row["running_observed_peak_pct"]),float(action["action_fraction_of_remaining"]),float(action["remaining_before"]),float(action["remaining_after"]),str(row["observation_id"]),"NONE",params,now)
    if persistence_backend()=="sqlite":
        with _sqlite_connect(database_path()) as c:
            cur=c.execute("insert or ignore into pp_v4_stage2d_shadow_actions values(?,?,?,?,?,?,?,?,?,?,?,?,?)",v);return cur.rowcount>0
    with _postgres_connect() as c:
        with c.cursor() as cur:
            cur.execute("insert into pp_v4_stage2d_shadow_actions values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(action_id) do nothing",v);return cur.rowcount>0

def process_observation(row:dict[str,Any])->dict[str,Any]:
    if not enabled():return {"status":"DISABLED"}
    boundary=start_ms()
    if boundary<=0:return {"status":"WAITING_FOR_START_BOUNDARY"}
    opened=int(row["opened_at_ms"])
    if opened<=boundary:return {"status":"PRE_BOUNDARY"}
    initialize_store();state=_load(str(row["position_id"]),opened);new,action,status=advance(state,float(row["current_pnl_pct"]),float(row["running_observed_peak_pct"]),int(row["observed_at_ms"]));_save_state(new)
    inserted=False
    if action is not None:inserted=_save_action(row,action)
    return {"status":status,"action":None if action is None else action["action_type"],"action_inserted":inserted,"remaining_fraction":new.remaining_fraction,"runner_qualified":new.runner_qualified,"small_fired":new.small_fired,"shadow_closed":new.shadow_closed}

def summary(recent_limit:int=20)->dict[str,Any]:
    initialize_store();limit=max(1,min(int(recent_limit),100))
    if persistence_backend()=="sqlite":
        with _sqlite_connect(database_path()) as c:
            s=c.execute("select count(*),sum(duplicate_count),sum(out_of_order_count),sum(invariant_error_count),sum(case when small_fired=1 then 1 else 0 end),sum(case when runner_qualified=1 then 1 else 0 end),sum(case when shadow_closed=1 then 1 else 0 end) from pp_v4_stage2d_shadow_state").fetchone()
            a=c.execute("select count(*),count(distinct action_id),sum(case when action_type='SHADOW_REDUCE_25' then 1 else 0 end),sum(case when action_type='SHADOW_CLOSE_REMAINDER' then 1 else 0 end) from pp_v4_stage2d_shadow_actions").fetchone()
            recent=[dict(r) for r in c.execute("select action_id,position_id,observed_at_ms,action_type,current_pnl_pct,running_peak_pct,remaining_before,remaining_after,authority from pp_v4_stage2d_shadow_actions order by observed_at_ms desc limit ?",(limit,)).fetchall()]
            eligible=int(c.execute("select count(*) from positions where upper(mode)='PAPER' and opened_at_ms>?",(start_ms(),)).fetchone()[0] or 0)
    else:
        with _postgres_connect() as c:
            with c.cursor() as cur:
                cur.execute("select count(*),coalesce(sum(duplicate_count),0),coalesce(sum(out_of_order_count),0),coalesce(sum(invariant_error_count),0),count(*) filter(where small_fired),count(*) filter(where runner_qualified),count(*) filter(where shadow_closed) from pp_v4_stage2d_shadow_state");s=cur.fetchone()
                cur.execute("select count(*),count(distinct action_id),count(*) filter(where action_type='SHADOW_REDUCE_25'),count(*) filter(where action_type='SHADOW_CLOSE_REMAINDER') from pp_v4_stage2d_shadow_actions");a=cur.fetchone()
                cur.execute("select action_id,position_id,observed_at_ms,action_type,current_pnl_pct,running_peak_pct,remaining_before,remaining_after,authority from pp_v4_stage2d_shadow_actions order by observed_at_ms desc limit %s",(limit,));recent=[{"action_id":r[0],"position_id":r[1],"observed_at_ms":int(r[2]),"action_type":r[3],"current_pnl_pct":float(r[4]),"running_peak_pct":float(r[5]),"remaining_before":float(r[6]),"remaining_after":float(r[7]),"authority":r[8]} for r in cur.fetchall()]
                cur.execute("select count(*) from positions where upper(mode)='PAPER' and opened_at_ms>%s",(start_ms(),));eligible=int(cur.fetchone()[0] or 0)
    positions=int(s[0] or 0); coverage=(100.0*positions/eligible) if eligible>0 else None
    return {"version":VERSION,"enabled":enabled(),"start_ms":start_ms(),"authority":"NONE","eligible_positions_since_boundary":eligible,"positions":positions,"position_start_coverage_pct":coverage,"duplicate_observations":int(s[1] or 0),"out_of_order_observations":int(s[2] or 0),"invariant_errors":int(s[3] or 0),"small_fired_positions":int(s[4] or 0),"runner_qualified_positions":int(s[5] or 0),"shadow_closed_positions":int(s[6] or 0),"actions":int(a[0] or 0),"unique_actions":int(a[1] or 0),"duplicate_actions":int(a[0] or 0)-int(a[1] or 0),"shadow_reduces":int(a[2] or 0),"shadow_closes":int(a[3] or 0),"recent_actions":recent}
