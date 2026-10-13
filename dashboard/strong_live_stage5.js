/* STRONG LIVE Stage 5 control/status. Separate from paper/shadow controls. */
(function(global){
"use strict";
const API="https://core-prod.43-153-193-103.sslip.io";
let state=null,publicStatus=null,busy=false,timer=null;
const el=id=>document.getElementById(id);
const token=()=>((el("strongLiveToken")&&el("strongLiveToken").value.trim())||
  (el("strongControlToken")&&el("strongControlToken").value.trim())||
  sessionStorage.getItem("baba_control_token_v1")||"");
function css(){
 const style=document.createElement("style");
 style.textContent=".strong-live-auth{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:10px 0}.strong-live-auth input{background:#101a25;border:1px solid #425a78;border-radius:4px;padding:9px;color:#fff;min-width:190px}.strong-live-auth button{background:#20456a;border:1px solid #4e78a1;padding:9px;color:#fff;cursor:pointer}.strong-live-activity{font-size:10px;color:#8eb9e5;margin:8px 0}.strong-live-box{margin-top:12px;padding:14px;border-top:2px solid #498bf5;background:#0c1118}.strong-live-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.strong-live-head h3{margin:3px 0;font-size:14px}.strong-live-badge{padding:4px 8px;border:1px solid #344050;border-radius:4px;font-size:9px}.strong-live-grid{display:grid;grid-template-columns:repeat(5,minmax(100px,1fr));gap:7px;margin-top:10px}.strong-live-stat{padding:9px;border:1px solid #242c37;background:#111720}.strong-live-stat span{display:block;color:#848e9c;font-size:7px}.strong-live-stat strong{display:block;margin-top:4px;font-size:11px}.strong-live-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:11px}.strong-live-actions button{padding:8px 12px;border-radius:4px;border:1px solid #344050;cursor:pointer}.strong-live-run{background:#123729;color:#17d792}.strong-live-pause{background:#342515;color:#ffcb69}.strong-live-actions button:disabled{opacity:.45;cursor:not-allowed}.strong-live-msg{font-size:9px;color:#9aa4b2}.strong-live-warn{margin-top:9px;font-size:8px;color:#e5c86b}@media(max-width:850px){.strong-live-grid{grid-template-columns:1fr 1fr}}";
 document.head.appendChild(style);
}
function inject(){
 const pane=document.querySelector('[data-pane="strongcontrol"]');
 if(!pane||el("strongLiveStage5"))return;
 const box=document.createElement("section");
 box.id="strongLiveStage5";box.className="strong-live-box";
 box.innerHTML='<div class="strong-live-head"><div><div class="panel-sub">BINANCE LIVE · INDEPENDENT CONTROL</div><h3>STRONG Independent Paper V1 → LIVE</h3></div><span id="strongLiveMode" class="strong-live-badge">LOCKED</span></div>'+
 '<div class="strong-live-auth"><input id="strongLiveToken" type="password" autocomplete="off" placeholder="Admin Token untuk RUN / PAUSE"><button id="strongLiveVerify">VERIFY ACCESS</button></div>'+
 '<div class="strong-live-activity">AKTIVITAS WORKER: <strong id="strongLiveActivity">CONNECTING…</strong></div>'+
 '<div class="strong-live-grid">'+
 '<div class="strong-live-stat"><span>WORKER</span><strong id="strongLiveWorker">—</strong></div>'+
 '<div class="strong-live-stat"><span>ACTIVE POSITIONS</span><strong id="strongLivePositions">—</strong></div>'+
 '<div class="strong-live-stat"><span>PENDING ENTRY / EXIT</span><strong id="strongLivePending">—</strong></div>'+
 '<div class="strong-live-stat"><span>SHARED DAILY LOSS</span><strong id="strongLiveRisk">—</strong></div>'+
 '<div class="strong-live-stat"><span>LAST RESULT</span><strong id="strongLiveResult">—</strong></div></div>'+
 '<div class="strong-live-actions"><button id="strongLiveRun" class="strong-live-run">RUN STRONG LIVE</button>'+
 '<button id="strongLivePause" class="strong-live-pause">PAUSE STRONG LIVE</button>'+
 '<button id="strongLiveRefresh">REFRESH</button><span id="strongLiveMessage" class="strong-live-msg">Verify Admin Token untuk membaca dan mengubah Strong LIVE.</span></div>'+
 '<div class="strong-live-warn">PAUSE hanya memblokir entry LIVE baru. Paper tetap berjalan dan exit posisi LIVE milik Strong tetap dikelola. Daily loss $5 dipakai bersama W1D.</div>';
 pane.appendChild(box);
 el("strongLiveRun").addEventListener("click",()=>control("run"));
 el("strongLivePause").addEventListener("click",()=>control("pause"));
 el("strongLiveRefresh").addEventListener("click",load);
 el("strongLiveVerify").addEventListener("click",verify);
 el("strongLiveToken").addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();verify();}});
 if(el("strongControlToken"))el("strongControlToken").addEventListener("input",()=>setTimeout(load,0));
}
async function request(path,options={}){
 const t=token();if(!t)throw Error("Admin Token required");
 const ctrl=new AbortController(),timeout=setTimeout(()=>ctrl.abort(),8000);
 try{
  const res=await fetch(API+"/w1d"+path,{method:options.method||"GET",
   signal:ctrl.signal,cache:"no-store",headers:{"X-Baba-Control-Token":t,
   ...(options.body?{"Content-Type":"application/json"}:{})},
   ...(options.body?{body:JSON.stringify(options.body)}:{})});
  const data=await res.json();
  if(!res.ok)throw Error(data.error||("HTTP "+res.status));
  return data;
 }finally{clearTimeout(timeout);}
}
function text(id,value){if(el(id))el(id).textContent=value;}
const activityLabels={
 SCANNING_PAPER_EVENTS:"SCANNING · MEMERIKSA STRONG PAPER",
 PAUSED_ENTRIES:"PAUSE · TIDAK ADA ENTRY BARU",
 BLOCKED_SHARED_RISK:"BLOCKED · DAILY RISK",
 WORKER_ERROR:"ERROR · WORKER",
 WORKER_HEARTBEAT_STALE:"OFFLINE / HEARTBEAT STALE"
};
function render(){
 const locked=!token(),mode=state?.mode||publicStatus?.mode||"CONNECTING";
 text("strongLiveMode",mode);
 text("strongLiveActivity",activityLabels[publicStatus?.activity]||"MEMERIKSA STATUS…");
 text("strongLiveWorker",state?(state.worker_healthy?"HEALTHY · "+state.worker_age_seconds+"s":"UNHEALTHY · "+state.worker_status):
    publicStatus?(publicStatus.worker_age_seconds===null?"UNKNOWN":String(publicStatus.worker_age_seconds)+"s sejak heartbeat"):"—");
 text("strongLivePositions",state?String(state.active_positions):"—");
 text("strongLivePending",state?(state.pending_entries+" / "+state.pending_exits):"—");
 text("strongLiveRisk",state&&state.shared_daily_risk?
   "$"+Number(state.shared_daily_risk.limit_usdt).toFixed(2)+" · "+state.shared_daily_risk.state:"—");
 text("strongLiveResult",state?(state.worker_last_result||"—"):"—");
 if(el("strongLiveRun"))el("strongLiveRun").disabled=busy||(!!state&&state.mode==="RUN");
 if(el("strongLivePause"))el("strongLivePause").disabled=busy||(!!state&&state.mode==="PAUSE");
 if(el("strongLiveRefresh"))el("strongLiveRefresh").disabled=busy;
}
async function load(){
 if(!el("strongLiveStage5"))inject();
 try{
  const response=await fetch(API+"/w1d/live/runtime",{cache:"no-store"});
  const data=await response.json();
  if(response.ok)publicStatus=data.live_runtime?.strong||null;
 }catch(e){publicStatus=null;}
 if(!token()){
  state=null;text("strongLiveMessage","Status LIVE terbuka. Masukkan Admin Token di atas dan klik VERIFY ACCESS untuk kontrol RUN / PAUSE.");
  render();return;
 }
 try{
  const data=await request("/strong-live/status");
  state=data.strong_live;
  text("strongLiveMessage","Admin terverifikasi · Status backend Strong LIVE tersambung.");
 }catch(err){state=null;text("strongLiveMessage","Admin Token perlu VERIFY: "+String(err.message||err));}
 render();
}
async function verify(){
 const t=token();
 if(!t){text("strongLiveMessage","Isi Admin Token langsung di kolom atas.");el("strongLiveToken")?.focus();return;}
 if(busy)return;
 busy=true;render();
 try{
  const data=await request("/strong-live/status");
  if(!data.strong_live)throw Error("STATUS_NOT_RETURNED");
  sessionStorage.setItem("baba_control_token_v1",t);
  ["w1dAdminToken","strongControlToken"].forEach(id=>{if(el(id))el(id).value=t;});
  state=data.strong_live;
  text("strongLiveMessage","VERIFIED · Tombol RUN / PAUSE Strong dapat digunakan.");
  global.LiveOpsHub?.refresh();
  global.W1DOperations?.refresh(true);
 }catch(err){state=null;text("strongLiveMessage","VERIFY gagal: "+String(err.message||err));}
 finally{busy=false;render();}
}
async function control(action){
 if(busy)return;
 if(!state){text("strongLiveMessage","Masukkan Admin Token di kolom atas lalu klik VERIFY ACCESS.");el("strongLiveToken")?.focus();return;}
 const target=action==="run"?"RUN":"PAUSE";
 if(target==="RUN"&&!state.worker_healthy){text("strongLiveMessage","RUN belum siap: worker Strong tidak HEALTHY.");return;}
 const warning=target==="RUN"?
  "Aktifkan STRONG LIVE riil? Entry berikutnya mengikuti Strong Independent Paper V1, margin $5, target 50x/$250, ISOLATED MARKET, dan daily loss bersama W1D $5.":
  "Pause entry STRONG LIVE baru? Posisi milik Strong yang sudah terbuka tetap dikelola sampai exit.";
 if(!confirm(warning))return;
 busy=true;render();text("strongLiveMessage","Mengirim "+target+" ke backend…");
 try{
  await request("/strong-live/control/"+action,{method:"POST",body:{
   expected_updated_at:state.updated_at,reason:"strong_live_stage5_ui"
  }});
  await load();text("strongLiveMessage","STRONG LIVE "+target+" tersimpan di backend. Paper tetap berjalan.");
 }catch(err){text("strongLiveMessage","Kontrol ditolak: "+String(err.message||err));}
 finally{busy=false;render();}
}
function init(){
 css();inject();load();
 timer=setInterval(load,10000);
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init,{once:true});
else init();
global.StrongLiveStage5={load,get state(){return state;}};
})(window);
