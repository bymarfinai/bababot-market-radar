/* STRONG Stage5 independent view/controller. No chart or radar functions. */
(function(global){
"use strict";
const API="https://core-prod.43-153-193-103.sslip.io";
const names={V43_PRIMARY:"V4.3 PRIMARY",V42_SHADOW:"V4.2 SHADOW",UNARMED_SHADOW:"UNARMED SHADOW"};
const keys=["V43_PRIMARY","V42_SHADOW","UNARMED_SHADOW"];
const s={status:null,positions:[],branches:[],actions:[],events:[],legacyMetrics:null,
  selected:null,lastError:null,loading:false,sequence:0,lastFetch:0,
  authorized:false,authRequired:false,busy:false,active:false};
const el=id=>document.getElementById(id);
const esc=v=>String(v===undefined||v===null?"":v).replace(/[&<>"']/g,
  c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const n=(v,d=2)=>v===null||v===undefined||!Number.isFinite(Number(v))?"—":Number(v).toFixed(d);
const amount=v=>v===null||v===undefined||!Number.isFinite(Number(v))?"—":(Number(v)>=0?"+":"")+"$"+Number(v).toFixed(2);
const percent=v=>v===null||v===undefined||!Number.isFinite(Number(v))?"—":n(v,2)+"%";
const date=v=>v?new Date(Number(v)).toLocaleString():"—";
const span=v=>'<span class="badge neutral">'+esc(v||"—")+"</span>";
const nodetext=(id,val)=>{if(el(id))el(id).textContent=val;};
function token(){return (el("strongControlToken")&&el("strongControlToken").value.trim())||
  sessionStorage.getItem("baba_control_token_v1")||"";}
function message(text,error){s.lastError=error?text:null;
  const node=el("strongControlMessage");if(node){node.textContent=text;node.className="control-message "+(error?"red":"muted");}}
async function req(path,{method="GET",body=null,requireAuth=false}={}){
  const t=token();
  if((requireAuth||method!=="GET")&&!t)throw Error("Admin Token required for STRONG control.");
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),8000);
  try{
    const result=await fetch(API+"/strong"+path,{
      method,signal:controller.signal,cache:"no-store",
      headers:{...(t?{"X-Baba-Control-Token":t}:{}),...(body?{"Content-Type":"application/json"}:{})},
      ...(body?{body:JSON.stringify(body)}:{})
    });
    const json=await result.json();
    if(!result.ok)throw Error(json.detail||json.error||("HTTP "+result.status));
    return json;
  }finally{clearTimeout(timeout);}
}
function primary(){return s.status&&s.status.summary&&s.status.summary.branches&&s.status.summary.branches.V43_PRIMARY||null;}
function branchStats(key){return s.status&&s.status.summary&&s.status.summary.branches&&s.status.summary.branches[key]||null;}
function summaryCards(){
  if(!s.status)return "";
  const summary=s.status.summary||{};
  const counts=summary.position_status_counts||{};
  const qualified=Number(counts.QUALIFIED_STRONG||0);
  const sourceSkipped=Number((summary.event_counts||{}).PAUSED_SKIP||0);
  const legacy=s.legacyMetrics;
  return '<div class="shadow-stat"><span>Legacy Shadow Candidates</span><strong>'+Number(summary.positions_total||0)+'</strong><small>independent strong_* only</small></div>'+
  '<div class="shadow-stat"><span>QUALIFIED_STRONG</span><strong>'+qualified+'</strong><small>classification known after T120</small></div>'+
  '<div class="shadow-stat"><span>V4.3 Closed Net</span><strong class="'+(primary()&&Number(primary().closed_realized_pnl_usdt)>=0?"green":"red")+'">'+(primary()&&primary().closed?amount(primary().closed_realized_pnl_usdt):"—")+'</strong><small>'+(primary()?primary().closed:0)+' closed · realized only</small></div>'+
  '<div class="shadow-stat"><span>Paused / No-backfill</span><strong>'+sourceSkipped+'</strong><small>Original sources skipped</small></div>'+
  '<div class="shadow-stat"><span>Observed MFE avg</span><strong>'+(legacy&&legacy.avg_observed_mfe_pct!==null?percent(legacy.avg_observed_mfe_pct):"—")+'</strong><small>Legacy T0 · 5s observed marks</small></div>'+
  '<div class="shadow-stat"><span>Observed MAE avg</span><strong>'+(legacy&&legacy.avg_observed_mae_pct!==null?percent(legacy.avg_observed_mae_pct):"—")+'</strong><small>Legacy T0 · 5s observed marks</small></div>';
}
function renderTop(){
  if(!s.active)return;
  if(global.StrongPaperUI&&global.StrongPaperUI.isSelected()){
    global.StrongPaperUI.renderTop();return;
  }
  const sm=s.status&&s.status.summary||{};
  const p=primary(),v42=branchStats("V42_SHADOW"),m=sm.positions_total;
  nodetext("stOpenLabel","Legacy Shadow Sources / V4.3 WR");
  nodetext("stLongPerfLabel","V4.3 PRIMARY · Closed / WR / PnL");
  nodetext("stShortPerfLabel","V4.2 SHADOW · Closed / WR / PnL");
  nodetext("stPnlLabel","STRONG Legacy V4.3 Virtual Closed PnL");
  nodetext("stOpen",m===undefined?"—":m);
  nodetext("stWr",p&&p.closed?percent(p.win_rate_pct):"—");
  function fmt(b){return !b?"—":b.closed+"t · "+(b.closed?percent(b.win_rate_pct):"—")+
    " · "+(b.closed?amount(b.closed_realized_pnl_usdt):"—");}
  nodetext("stLongPerf",fmt(p));
  nodetext("stShortPerf",fmt(v42));
  nodetext("stPnl",p&&p.closed?amount(p.closed_realized_pnl_usdt):"—");
  if(el("stPnl"))el("stPnl").className=p&&p.closed?(Number(p.closed_realized_pnl_usdt)>=0?"green":"red"):"muted";
  nodetext("stClosed",p?p.closed:"—");
  nodetext("apiChip",s.lastError?"STRONG DATA ERROR":s.status?"STRONG API LIVE":"STRONG CONNECTING");
  if(el("apiDot"))el("apiDot").className=s.lastError?"dot bad":s.status?"dot ok":"dot";
  nodetext("refreshChip","STRONG "+(s.lastFetch?new Date(s.lastFetch).toLocaleTimeString():"—"));
}
function context(){
  if(global.StrongPaperUI&&global.StrongPaperUI.isSelected()){
    global.StrongPaperUI.context();return;
  }
  const c=s.status&&s.status.controls||{};
  nodetext("strongStrategyStatus",!s.status?"CONNECTING · SHADOW":(c.master_enabled?"RUNNING":"MASTER OFF")+" · RESEARCH");
  if(!s.active)return;
  nodetext("activeStrategyTitle","STRONG — T0 RESEARCH");
  nodetext("strategyContextTitle","STRONG isolated shadow");
  nodetext("strategyContextNote","strong_* tables · 3 independent branches · no trading authority");
}

function renderPositions(){
  const p=s.positions;
  nodetext("strongPositionsMeta",p.length);
  nodetext("strongPositionsInfo",p.length+" source candidates · 1:1 original T0 · never reuse Flow Guard PnL");
  if(el("strongPositionRows"))el("strongPositionRows").innerHTML=p.length?p.map(x=>{
    const branches=s.branches.filter(b=>b.strong_position_id===x.strong_position_id);
    const label=branches.map(b=>(names[b.branch_key]||b.branch_key)+": "+b.status).join(" / ")||"—";
    const mx=s.legacyMetrics&&s.legacyMetrics.positions&&s.legacyMetrics.positions[x.strong_position_id];
    return '<tr data-strong-position="'+esc(x.strong_position_id)+'" class="'+(x.strong_position_id===s.selected?"is-selected":"")+'">'+
     '<td><div class="cell-main">'+esc(date(x.opened_at_ms))+'</div><div class="cell-sub mono">'+esc(x.source_signal_id||"—")+'</div></td>'+
     '<td><strong>'+esc(x.symbol)+'</strong> '+span(x.side)+'</td><td>'+span(x.status)+'</td>'+
     '<td class="mono">'+esc(n(x.entry_price,5))+' · '+esc(n(x.source_original_quantity,5))+
       '<div class="cell-sub">'+esc(amount(x.source_original_notional_usdt))+' notional</div></td>'+
     '<td>'+span(x.open_lane)+'</td><td>'+span(x.early60)+'</td><td>'+span(x.strong120)+'</td>'+
     '<td>'+(mx?percent(mx.mfe_pct):"—")+'</td><td>'+(mx?percent(mx.mae_pct):"—")+'</td>'+
     '<td class="reason-cell" title="'+esc(label)+'">'+esc(label)+'</td></tr>';
  }).join(""):'<tr><td colspan="10" class="empty"><strong>No STRONG candidates</strong><span>'+(!s.status?"Connecting to STRONG read-only data.":s.status.controls.master_enabled?"MASTER ON · waiting for eligible new LONG source.":"MASTER OFF · pre-resume source entries remain PAUSED_SKIP")+"</span></td></tr>";
  renderDetail();
}
function renderDetail(){
  const x=s.positions.find(p=>p.strong_position_id===s.selected);
  if(!el("strongSelectedDetail"))return;
  if(!x){el("strongSelectedDetail").textContent="Select a STRONG position to see each branch independently.";return;}
  const related=s.branches.filter(b=>b.strong_position_id===s.selected);
  const actions=s.actions.filter(a=>a.strong_position_id===s.selected);
  el("strongSelectedDetail").innerHTML='<strong>'+esc(x.symbol)+' · '+esc(x.strong_position_id)+'</strong>'+
    '<div>Original entry '+esc(date(x.opened_at_ms))+' · signal '+esc(x.source_signal_id||"—")+
    ' · price '+esc(n(x.entry_price,5))+' · status '+esc(x.status)+'</div>'+
    '<div class="strong-data-grid">'+keys.map(key=>{
      const b=related.find(z=>z.branch_key===key);
      return '<div><span>'+esc(names[key])+'</span><strong>'+esc(b?b.status:"NOT_STARTED")+'</strong>'+
        '<div>Net realized: '+(b&&b.status==="CLOSED"?amount(b.realized_pnl):"—")+
        '</div><div>Peak: '+(b?percent(b.peak_pct):"—")+
        '</div><div>Virtual actions: '+actions.filter(a=>a.branch_key===key).length+'</div></div>';
    }).join("")+'</div>';
}
function renderHistory(){
  const rows=s.branches.filter(b=>b.status==="CLOSED"&&b.realized_pnl!==null);
  nodetext("strongHistoryInfo",rows.length+" virtual CLOSED branch outcomes · open/reduced/censored excluded");
  const index=Object.fromEntries(s.positions.map(x=>[x.strong_position_id,x]));
  if(el("strongHistoryRows"))el("strongHistoryRows").innerHTML=rows.length?rows.map(b=>{
    const parent=index[b.strong_position_id]||{};
    const win=Number(b.realized_pnl)>0;
    return '<tr><td>'+esc(date(b.closed_at_ms))+'</td><td><strong>'+esc(parent.symbol||b.strong_position_id)+'</strong></td>'+
      '<td>'+esc(names[b.branch_key]||b.branch_key)+'</td><td>'+span(win?"WIN":"NON-WIN")+'</td>'+
      '<td class="'+(win?"green":"red")+'">'+esc(amount(b.realized_pnl))+'</td>'+
      '<td>'+esc(percent(b.realized_pnl_pct))+'</td><td>'+esc(n(b.entry_price,5))+'</td>'+
      '<td>'+esc(n(b.exit_price,5))+'</td><td>'+esc(b.close_reason||"—")+'</td></tr>';
  }).join(""):'<tr><td colspan="9" class="empty"><strong>No virtual close yet</strong><span>Unresolved outcomes never count toward realized WR/PnL.</span></td></tr>';
}
function renderDecisions(){
  const rows=s.events;
  nodetext("strongDecisionsInfo",rows.length+" STRONG event records · T0 source, 3B/3C/3D gates, virtual branch samples");
  if(el("strongDecisionRows"))el("strongDecisionRows").innerHTML=rows.length?rows.map(e=>
    '<tr><td>'+esc(date(e.observed_at_ms))+'</td><td>'+span(e.event_type)+'</td>'+
    '<td class="mono">'+esc(e.source_position_id||e.strong_position_id||"—")+'</td>'+
    '<td>'+esc(e.event_type==="PAUSED_SKIP"?"MASTER OFF — no backfill":e.event_type||"—")+'</td></tr>'
  ).join(""):'<tr><td colspan="4" class="empty"><strong>No STRONG events</strong></td></tr>';
}

function renderProtection(){
  const overview=el("strongBranchOverview");
  if(overview)overview.innerHTML=keys.map(key=>{
    const x=branchStats(key);
    return '<div class="shadow-stat"><span>'+esc(names[key])+'</span>'+
      '<strong>'+(x&&x.closed?amount(x.closed_realized_pnl_usdt):"—")+'</strong>'+
      '<small>'+(x?x.closed:0)+' closed · '+(x&&x.closed?percent(x.win_rate_pct):"—")+
      ' WR · '+(x?x.open:0)+' open · '+(x?x.data_gap:0)+' gaps</small></div>';
  }).join("")+'<div class="shadow-stat"><span>Economic basis</span><strong>VIRTUAL ONLY</strong><small>Open/censored not counted as winners</small></div>';
  const parent=Object.fromEntries(s.positions.map(p=>[p.strong_position_id,p]));
  if(el("strongProtectionRows"))el("strongProtectionRows").innerHTML=s.branches.length?s.branches.map(b=>{
    const p=parent[b.strong_position_id]||{};
    const pnl=b.status==="CLOSED"?b.realized_pnl:b.current_model_pnl_usdt;
    const obs=b.unarmed_observation||{};
    return '<tr><td>'+esc(date(p.opened_at_ms||b.opened_at_ms))+
      '<div class="cell-sub">'+esc(p.symbol||b.strong_position_id)+'</div></td>'+
      '<td>'+esc(names[b.branch_key]||b.branch_key)+'</td><td>'+span(b.status)+'</td>'+
      '<td class="'+(pnl===null||pnl===undefined?"muted":Number(pnl)>=0?"green":"red")+'">'+
        esc(amount(pnl))+'<div class="cell-sub">'+(b.status==="CLOSED"?"REALIZED":"MARK / UNREALIZED")+'</div></td>'+
      '<td>'+esc(percent(b.peak_pct))+'</td><td>'+esc(b.touched_arm?"TOUCHED +0.50%":"NOT TOUCHED")+'</td>'+
      '<td class="reason-cell">'+esc(b.unarmed_status||"—")+
      (b.branch_key==="UNARMED_SHADOW"&&obs.return_pct!==undefined?
         '<div class="cell-sub">Return '+esc(percent(obs.return_pct))+
         ' · velocity15 '+esc(n(obs.velocity_15s_pps,5))+' pp/s'+
         ' · velocity30 '+esc(n(obs.velocity_30s_pps,5))+
         ' · velocity60 '+esc(n(obs.velocity_60s_pps,5))+'</div>':"")+'</td></tr>';
  }).join(""):'<tr><td colspan="7" class="empty"><strong>No STRONG branches yet</strong><span>Three branches begin at original T0 when source is eligible.</span></td></tr>';
  if(el("strongActionRows"))el("strongActionRows").innerHTML=s.actions.length?s.actions.map(a=>
    '<tr><td>'+esc(date(a.observed_at_ms))+'</td><td>'+esc(names[a.branch_key]||a.branch_key)+'</td>'+
    '<td>'+span(a.action)+'</td><td>'+esc(n(a.price,5))+'</td>'+
    '<td>'+esc(n(a.quantity,6))+'</td><td>'+esc(amount(a.pnl_delta))+'</td>'+
    '<td>'+esc(a.reason||"—")+'</td></tr>').join(""):
    '<tr><td colspan="7" class="empty"><strong>No virtual actions</strong><span>STRONG does not place exchange orders.</span></td></tr>';
}
function renderControls(){
  const c=s.status&&s.status.controls||{};
  const on=!!c.master_enabled;
  nodetext("strongControlBadge",!s.status?"STATUS CONNECTING":on?"MASTER RUNNING":"MASTER OFF · NO BACKFILL");
  nodetext("strongEngineStatus",s.status&&s.status.engine?s.status.engine.status:"—");
  nodetext("strongEngineBoundary",s.status&&s.status.engine?date(s.status.engine.start_ms):"—");
  nodetext("strongPausedSkip",s.status?Number((s.status.summary&&s.status.summary.event_counts||{}).PAUSED_SKIP||0):"—");
  nodetext("strongTokenBadge",s.authorized?"CONTROL VERIFIED":"CONTROL LOCKED");
  document.querySelectorAll("[data-strong-setting]").forEach(btn=>{
    const setting=btn.dataset.strongSetting;
    const enabled=!!c[setting];
    btn.classList.toggle("active",enabled);
    btn.classList.toggle("paused",!enabled);
    const canResume=!!(s.status&&s.status.master_resume_api_enabled&&
      s.status.engine&&s.status.engine.status==="RUNNING"&&!s.status.engine.last_error&&
      c.v43_enabled&&c.v42_shadow_enabled&&c.unarmed_shadow_enabled);
    btn.disabled=s.busy||!s.authorized||!s.status||(setting==="master_enabled"&&!enabled&&!canResume);
    const label=btn.querySelector("strong");
    if(label)label.textContent=(setting==="master_enabled"?"MASTER":
      setting==="v43_enabled"?"V4.3 PRIMARY":
      setting==="v42_shadow_enabled"?"V4.2 SHADOW":"UNARMED SHADOW")+" — "+(!s.status?"LOCKED":enabled?"ON":"OFF");
  });
}
function render(){
  if(!s.active)return;
  context();renderTop();
  if(el("strongOverview"))el("strongOverview").innerHTML=summaryCards();
  const c=s.status&&s.status.controls||{};
  const node=el("strongDataState");
  if(node){
    const text=s.lastError?"STRONG DATA ERROR: "+s.lastError:
      !s.status?"Menghubungkan ke STRONG read-only API...":
      c.master_enabled?"MASTER ON · shadow research running · no execution authority.":
      "MASTER OFF · no-backfill active · "+Number((s.status.summary.event_counts||{}).PAUSED_SKIP||0)+
      " PAUSED_SKIP · live qualification/replay parity still pending.";
    node.textContent=text;
    node.className="strong-notice "+(s.lastError?"strong-error":"strong-paused");
  }
  renderPositions();renderHistory();renderDecisions();renderProtection();renderControls();
}

async function load(force=false){
  if(!s.active||s.loading)return;
  if(!force&&Date.now()-s.lastFetch<7000){render();return;}
  s.loading=true;
  const requestSequence=++s.sequence;
  try{
    const routes=["/status","/positions?limit=200","/branches?limit=300",
      "/actions?limit=300","/events?limit=250","/paper/legacy-excursions"];
    const results=await Promise.allSettled(routes.map(path=>req(path)));
    if(requestSequence!==s.sequence||!s.active)return;
    if(results[0].status!=="fulfilled")throw results[0].reason;
    const values=results.map(x=>x.status==="fulfilled"?x.value:null);
    s.status=values[0];s.authRequired=false;
    s.positions=values[1]?values[1].positions||[]:[];
    s.branches=values[2]?values[2].branches||[]:[];
    s.actions=values[3]?values[3].actions||[]:[];
    s.events=values[4]?values[4].events||[]:[];
    s.legacyMetrics=values[5]||null;
    const failed=results.map((r,i)=>r.status==="rejected"?routes[i]:null).filter(Boolean);
    s.lastError=failed.length?"Partial STRONG data unavailable: "+failed.join(", "):null;
    s.lastFetch=Date.now();
  }catch(err){
    if(requestSequence!==s.sequence)return;
    s.lastError=String(err&&err.message||err);
  }finally{
    s.loading=false;
    if(requestSequence===s.sequence)render();
    else if(s.active)load(true);
  }
}
async function verify(){
  const t=token();
  if(!t){message("Enter the admin token first.",true);return;}
  try{
    await req("/controls",{requireAuth:true});
    sessionStorage.setItem("baba_control_token_v1",t);
    ["controlToken","dlsControlToken","strongControlToken"].forEach(id=>{if(el(id))el(id).value=t;});
    s.authorized=true;s.authRequired=false;s.lastError=null;
    message("Control token verified. STRONG controls unlocked; read-only data stays visible without login.",false);
    await load(true);
  }catch(err){s.authorized=false;message("Verification failed: "+String(err.message||err),true);renderControls();}
}
async function setSetting(setting){
  const current=s.status&&s.status.controls;
  if(!current||!s.authorized||s.busy)return;
  const active=!!current[setting];
  if(setting==="master_enabled"&&!active){
    const engine=s.status&&s.status.engine;
    if(!s.status.master_resume_api_enabled||!engine||engine.status!=="RUNNING"||
       engine.last_error||!current.v43_enabled||!current.v42_shadow_enabled||
       !current.unarmed_shadow_enabled){
      message("Shadow MASTER resume unavailable: check feature gate, engine and all three branches.",true);return;
    }
  }
  const next=setting==="master_enabled"?!active:!active;
  const prompt=setting==="master_enabled"&&next?
     "Activate STRONG MASTER SHADOW-ONLY? New original LONG source positions will be evaluated from T0; previous PAUSED_SKIP will NOT backfill. No Binance orders. Ensure DLS remains PAUSED.":
     "Change STRONG "+setting+" to "+(next?"ON":"OFF")+
     "? This changes STRONG controls only; existing branches retain their frozen settings.";
  if(!confirm(prompt))return;
  s.busy=true;renderControls();
  try{
    const payload={[setting]:next,expected_updated_at_ms:Number(current.updated_at_ms||0),
                   reason:"strong_stage5_ui"};
    const response=await req("/control",{method:"POST",body:payload});
    s.status.controls=response.controls;
    message("STRONG "+setting+": "+(next?"ON":"OFF")+". Other engines unchanged.",false);
    s.lastFetch=0;await load(true);
  }catch(err){message("STRONG control failed: "+String(err.message||err),true);}
  finally{s.busy=false;render();}
}
function init(){
  const saved=sessionStorage.getItem("baba_control_token_v1");
  if(el("strongControlToken")&&saved)el("strongControlToken").value=saved;
  if(!saved&&el("strongControlMessage"))el("strongControlMessage").textContent="Read-only STRONG data is live. Verify Admin Token only to change controls.";
  if(el("strongVerifyToken"))el("strongVerifyToken").addEventListener("click",verify);
  if(el("strongClearToken"))el("strongClearToken").addEventListener("click",()=>{
    sessionStorage.removeItem("baba_control_token_v1");
    ["strongControlToken","controlToken","dlsControlToken"].forEach(id=>{if(el(id))el(id).value="";});
    s.authorized=false;s.authRequired=false;
    message("Control token cleared. STRONG read-only data remains visible; controls are locked.",false);
    render();
  });
  if(el("strongControlToken"))el("strongControlToken").addEventListener("input",()=>{
    s.authorized=false;renderControls();
  });
  document.querySelectorAll("[data-strong-setting]").forEach(btn=>
    btn.addEventListener("click",()=>setSetting(btn.dataset.strongSetting)));
  if(el("strongPositionRows"))el("strongPositionRows").addEventListener("click",evt=>{
    const row=evt.target.closest("[data-strong-position]");
    if(!row)return;
    s.selected=row.dataset.strongPosition;
    renderPositions();
  });
}
function activate(on){
  s.active=!!on;
  ++s.sequence;
  if(s.active){render();load(false);}
}
global.StrongStage5={init,activate,load,render,context,renderTop,getToken:token,
  model:s};
})(window);