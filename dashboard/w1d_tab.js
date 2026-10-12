/* W1D independent strategy tab. Read-only until signed backend/Vault exists.
 * This module NEVER fetches candles, touches Flow Guard/DLS/STRONG state,
 * sends Binance orders, or accepts Binance API secrets in the browser.
 */
(function(global){
"use strict";
const state={active:false,data:null,loading:false,lastFetch:0,lastError:null,
 selected:null,tab:"w1dsummary",requestSeq:0};
const el=id=>document.getElementById(id);
const html=s=>String(s===null||s===undefined?"":s).replace(/[&<>"']/g,
 c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=(v,n=2)=>v===null||v===undefined||v===""||!Number.isFinite(Number(v))?"N/A":
 Number(v).toLocaleString("en-US",{minimumFractionDigits:n,maximumFractionDigits:n});
const usdt=v=>v===null||v===undefined?"N/A":
 (Number(v)>=0?"+":"-")+"$"+fmt(Math.abs(Number(v)),4);
const pct=v=>v===null||v===undefined?"N/A":fmt(v,2)+"%";
const ts=ms=>!ms?"—":new Date(Number(ms)).toLocaleString("id-ID",{timeZone:"Asia/Jakarta",dateStyle:"short",timeStyle:"short"});
const set=(name,v)=>{const x=el(name);if(x)x.textContent=String(v);};
function isSelected(){return state.active;}
function activate(on){state.active=!!on;
 if(on){renderTop();render();load(false);}
}
function row(tr,values){values.forEach(v=>{const td=document.createElement("td");td.textContent=String(v);tr.appendChild(td);});}
function tbody(id,records,fallback,colCount){const n=el(id);if(!n)return;n.replaceChildren();if(!records.length){
 const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=colCount;td.className="empty";td.textContent=fallback;tr.appendChild(td);n.appendChild(tr);
 }else records.forEach(r=>{const tr=document.createElement("tr");row(tr,r);n.appendChild(tr);});}
function amountNow(){
 const ref=el("w1dMarginReference"),target=el("w1dLeverageTarget");
 if(!ref||!target)return;
 const m=Number(ref.value),l=Number(target.value);
 const okay=Number.isFinite(m)&&m>=1&&m<=1000000&&Number.isInteger(l)&&l>=1&&l<=125;
 set("w1dTargetNotional",okay?"$"+fmt(m*l,2):"INVALID");
 [50,25,10].forEach(cap=>set("w1dExample"+cap,okay?"$"+fmt(m*l/Math.min(l,cap),2):"—"));
 if(global.W1DOperations&&global.W1DOperations.sizingStatus)
   set("w1dSizeMode",global.W1DOperations.sizingStatus());
 else set("w1dSizeMode","PREVIEW LOKAL · BELUM DISIMPAN DI LIVE");
}
function statusTag(){const d=state.data;const l=d?.live,c=d?.controls;
 const fresh=d&&Number.isFinite(Date.parse(d.generated_at_utc))&&(Date.now()-Date.parse(d.generated_at_utc)<120000);
 if(!d)return "BELUM TERVERIFIKASI";
 if(!fresh)return "SNAPSHOT LAMA · READ-ONLY";
 if(l?.status==="NO_REGISTERED_ACCOUNTS")return "0 AKUN LIVE · PAUSE";
 if(l?.status==="PRIVATE_ACCOUNT_DATA_NOT_EXPOSED")return "LIVE PRIVAT · N/A";
 return "LIVE UNVERIFIED";
}
function renderTop(){
 if(!state.active)return;
 const d=state.data,p=d&&d.paper||{},l=d&&d.live||{};
 const close=p.closed===undefined?"—":p.closed,win=p.wins===undefined?"—":p.wins;
 set("activeStrategyTitle","W1D — LONG T+150");
 set("strategyContextTitle","W1D Paper ↔ Binance LIVE");
 set("strategyContextNote","Terpisah dari Flow Guard / DLS / STRONG · tanpa TP statis");
 set("stOpenLabel","W1D Paper Open / WR");
 set("stLongPerfLabel","W1D Paper · Closed / WR / Net");
 set("stShortPerfLabel","Binance LIVE · Verified / WR / Net");
 set("stPnlLabel","W1D Paper Net (USDT)");
 // These top-bar candidates belong to Flow Guard radar, NOT W1D signals.
 set("stMoving","—");set("stActionable","—");
 set("controlChip",d&&d.controls?
   "W1D "+String(d.controls.global_mode||"UNKNOWN")+" · "+String(d.controls.execution_gate||"UNKNOWN"):
   "W1D CONTROL UNVERIFIED");
 set("stOpen",p.open===undefined?"—":p.open);
 set("stWr",pct(p.wr_pct));
 set("stLongPerf",(p.closed===undefined?"—":p.closed+"t · "+pct(p.wr_pct)+" · "+usdt(p.net_pnl_usdt)));
 set("stShortPerf",l.status==="NO_REGISTERED_ACCOUNTS"?"0 akun · WR N/A · PnL N/A":
  "SIGNED LEDGER REQUIRED · N/A");
 set("stPnl",usdt(p.net_pnl_usdt));
 const net=el("stPnl");if(net)net.className=Number(p.net_pnl_usdt)>=0?"green":"red";
 set("stClosed",close);
 set("apiChip",state.lastError?"W1D SNAPSHOT ERROR":d?"W1D PAPER CONNECTED":"W1D CONNECTING");
 const dot=el("apiDot");if(dot)dot.className="dot "+(state.lastError?"bad":d?"ok":"");
 set("refreshChip","W1D "+(state.lastFetch?new Date(state.lastFetch).toLocaleTimeString("id-ID"):"—"));
 set("w1dStrategyStatus",statusTag());
}
function render(){
 if(!state.active)return;
 const d=state.data,p=d&&d.paper||{},l=d&&d.live||{},c=d&&d.controls||{};
 const stamp=d&&d.generated_at_utc?Date.parse(d.generated_at_utc):NaN;
 const ageMs=Date.now()-stamp,hasTime=Number.isFinite(stamp);
 set("w1dSnapshotAt",hasTime?new Date(stamp).toLocaleString("id-ID",{timeZone:"Asia/Jakarta",dateStyle:"medium",timeStyle:"short"})+" WIB":"TIDAK ADA SNAPSHOT");
 set("w1dSnapshotAge",hasTime?((Math.max(0,Math.round(ageMs/1000)))+" detik yang lalu"):"N/A");
 set("w1dPaperClosed",p.closed??"—");set("w1dPaperWins",p.wins??"—");
 set("w1dPaperLosses",p.losses??"—");set("w1dPaperWR",pct(p.wr_pct));set("w1dPaperNet",usdt(p.net_pnl_usdt));
 set("w1dLiveNet",usdt(l.net_pnl_usdt));set("w1dLiveWR",pct(l.wr_pct));
 set("w1dLiveClosed",l.verified_closed??"N/A");set("w1dLiveAccounts",
   l.connected===false?"0 akun":"N/A · privasi akun");
 const privateControl=global.W1DOperations&&global.W1DOperations.control||null;
 set("w1dGlobalMode",String(privateControl?.global_mode??c.global_mode??"UNKNOWN"));
 set("w1dGate",String(privateControl?.execution_gate??c.execution_gate??"UNKNOWN"));
 set("w1dDailyRisk",String(c.daily_loss_limit_usdt??"UNSET"));
 const warning=el("w1dWarning");
 if(warning){warning.textContent=state.lastError?
  "Gagal membaca snapshot W1D, jangan menganggap LIVE tersedia. "+state.lastError:
  (!hasTime||ageMs>120000?
   "Snapshot paper lebih dari 2 menit. Refresh di sini hanya memuat ulang snapshot dari VPS, bukan memanggil Binance.":
   "W1D PAPER adalah simulasi. LIVE belum memiliki akun Binance terverifikasi; WR/PnL LIVE tetap N/A.");}
 const egress=d&&d.binance_api_egress||{};
 set("w1dEgressIP",egress.ip||"BELUM TERVERIFIKASI");
 set("w1dEgressAsOf",egress.verified_at_utc||"N/A");
 if(!(global.W1DOperations&&global.W1DOperations.authorized))
 set("w1dAccountsState",l.status==="NO_REGISTERED_ACCOUNTS"?
  "Belum ada akun LIVE di database W1D — koneksi API tidak dapat diasumsikan dari Railway.":
  l.status==="PRIVATE_ACCOUNT_DATA_NOT_EXPOSED"?
  "Data akun disembunyikan pada endpoint publik. Perlu login backend W1D.":
  "Status akun belum terverifikasi.");
 if(d&&d.privacy) set("w1dPrivacyLabel","LIVE akun privat: N/A sampai tersedia authenticated viewer");
 const entries=[
  ["OPEN",p.open??"N/A",l.open??"N/A"],
  ["CLOSED",p.closed??"N/A",l.closed??"N/A"],
  ["WIN / LOSS",(p.wins??"N/A")+" / "+(p.losses??"N/A"),(l.wins??"N/A")+" / "+(l.losses??"N/A")],
  ["WIN RATE",pct(p.wr_pct),pct(l.wr_pct)],
  ["GROSS",usdt(p.gross_pnl_usdt),usdt(l.gross_pnl_usdt)],
  ["ENTRY + EXIT FEE",p.trading_fees_usdt===null||p.trading_fees_usdt===undefined?"N/A":"$"+fmt(p.trading_fees_usdt,4),
   l.trading_fees_usdt===null||l.trading_fees_usdt===undefined?"N/A":"$"+fmt(l.trading_fees_usdt,4)],
  ["FUNDING","TIDAK DIMODELKAN",usdt(l.funding_usdt)],
  ["NET PNL",usdt(p.net_pnl_usdt),usdt(l.net_pnl_usdt)]
 ];
 tbody("w1dParityRows",entries,"Belum ada data terverifikasi",3);
 const filtered=(Array.isArray(p.rows)?p.rows:[]).filter(x=>
  (!el("w1dSearch")?.value||String(x.symbol).includes(el("w1dSearch").value.trim().toUpperCase()))&&
  (!el("w1dFilter")||el("w1dFilter").value==="ALL"||x.state===el("w1dFilter").value));
 tbody("w1dPaperRows",filtered.map(x=>[x.symbol,x.state,ts(x.entry_at_ms),
  x.entry_fill??"—",x.exit_fill??"—",usdt(x.net_pnl_usdt),x.exit_reason||"—"]),
  "Tidak ada trade W1D paper sesuai filter",7);
 if(!state.selected&&filtered.length)state.selected=filtered[0].symbol;
 set("w1dHistoryCount",filtered.length+" baris snapshot · data PAPER, bukan LIVE");
 amountNow();
}
async function load(force){
 if(!state.active||state.loading)return;
 if(!force&&state.lastFetch&&Date.now()-state.lastFetch<9500){render();return;}
 state.loading=true;const seq=++state.requestSeq;
 const c=new AbortController(),t=setTimeout(()=>c.abort(),8500);
 try{
  const r=await fetch("/w1d-stage12-summary.json",{cache:"no-store",signal:c.signal});
  if(!r.ok)throw Error("snapshot HTTP "+r.status);
  const x=await r.json();
  if(x.schema!=="w1d.paper-live.dashboard.v1"||!x.paper||!x.live)throw Error("W1D_SCHEMA_NOT_VERIFIED");
  if(seq!==state.requestSeq)return;
  const old=state.data&&state.data.generated_at_utc;
  state.data=x;state.lastFetch=Date.now();state.lastError=null;
  if(state.active){renderTop();if(old!==x.generated_at_utc||force)render();else render();}
 }catch(e){
  state.lastError=String(e.message||"READ_ONLY_ERROR");
  if(state.active){renderTop();render();}
 }finally{clearTimeout(t);state.loading=false;}
}
function chartMarkers(symbol){
 const p=state.data&&state.data.paper,records=p&&p.rows||[];
 return records.filter(r=>r.symbol===symbol).map(r=>({
  id:"W1D-"+r.source_id,symbol:r.symbol,side:"LONG",
  time:Number(r.entry_at_ms),price:Number(r.entry_fill),isOpen:r.state==="OPEN",
  status:r.state,source:"W1D_PAPER"}))
 .filter(x=>x.time>0&&x.price>0);
}
function init(){
 ["w1dMarginReference","w1dLeverageTarget"].forEach(k=>{
  const e=el(k);if(e)e.addEventListener("input",()=>{
   amountNow();
   if(global.W1DOperations&&global.W1DOperations.onSizingEdit)
     global.W1DOperations.onSizingEdit();
  });
 });
 const b=el("w1dRefresh");if(b)b.addEventListener("click",()=>load(true));
 ["w1dSearch","w1dFilter"].forEach(k=>{const e=el(k);if(e)e.addEventListener(
  k==="w1dSearch"?"input":"change",render);});
 const copy=el("w1dCopyIP");if(copy)copy.addEventListener("click",async()=>{
  const value=state.data&&state.data.binance_api_egress&&state.data.binance_api_egress.ip;
  if(!value){set("w1dIpCopyState","IP belum diverifikasi");return;}
  try{await navigator.clipboard.writeText(value);set("w1dIpCopyState","IP tersalin");}
  catch(e){set("w1dIpCopyState","Salin manual dari kolom IP");}
 });
 amountNow();
}
global.W1DTab={init,activate,load,render,renderTop,chartMarkers,isSelected,
 previewNotional:amountNow,getSelectedSymbol:()=>state.selected};
})(window);