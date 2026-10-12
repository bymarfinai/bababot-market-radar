/* W1D Operations: authenticated private account admin; no direct Binance order API.
 * API Key/Secret exist only in the form until HTTPS POST, then fields cleared.
 * RUN is an audited backend request which is rejected until authorization/
 * verified Binance account, emergency SL and actual executor are ready.
 */
(function(global){
"use strict";
const BASE="https://core-prod.43-153-193-103.sslip.io/w1d";
const el=k=>document.getElementById(k);
const ctx={authorized:false,busy:false,lastRead:0,status:null,accounts:[],
 positions:[],orders:[],message:"",pendingAction:null,
 sizing:null,sizingEdited:false,sizingLoaded:false};
const text=(id,x)=>{if(el(id))el(id).textContent=String(x??"—");};
const token=()=>(el("w1dAdminToken")?.value||"").trim()||
 sessionStorage.getItem("baba_control_token_v1")||"";
const ACTION_LABELS={
 w1dAuthorize:["VERIFY ACCESS","CHECKING ADMIN…"],
 w1dAddAccount:["+ Add Account","ADDING ACCOUNT…"],
 w1dSaveKeys:["SAVE TO ENCRYPTED VAULT","ENCRYPTING & SAVING…"],
 w1dVerifyBinance:["VERIFY BINANCE (GET ONLY)","VERIFYING BINANCE…"],
 w1dPause:["PAUSE W1D","SAVING PAUSE…"],
 w1dRun:["RUN W1D LIVE","CHECKING RUN GATES…"],
 w1dControlRefresh:["CHECK BACKEND","REFRESHING STATUS…"],
 w1dSaveSizing:["SAVE GLOBAL DRAFT","SAVING DRAFT…"],
 w1dReloadSizing:["RELOAD SAVED","LOADING SAVED…"]
};
function busyUi(){
 for(const [id,labels] of Object.entries(ACTION_LABELS)){
  const b=el(id);if(!b)continue;
  const active=ctx.busy&&ctx.pendingAction===id;
  b.disabled=ctx.busy||
    (id==="w1dSaveSizing"&&!sizingDirty()) ||
    (id==="w1dReloadSizing"&&!ctx.authorized);
  b.classList.toggle("is-busy",active);
  b.textContent=active?labels[1]:labels[0];
  if(active)b.setAttribute("aria-busy","true");
  else b.removeAttribute("aria-busy");
 }
}
function sizingDirty(){
 if(!ctx.sizingLoaded||!ctx.sizing)return false;
 const d=ctx.sizing;
 const margin=el("w1dMarginReference")?.value||"";
 const lev=el("w1dLeverageTarget")?.value||"";
 return Number(margin)!==Number(d.reference_margin_usdt??"")||
       Number(lev)!==Number(d.desired_leverage??"");
}
function sizingStatus(){
 if(!ctx.authorized)return "LOGIN REQUIRED · GLOBAL DRAFT NOT LOADED";
 if(!ctx.sizingLoaded)return "LOADING GLOBAL DRAFT";
 return sizingDirty()?"UNSAVED CHANGES · NOT APPLIED":
  ctx.sizing?.saved?"DRAFT SAVED v"+ctx.sizing.version+" · NOT LIVE":"NOT SAVED · NOT LIVE";
}
function sizingDisplay(){
 text("w1dSizingSaveState",sizingStatus());
 text("w1dSizeMode",sizingStatus());
 text("w1dSizingVersion",ctx.sizing?.version??"—");
 text("w1dSizingSavedAt",ctx.sizing?.saved_at?
  new Date(ctx.sizing.saved_at).toLocaleString("id-ID",{timeZone:"Asia/Jakarta"}):"—");
 text("w1dSizingLiveNotice",
  ctx.sizing?.active_sizing_state==="CONFIGURED"?
  "Active sizing exists separately; draft edit DOES NOT change exchange leverage.":
  "Active LIVE profile UNCONFIGURED. Saving draft DOES NOT sync Binance or enable RUN.");
}
function syncSizingDraft(saved){
 ctx.sizing=saved;ctx.sizingLoaded=true;
 if(!ctx.sizingEdited&&saved&&saved.saved){
  const m=el("w1dMarginReference"),l=el("w1dLeverageTarget");
  if(m)m.value=String(saved.reference_margin_usdt);
  if(l)l.value=String(saved.desired_leverage);
 }
 if(!sizingDirty())ctx.sizingEdited=false;
 sizingDisplay();
 if(global.W1DTab&&global.W1DTab.previewNotional)
  global.W1DTab.previewNotional();
}
const fmt=(x,n=4)=>x===null||x===undefined||x===""?"N/A":
 Number(x).toLocaleString("en-US",{minimumFractionDigits:n,maximumFractionDigits:n});
const badCode=e=>String(e.message||"UNAVAILABLE").replace(/[^A-Z0-9_:,-]/g,"").slice(0,350);
function feedback(message,bad=false){
 ctx.message=message;
 text("w1dControlAction",message);text("w1dAccountAction",message);
 text("w1dKeyResult",message);
 const status=el("w1dControlAction");
 if(status)status.style.color=bad?"#f6465d":"#0ecb81";
}
function authorized(){
 if(!token())throw Error("AUTH_REQUIRED: Isi Admin Token di tab API & Accounts");
}
async function api(method,path,payload){
 authorized();
 const c=new AbortController(),timer=setTimeout(()=>c.abort(),path.endsWith("/verify")?45000:14000);
 try{
  const res=await fetch(BASE+path,{
    method,mode:"cors",credentials:"omit",cache:"no-store",signal:c.signal,
    headers:{"X-Baba-Control-Token":token(),...(method!=="GET"?
      {"Content-Type":"application/json"}:{})},
    ...(method!=="GET"?{body:JSON.stringify(payload??{})}:{})
  });
  const response=await res.json().catch(()=>({error:"INVALID_SERVER_RESPONSE"}));
  if(!res.ok||response.ok!==true)
   throw Error(response.error||("HTTP_"+res.status));
  return response;
 }finally{clearTimeout(timer);}
}
function tcell(tr,value){
 const cell=document.createElement("td");cell.textContent=String(value??"—");
 tr.appendChild(cell);return cell;
}
function table(id,rows,empty,cols){
 const tb=el(id);if(!tb)return;tb.replaceChildren();
 if(!rows.length){const tr=document.createElement("tr"),td=document.createElement("td");
 td.colSpan=cols;td.className="empty";td.textContent=empty;tr.appendChild(td);tb.appendChild(tr);return}
 rows.forEach(row=>{const tr=document.createElement("tr");
 row.forEach(value=>tcell(tr,value));tb.appendChild(tr)});
}
function render(){
 busyUi();
 sizingDisplay();
 text("w1dAuthState",ctx.authorized?"AUTHORIZED · PRIVATE":"LOCKED");
 if(!ctx.authorized)return;
 const s=ctx.status||{};
 text("w1dGlobalMode",s.global_mode||"UNKNOWN");
 text("w1dGate",s.execution_gate||"UNKNOWN");
 text("w1dLiveAccounts",s.account_count===undefined?"N/A":s.account_count+" registered");
 const notVerified=ctx.accounts.filter(x=>x.futures_status!=="VERIFIED_READ_ONLY");
 text("w1dAccountsState",ctx.accounts.length?
  (notVerified.length?
   notVerified.length+" akun masih BELUM diverifikasi Binance. Pilih akun, klik VERIFY BINANCE (GET ONLY). Status IP UNVERIFIED berarti Binance belum diperiksa dari VPS, bukan bukti whitelist salah.":
   "Binance signed GET terverifikasi untuk akun terdaftar. LIVE RUN tetap dikunci menunggu execution gate dan proteksi.") :
  "0 akun Binance Futures pada W1D LIVE. Tambahkan nama akun lalu SAVE API Key ke Vault.");
 text("w1dOpenCount",ctx.positions.filter(x=>
   ["OPEN","OPENING","CLOSING","UNKNOWN"].includes(x.state)).length);
 table("w1dAccountRows",ctx.accounts.map(a=>[
   a.account_name,a.status,a.credential_state,
   a.futures_status+(a.futures_error?" · "+a.futures_error:
      a.futures_status==="NOT_VERIFIED"?" · CLICK VERIFY BINANCE":""),
   a.ip_restricted?"VERIFIED":"NOT YET VERIFIED",a.available_usdt??"N/A"
 ]),"Belum ada akun terdaftar. Klik + Add Account.",6);
 table("w1dLivePositionRows",ctx.positions.map(p=>[
   p.account_name,p.symbol,p.side,p.state,p.filled_entry_qty,p.exchange_remaining_qty,
   p.entry_avg??"—",p.financial_verification==="VERIFIED"?
      (p.verified_net_usdt??"N/A"):"N/A",p.financial_verification
 ]),"Tidak ada posisi LIVE di database W1D.",9);
 table("w1dOrderRows",ctx.orders.map(o=>[
   o.account_name,o.symbol,o.side,o.origin,o.order_type,o.state,
   o.requested_qty??"—",o.executed_qty??"—",o.average_fill_price??"—"
 ]),"Tidak ada order LIVE W1D.",9);
 const selector=el("w1dAccountSelect");if(selector){
  const previous=selector.value;selector.replaceChildren();
  const placeholder=document.createElement("option");placeholder.value="";
  placeholder.textContent="Pilih akun Binance";selector.appendChild(placeholder);
  ctx.accounts.forEach(a=>{const op=document.createElement("option");
   op.value=a.account_id;op.textContent=a.account_name+" · "+a.credential_state;
   selector.appendChild(op)});
  if(ctx.accounts.some(a=>a.account_id===previous))selector.value=previous;
 }
 const run=el("w1dRun"),pause=el("w1dPause");
 if(run){run.disabled=ctx.busy;run.title=(s.run_blockers||[]).join(", ")||"RUN requires live executor authorization"}
 if(pause)pause.disabled=ctx.busy;
 const blockers=(s.run_blockers||[]);
 if(blockers.length)text("w1dControlAction",
  ctx.message||"RUN LOCKED: "+blockers.join(" · ")+"; PAUSE tetap bisa disimpan.");
}
async function refresh(force=false,trigger="w1dAuthorize"){
 if(ctx.busy||(!force&&Date.now()-ctx.lastRead<8000))return;
 if(!token())return;
 ctx.busy=true;ctx.pendingAction=trigger;render();
 try{
  const [control,accounts,positions,orders,draft]=await Promise.all([
   api("GET","/status"),api("GET","/accounts"),
   api("GET","/positions"),api("GET","/orders"),api("GET","/sizing-draft")
  ]);
  ctx.status=control;ctx.accounts=accounts.accounts||[];
  ctx.positions=positions.positions||[];ctx.orders=orders.orders||[];
  syncSizingDraft(draft.sizing_draft);
  const firstAuthorization=!ctx.authorized;
  ctx.authorized=true;ctx.lastRead=Date.now();
  // Never erase signed Binance VERIFY success/error on ordinary polling.
  // Admin authorization != Binance exchange verification.
  if(firstAuthorization&&!ctx.message)
   feedback("ADMIN CONNECTED ONLY · Next: select account and click VERIFY BINANCE (GET ONLY). LIVE trade sender disabled.");
 }catch(e){ctx.authorized=false;feedback("AUTH/BACKEND FAILED: "+badCode(e),true);}
 finally{ctx.busy=false;ctx.pendingAction=null;render();}
}
async function invoke(action,fn,clearSecrets=false,buttonId=null){
 if(ctx.busy)return;
 ctx.busy=true;ctx.pendingAction=buttonId;
 feedback(action+" · SEDANG DIPROSES…");
 render();
 try{
  const x=await fn();
  ctx.message="";
  feedback(action+" · VERIFIED BY W1D BACKEND"+(x.reason?" · "+x.reason:""));
  return x;
 }catch(e){feedback(action+" FAILED: "+badCode(e),true);return null;}
 finally{
  if(clearSecrets){if(el("w1dBinanceKey"))el("w1dBinanceKey").value="";
   if(el("w1dBinanceSecret"))el("w1dBinanceSecret").value="";}
  ctx.busy=false;ctx.pendingAction=null;ctx.lastRead=0;render();
 }
}
async function saveSizing(){
 if(!ctx.authorized){feedback("VERIFY ACCESS dulu sebelum menyimpan sizing draft",true);return;}
 if(!ctx.sizingLoaded){feedback("DRAFT NOT LOADED: klik CHECK BACKEND terlebih dahulu",true);return;}
 const raw=el("w1dMarginReference")?.value?.trim();
 const lv=Number(el("w1dLeverageTarget")?.value);
 if(!raw||!/^(?:[0-9]+)(?:\.[0-9]{1,2})?$/.test(raw)||Number(raw)<1||
    Number(raw)>1000000||!Number.isInteger(lv)||lv<1||lv>125){
  feedback("SIZING INVALID: margin $1–$1,000,000 (maksimal 2 desimal); leverage integer 1–125",true);
  return;
 }
 if(!sizingDirty())return;
 const result=await invoke("SAVE GLOBAL DRAFT",
  ()=>api("POST","/sizing-draft",{
    reference_margin_usdt:raw,desired_leverage:lv,
    expected_version:ctx.sizing.version
  }),false,"w1dSaveSizing");
 if(result&&result.sizing_draft){
  ctx.sizingEdited=false;syncSizingDraft(result.sizing_draft);
  feedback("SAVED v"+result.sizing_draft.version+" · DATABASE VERIFIED · NOT APPLIED TO BINANCE");
 }
}
async function reloadSizing(){
 if(sizingDirty()&&!global.confirm("Buang perubahan modal/leverage yang belum disimpan?"))return;
 ctx.sizingEdited=false;
 const result=await invoke("RELOAD SAVED",()=>api("GET","/sizing-draft"),false,"w1dReloadSizing");
 if(result?.sizing_draft){
  syncSizingDraft(result.sizing_draft);
  feedback("DRAFT RELOADED FROM DATABASE v"+result.sizing_draft.version);
 }
}
function bind(){
 const auth=el("w1dAuthorize");
 if(auth)auth.addEventListener("click",()=>refresh(true,"w1dAuthorize"));
 const add=el("w1dAddAccount");
 if(add)add.addEventListener("click",async()=>{
  const name=el("w1dNewNickname")?.value.trim();
  if(!name){feedback("Nama akun wajib diisi",true);return;}
  const r=await invoke("ADD ACCOUNT",()=>api("POST","/accounts",{account_name:name}),false,"w1dAddAccount");
  if(r){el("w1dNewNickname").value="";await refresh(true);}
 });
 const save=el("w1dSaveKeys");
 if(save)save.addEventListener("click",async()=>{
  const aid=el("w1dAccountSelect")?.value||"";
  const key=el("w1dBinanceKey")?.value||"";
  const secret=el("w1dBinanceSecret")?.value||"";
  if(!aid||!key||!secret){feedback("Pilih akun dan isi API Key serta API Secret.",true);return;}
  if(!global.confirm("Enkripsi API Key akun terpilih ke VPS W1D Vault? LIVE trading tetap DISABLED."))return;
  const result=await invoke("ENCRYPTED VAULT",()=>api("POST",
    "/accounts/"+encodeURIComponent(aid)+"/credentials",
    {api_key:key,api_secret:secret}),true,"w1dSaveKeys");
  if(result)await refresh(true);
 });
 const verify=el("w1dVerifyBinance");
 if(verify)verify.addEventListener("click",async()=>{
  const aid=el("w1dAccountSelect")?.value;
  if(!aid){feedback("Pilih akun untuk verifikasi read-only Binance",true);return;}
  const result=await invoke("SIGNED FUTURES VERIFY",()=>api("POST",
   "/accounts/"+encodeURIComponent(aid)+"/verify",{}),false,"w1dVerifyBinance");
  if(result)await refresh(true);
 });
 const pause=el("w1dPause");
 if(pause)pause.addEventListener("click",async()=>{
  const result=await invoke("PAUSE W1D",()=>api("POST","/control/pause",{}),false,"w1dPause");
  if(result)await refresh(true);
 });
 const run=el("w1dRun");
 if(run)run.addEventListener("click",async()=>{
  const result=await invoke("RUN REQUEST",()=>api("POST","/control/run",{}),false,"w1dRun");
  if(result)await refresh(true);
 });
 const refreshB=el("w1dControlRefresh");
 if(refreshB)refreshB.addEventListener("click",()=>refresh(true,"w1dControlRefresh"));
  const saveDraftButton=el("w1dSaveSizing");if(saveDraftButton)saveDraftButton.addEventListener("click",saveSizing);
  const reloadDraftButton=el("w1dReloadSizing");if(reloadDraftButton)reloadDraftButton.addEventListener("click",reloadSizing);
}
bind();
global.W1DOperations={refresh,saveSizing,reloadSizing,
 onSizingEdit(){ctx.sizingEdited=true;sizingDisplay();busyUi();},
 sizingStatus, get control(){return ctx.status},
 get authorized(){return ctx.authorized}};
})(window);