from __future__ import annotations
import os, threading, time
from typing import Any

from .persistence import _postgres_connect, _sqlite_connect, database_path, persistence_backend

STAGE7_VERSION = "pp-decision-v2-stage7-ambiguous-recovery-gate"
STAGE7_RECOVERY_MIN_PP = 0.10
_LOCK = threading.Lock()
_READY: set[tuple[str, str]] = set()

SQLITE_SCHEMA = """
create table if not exists pp_decision_v2_stage7_ambiguous (
 position_id text primary key,
 opened_at_ms integer not null,
 stage5_classified_at_ms integer not null,
 initial_mfe_pct real not null,
 initial_current_pnl_pct real not null,
 followup_mfe_pct real not null,
 followup_current_pnl_pct real not null,
 recovery_pp real not null,
 decision text not null,
 confidence text not null,
 version text not null,
 created_at_ms integer not null
);
"""
POSTGRES_SCHEMA = SQLITE_SCHEMA.replace(" integer", " bigint").replace(" real", " double precision")

def stage7_enabled() -> bool:
    return os.environ.get("PP_DECISION_V2_STAGE7_ENABLED","false").strip().lower() in {"1","true","yes","on"}
def stage7_start_ms() -> int:
    try:
        return int(os.environ.get("PP_DECISION_V2_STAGE7_START_MS","0") or 0)
    except (TypeError, ValueError):
        return 0

def initialize_stage7_store() -> None:
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

def _save(row: dict[str,Any]) -> None:
    initialize_stage7_store()
    vals=(
        str(row["position_id"]),int(row["opened_at_ms"]),int(row["stage5_classified_at_ms"]),
        float(row["initial_mfe_pct"]),float(row["initial_current_pnl_pct"]),
        float(row["followup_mfe_pct"]),float(row["followup_current_pnl_pct"]),
        float(row["recovery_pp"]),str(row["decision"]),str(row["confidence"]),
        STAGE7_VERSION,int(row["created_at_ms"]),
    )
    if persistence_backend()=="sqlite":
        with _sqlite_connect(database_path()) as c:
            c.execute("""insert or ignore into pp_decision_v2_stage7_ambiguous(
                position_id,opened_at_ms,stage5_classified_at_ms,initial_mfe_pct,
                initial_current_pnl_pct,followup_mfe_pct,followup_current_pnl_pct,
                recovery_pp,decision,confidence,version,created_at_ms
            ) values (?,?,?,?,?,?,?,?,?,?,?,?)""",vals)
    else:
        with _postgres_connect() as c:
            with c.cursor() as cur:
                cur.execute("""insert into pp_decision_v2_stage7_ambiguous(
                    position_id,opened_at_ms,stage5_classified_at_ms,initial_mfe_pct,
                    initial_current_pnl_pct,followup_mfe_pct,followup_current_pnl_pct,
                    recovery_pp,decision,confidence,version,created_at_ms
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict(position_id) do nothing""",vals)

def evaluate_stage7_ambiguous(
    *,
    position_id: str,
    opened_at_ms: int,
    stage5_state: dict[str,Any] | None,
) -> dict[str,Any] | None:
    if not stage7_enabled():
        return None
    if int(opened_at_ms) <= stage7_start_ms():
        return None
    if not stage5_state or str(stage5_state.get("status")) != "AMBIGUOUS":
        return None
    classified_at=stage5_state.get("classified_at_ms")
    initial=stage5_state.get("initial_current_pnl_pct")
    followup=stage5_state.get("followup_current_pnl_pct")
    initial_mfe=stage5_state.get("initial_mfe_pct")
    followup_mfe=stage5_state.get("followup_mfe_pct")
    if None in {classified_at,initial,followup,initial_mfe,followup_mfe}:
        return None
    recovery=float(followup)-float(initial)
    decision="GRACE_CANDIDATE" if recovery >= STAGE7_RECOVERY_MIN_PP else "PROTECT_CANDIDATE"
    confidence="MEDIUM_HIGH" if decision=="GRACE_CANDIDATE" else "MEDIUM"
    row={
        "position_id":str(position_id),
        "opened_at_ms":int(opened_at_ms),
        "stage5_classified_at_ms":int(classified_at),
        "initial_mfe_pct":float(initial_mfe),
        "initial_current_pnl_pct":float(initial),
        "followup_mfe_pct":float(followup_mfe),
        "followup_current_pnl_pct":float(followup),
        "recovery_pp":recovery,
        "decision":decision,
        "confidence":confidence,
        "version":STAGE7_VERSION,
        "created_at_ms":int(time.time()*1000),
    }
    _save(row)
    return {
        "version":STAGE7_VERSION,
        "decision":decision,
        "confidence":confidence,
        "recovery_pp":recovery,
        "threshold_pp":STAGE7_RECOVERY_MIN_PP,
    }

def stage7_summary() -> dict[str,Any]:
    initialize_stage7_store()
    if persistence_backend()=="sqlite":
        with _sqlite_connect(database_path()) as c:
            total=c.execute("select count(*) from pp_decision_v2_stage7_ambiguous").fetchone()[0]
            groups=c.execute("""select decision,count(*) from pp_decision_v2_stage7_ambiguous
                                group by decision order by decision""").fetchall()
        return {
            "version":STAGE7_VERSION,"enabled":stage7_enabled(),"start_ms":stage7_start_ms(),
            "authority":"NONE_SHADOW","rows":int(total or 0),
            "by_decision":{str(k):{"n":int(v)} for k,v in groups},
        }
    with _postgres_connect() as c:
        with c.cursor() as cur:
            cur.execute("""select s.decision,count(*),
                sum(case when v.position_id is not null then 1 else 0 end),
                sum(case when v.delta_grace30_vs_stage3>0 then 1 else 0 end),
                sum(case when v.delta_grace30_vs_stage3<0 then 1 else 0 end),
                sum(case when v.position_id is not null then v.delta_grace30_vs_stage3 else 0 end)
                from pp_decision_v2_stage7_ambiguous s
                left join pp_decision_v2_stage6_validation v on v.position_id=s.position_id
                group by s.decision order by s.decision""")
            groups=cur.fetchall()
            cur.execute("select count(*) from pp_decision_v2_stage7_ambiguous")
            total=int(cur.fetchone()[0] or 0)
    by={}
    hybrid_delta=0.0
    for decision,n,finalized,wins,losses,delta in groups:
        delta=float(delta or 0)
        if str(decision)=="GRACE_CANDIDATE":
            hybrid_delta += delta
        by[str(decision)]={
            "n":int(n),"finalized":int(finalized or 0),
            "grace30_better":int(wins or 0),"grace30_worse":int(losses or 0),
            "grace30_delta_vs_stage3":delta,
        }
    return {
        "version":STAGE7_VERSION,"enabled":stage7_enabled(),"start_ms":stage7_start_ms(),
        "authority":"NONE_SHADOW","recovery_threshold_pp":STAGE7_RECOVERY_MIN_PP,
        "rows":total,"hybrid_delta_vs_stage3":hybrid_delta,"by_decision":by,
    }
