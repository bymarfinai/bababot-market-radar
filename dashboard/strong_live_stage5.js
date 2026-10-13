/* STRONG LIVE Stage 5 control/status. Separate from paper/shadow controls. */
(function(global){
"use strict";
const API="https://core-prod.43-153-193-103.sslip.io";
let state=null,busy=false,timer=null;
const el=id=>document.getElementById(id);
const token=()=>((el("strongControlToken")&&el("strongControlToken").value.trim())||
  sessionStorage.getItem("baba_control_token_v1")||"");
function css(){
 const style=document.createElement("style");
 style.textContent=".strong-live-box{margin-top:12px;padding:14px;border-top:2px solid #498bf5;background:#0c1118}.strong-live-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.strong-live-head h3{margin:3px 0;font-size:14px}.strong-live-badge{padding:4px 8px;border:1px solid #344050;border-radius:4px;font-size:9px}.strong-live-grid{display:grid;grid-template-columns:repeat(5,minmax(100px,1fr));gap:7px;margin-top:10px}.strong-live-stat{padding:9px;border:1px solid #242c37;background:#111720}.strong-live-stat span{display:block;color:#848e9c;font-size:7px}.strong-live-stat strong{display:block;margin-top:4px;font-size:11px}.strong-live-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:11px}.strong-live-actions button{padding:8px 12px;border-radius:4px;border:1px solid #344050;cursor:pointer}.strong-live-run{background:#123729;color:#17d792}.strong-live-pause{background:#342515;color:#ffcb69}.strong-live-actions button:disabled{opacity:.45;cursor:not-allowed}.strong-live-msg{font-size:9px;color:#9aa4b2}.strong-live-warn{margin-top:9px;font-size:8px;color:#e5c86b}@media(max-width:850px){.strong-live-grid{grid-template-columns:1fr 1fr}}";
 document.head.appendChild(style);
}
function inject(){
 const pane=document.querySelector('[data-pane="strongcontrol"]');
 if(!pane||el("strongLiveStage5"))return;
 const box=document.createElement("section");
 box.id="strongLiveStage5";box.className="strong-live-box";
 box.innerHTML='<div class="strong-live-head"><div><div class="panel-sub">BINANCE LIVE · INDEPENDENT CONTROL</div><h3>STRONG Independent Paper V1 → LIVE</h3></div><span id="strongLiveMode" class="strong-live-badge">LOCKED</span></div>'+
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
function render(){
 const locked=!token();
 text("strongLiveMode",locked?"LOCKED":state?state.mode:"CONNECTING");
 text("strongLiveWorker",state?(state.worker_healthy?"HEALTHY · "+state.worker_age_seconds+"s":"UNHEALTHY · "+state.worker_status):"—");
 text("strongLivePositions",state?String(state.active_positions):"—");
 text("strongLivePending",state?(state.pending_entries+" / "+state.pending_exits):"—");
 text("strongLiveRisk",state&&state.shared_daily_risk?
   "$"+Number(state.shared_daily_risk.limit_usdt).toFixed(2)+" · "+state.shared_daily_risk.state:"—");
 text("strongLiveResult",state?(state.worker_last_result||"—"):"—");
 if(el("strongLiveRun"))el("strongLiveRun").disabled=busy||locked||!state||!state.worker_healthy||state.mode==="RUN";
 if(el("strongLivePause"))el("strongLivePause").disabled=busy||locked||!state||state.mode==="PAUSE";
 if(el("strongLiveRefresh"))el("strongLiveRefresh").disabled=busy;
}
async function load(){
 if(!el("strongLiveStage5"))inject();
 if(!token()){state=null;text("strongLiveMessage","Verify Admin Token untuk membaca Strong LIVE.");render();return;}
 try{
  const data=await request("/strong-live/status");
  state=data.strong_live;text("strongLiveMessage","Status backend terverifikasi · paper tidak terpengaruh.");
 }catch(err){state=null;text("strongLiveMessage","Strong LIVE status gagal: "+String(err.message||err));}
 render();
}
async function control(action){
 if(!state||busy)return;
 const target=action==="run"?"RUN":"PAUSE";
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
