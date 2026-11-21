/* STRONG independent paper forward dashboard. Reads ONLY /strong/paper/*. */
(function(global){
"use strict";
const API="https://core-prod.43-153-193-103.sslip.io/strong";
const s={active:false,data:null,positions:[],events:[],error:null,loading:false,lastFetch:0,seq:0};
const el=id=>document.getElementById(id);
const esc=v=>String(v===undefined||v===null?"":v).replace(/[&<>"']/g,
  c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=(v,d=2)=>v===null||v===undefined||!Number.isFinite(Number(v))?"—":Number(v).toFixed(d);
const money=v=>v===null||v===undefined?"—":(Number(v)>=0?"+":"")+"$"+fmt(v,2);
const percentage=v=>v===null||v===undefined?"—":fmt(v,3)+"%";
const date=v=>v?new Date(Number(v)).toLocaleString():"—";
const authToken=()=>((el("strongControlToken")?.value||"").trim()||
                sessionStorage.getItem("baba_control_token_v1")||"");
function selected(){return s.active;}
async function request(path){
  const t=authToken();
  const c=new AbortController();
  const timer=setTimeout(()=>c.abort(),8000);
  try{
    const r=await fetch(API+path,{cache:"no-store",signal:c.signal,
                                  headers:{...(t?{"X-Baba-Control-Token":t}:{})}});
    const data=await r.json();
    if(!r.ok)throw Error(r.status===401?"Admin Token rejected":
                          String(data.error||data.detail||("HTTP "+r.status)));
    return data;
  }finally{clearTimeout(timer);}
}
function renderTop(){
  if(!s.active)return;
  const m=s.data&&s.data.summary||{};
  const open=m.open,closed=m.closed,wr=m.wr_pct;
  const set=(id,val)=>{if(el(id))el(id).textContent=val;};
  set("stOpenLabel","STRONG Independent OPEN / WR");
  set("stLongPerfLabel","Independent LONG · Closed / WR / Net");
  set("stShortPerfLabel","Independent SHORT · Not installed");
  set("stPnlLabel","STRONG Independent Closed PnL");
  set("stOpen",open===undefined?"—":open);
  set("stWr",percentage(wr));
  set("stClosed",closed===undefined?"—":closed);
  set("stLongPerf",closed===undefined?"—":closed+"t · "+percentage(wr)+" · "+money(m.realized_closed_pnl_usdt));
  set("stShortPerf","NOT INSTALLED");
  set("stPnl",closed===undefined?"—":money(m.realized_closed_pnl_usdt));
  if(el("stPnl"))el("stPnl").className=Number(m.realized_closed_pnl_usdt)>=0?"green":"red";
  set("apiChip",s.error?"STRONG PAPER ERROR":s.data?"STRONG PAPER LIVE":"STRONG PAPER CONNECTING");
  if(el("apiDot"))el("apiDot").className=s.error?"dot bad":s.data?"dot ok":"dot";
  set("refreshChip","PAPER "+(s.lastFetch?new Date(s.lastFetch).toLocaleTimeString():"—"));
}
function context(){
  if(!s.active)return;
  const e=s.data&&s.data.engine;
  if(el("strongStrategyStatus"))el("strongStrategyStatus").textContent=
    e&&e.status==="RUNNING"?"PAPER RUNNING":"PAPER STATUS UNKNOWN";
  if(el("activeStrategyTitle"))el("activeStrategyTitle").textContent="STRONG — FORWARD PAPER";
  if(el("strategyContextTitle"))el("strategyContextTitle").textContent="STRONG Independent Paper";
  if(el("strategyContextNote"))el("strategyContextNote").textContent=
    "Separate strong_paper_* ledger · entry AFTER STRONG qualified · paper only";
}
function card(label,value,note){
  return '<div class="shadow-stat"><span>'+esc(label)+'</span><strong>'+esc(value)+
         '</strong><small>'+esc(note)+'</small></div>';
}
function render(){
  if(!s.active)return;
  renderTop();context();
  const notice=el("strongPaperNotice"),m=s.data&&s.data.summary,e=s.data&&s.data.engine;
  if(notice){
    notice.textContent=s.error?"PAPER DATA ERROR · "+s.error:
      !s.data?"Connecting to isolated paper ledger...":
      "INDEPENDENT FORWARD ONLY · Starts "+date(e&&e.start_ms)+
      " · "+(e&&e.status||"NO ENGINE")+" · paper-only execution. Shadow T0 PnL excluded.";
    notice.className="strong-notice "+(s.error?"strong-error":"");
  }
  const overview=el("strongPaperOverview");
  if(overview){
    overview.innerHTML=m?[
      card("Paper OPEN",m.open,"independent entry after T+120 qualification"),
      card("Paper CLOSED",m.closed,"closed outcomes only"),
      card("WR",percentage(m.wr_pct),m.wins+" win / "+m.closed+" closed"),
      card("Realized net",money(m.realized_closed_pnl_usdt),"independent paper only; not legacy virtual"),
      card("Observed MFE avg",percentage(m.avg_observed_mfe_pct),"observed marks; not full-tick MFE"),
      card("Observed MAE avg",percentage(m.avg_observed_mae_pct),"observed marks; not full-tick MAE"),
      card("DATA_GAP",m.statuses.DATA_GAP,"excluded from WR / realized PnL"),
      card("CENSORED",m.statuses.CENSORED_30MIN,"unresolved; excluded from WR")
    ].join(""):"";
  }
  if(el("strongPaperMeta"))el("strongPaperMeta").textContent=
    (m?m.total:0)+" independent LONG paper positions · "+(e?"Cutoff "+date(e.start_ms):"No runtime")+
    " · no legacy trades included";
  const rows=s.positions;
  const table=el("strongPaperRows");
  if(table)table.innerHTML=rows.length?rows.map(p=>{
    const pnl=p.status==="CLOSED"?money(p.realized_pnl):"—";
    return '<tr><td><strong>'+esc(p.symbol)+'</strong><div class="cell-sub">'+esc(p.side)+
      ' · '+esc(p.strategy)+'</div></td>'+
      '<td><span class="badge neutral">'+esc(p.status)+'</span></td>'+
      '<td>'+esc(date(p.opened_at_ms))+'<div class="cell-sub">Qualified '+esc(date(p.source_qualified_at_ms))+'</div></td>'+
      '<td class="mono">'+esc(fmt(p.entry_market_price,8))+'<div class="cell-sub">Fill '+esc(fmt(p.entry_fill_price,8))+'</div></td>'+
      '<td class="mono">'+esc(fmt(p.last_price,8))+'<div class="cell-sub">'+esc(p.samples)+' marks</div></td>'+
      '<td class="green">'+esc(percentage(p.peak_pct))+'</td>'+
      '<td class="red">'+esc(percentage(p.trough_pct))+'</td>'+
      '<td class="'+(Number(p.realized_pnl)>=0?"green":"red")+'">'+esc(pnl)+'</td>'+
      '<td>'+esc(p.closed_at_ms?date(p.closed_at_ms):"—")+
      '<div class="cell-sub">'+esc(p.close_reason||p.last_error||"—")+'</div></td></tr>';
  }).join(""):'<tr><td colspan="9" class="empty"><strong>No independent paper positions</strong><span>Only new QUALIFIED_STRONG signals after cutoff can create a paper entry.</span></td></tr>';
  const ev=el("strongPaperEventRows");
  if(ev)ev.innerHTML=s.events.length?s.events.map(x=>
    '<tr><td>'+esc(date(x.observed_at_ms))+'</td><td>'+esc(x.event_type)+'</td>'+
    '<td class="mono">'+esc((x.paper_id||"").split("PAPER:").pop().split(":")[0])+'</td>'+
    '<td>'+esc(fmt(x.price,8))+'</td><td>'+esc(x.trade_ms?date(x.trade_ms):"—")+'</td></tr>'
  ).join(""):'<tr><td colspan="5" class="empty">No independent paper events.</td></tr>';
}
async function load(force=false){
  if(!s.active||s.loading)return;
  if(!force&&Date.now()-s.lastFetch<7000){render();return;}
  s.loading=true;const seq=++s.seq;
  try{
    const results=await Promise.all([
      request("/paper/status"),request("/paper/positions?limit=200"),request("/paper/events?limit=75")
    ]);
    if(!s.active||seq!==s.seq)return;
    s.data=results[0];s.positions=results[1].positions||[];
    s.events=results[2].events||[];s.error=null;s.lastFetch=Date.now();
  }catch(err){
    if(seq!==s.seq)return;
    s.error=String(err.message||err);
    s.data=null;s.positions=[];s.events=[];s.lastFetch=0;
  }finally{
    s.loading=false;if(s.active&&seq===s.seq)render();
  }
}
function activate(value){
  const was=s.active;
  s.active=!!value;
  if(!s.active){s.seq++;return;}
  if(!was){s.lastFetch=0;render();}
  load(!was);
}
function init(){
  if(el("strongPaperRefresh"))el("strongPaperRefresh").addEventListener("click",()=>{s.lastFetch=0;load(true);});
}
global.StrongPaperUI={init,activate,load,renderTop,context,isSelected:selected,model:s};
})(window);