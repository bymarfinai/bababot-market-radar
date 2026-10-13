/* Operational W1D + Strong LIVE panel. Read-only by default, authenticated UI control. */
(function (global) {
'use strict';
const BASE='https://core-prod.43-153-193-103.sslip.io/w1d';
let snapshot=null,runtime=null,busy=false,lastError='',requesting=false;
const hosts=[];
const el=id=>document.getElementById(id);
function adminToken(){
 const entered=hosts.map(h=>(h.querySelector('[data-hub-token]')?.value||'').trim()).find(Boolean);
 return entered || (el('w1dAdminToken')?.value||'').trim() ||
        (el('strongLiveToken')?.value||'').trim() ||
        (el('strongControlToken')?.value||'').trim() ||
        sessionStorage.getItem('baba_control_token_v1')||'';
}
const activityLabel=v=>({
 SCANNING_WAITING_SIGNAL:'SCANNING · MENUNGGU SINYAL',
 SCANNING_PAPER_EVENTS:'SCANNING · STRONG PAPER',
 PROCESSING_OR_CHECKING:'MEMERIKSA SINYAL / ORDER',
 PAUSED_ENTRIES:'PAUSE · ENTRY BERHENTI',
 WORKER_ERROR:'ERROR WORKER · CEK LOG',
 WORKER_HEARTBEAT_STALE:'WORKER TIDAK MERESPONS',
 BLOCKED_SHARED_RISK:'TERKUNCI OLEH SHARED RISK'
}[v]||'MENUNGGU STATUS WORKER');
function statusStrip(){
 let strip=el('liveRuntimeStrip');
 if(!strip){
  const anchor=document.querySelector('.strategy-shell')||document.querySelector('header');
  if(!anchor)return;
  strip=document.createElement('div');strip.id='liveRuntimeStrip';
  strip.className='live-runtime-strip';anchor.insertAdjacentElement('afterend',strip);
 }
 const w=runtime?.w1d,st=runtime?.strong,shared=runtime?.shared;
 strip.replaceChildren();
 const item=(label,value)=>{
  const x=document.createElement('div');const l=document.createElement('span'),v=document.createElement('strong');
  l.textContent=label;v.textContent=value;x.append(l,v);strip.appendChild(x);
 };
 item('W1D LIVE',w?w.mode+' · '+activityLabel(w.activity):'MENYAMBUNG…');
 item('STRONG LIVE',st?st.mode+' · '+activityLabel(st.activity):'MENYAMBUNG…');
 item('GLOBAL / RISK',shared?shared.mode+' / '+(shared.risk_state||'UNKNOWN'):'MENYAMBUNG…');
}
function cell(value){const x=document.createElement('td');x.textContent=value==null?'—':String(value);return x;}
function fillRows(target,rows,values,empty){
 const table=target.querySelector('tbody');if(!table)return;
 table.replaceChildren();
 if(!rows.length){const r=document.createElement('tr'),t=cell(empty);t.colSpan=values.length;r.appendChild(t);table.appendChild(r);return;}
 rows.forEach(obj=>{const tr=document.createElement('tr');values.forEach(k=>tr.appendChild(cell(typeof k==='function'?k(obj):obj[k])));table.appendChild(tr);});
}
function show(host){
 const token=adminToken(),s=snapshot,r=runtime;
 const set=(key,v)=>{const n=host.querySelector('[data-hub-'+key+']');if(n)n.textContent=v;};
 set('w1d',s?s.w1d.mode:r?.w1d.mode||'CONNECTING');set('strong',s?s.strong.mode:r?.strong.mode||'CONNECTING');
 set('w1d-activity',activityLabel(r?.w1d.activity));set('strong-activity',activityLabel(r?.strong.activity));
 set('shared',s?s.w1d.global_mode+' · '+s.risk.status:r?r.shared.mode+' / '+r.shared.risk_state:'CONNECTING');
 set('risk',s?s.risk.configured_cap_usdt+' USDT · '+(s.risk.current_day_state||s.risk.reason):r?(r.shared.daily_cap_usdt||'—')+' USDT':'—');
 set('w1d-orders',s?String(s.orders.w1d_orders):'—');
 set('strong-orders',s?String(s.orders.strong_entry_orders)+' / '+String(s.orders.strong_exit_orders):'—');
 set('pending-risk',s?String(s.orders.w1d_pending_risk_exits+s.orders.strong_pending_risk_exits):'—');
 set('strong-worker',s?(s.strong.worker_healthy?'HEALTHY':'NOT HEALTHY'):'—');
 set('message',lastError||(!token?'Status LIVE sudah terlihat. Masukkan Admin Token di panel ini lalu tekan VERIFY agar RUN/PAUSE bisa digunakan.':
    !s?'Token ada, tetapi belum terverifikasi. Tekan VERIFY ACCESS.':'TOKEN VERIFIED · Kendali siap digunakan. CLOSE tetap aktif saat entry PAUSE.'));
 host.querySelectorAll('[data-hub-verified]').forEach(x=>x.textContent=s?'VERIFIED':'NOT VERIFIED');
 fillRows(host.querySelector('[data-hub-table="positions"]'),s?s.positions:[],
   ['strategy','symbol','side','state','remaining_qty','entry_avg'],'Belum ada posisi LIVE');
 fillRows(host.querySelector('[data-hub-table="ownership"]'),s?s.ownership:[],
   ['strategy','symbol','state','signal_key'],'Tidak ada simbol yang sedang dimiliki');
 fillRows(host.querySelector('[data-hub-table="orders"]'),s?s.recent_orders:[],
   ['strategy','symbol','side','state','requested_qty','executed_qty'],'Belum ada order LIVE');
 host.querySelectorAll('button[data-dual]').forEach(b=>{b.disabled=busy;});
 host.querySelectorAll('[data-hub-verify]').forEach(b=>b.disabled=busy||requesting);
}
function render(){statusStrip();hosts.forEach(show);}
async function call(path,options){
 const token=adminToken();if(!token)throw Error('Admin Token dibutuhkan');
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8500);
 try{
  const res=await fetch(BASE+path,{cache:'no-store',signal:controller.signal,
    method:options?.method||'GET',headers:{'X-Baba-Control-Token':token,
      ...(options?.body?{'Content-Type':'application/json'}:{})},
    ...(options?.body?{body:JSON.stringify(options.body)}:{})});
  const json=await res.json();
  if(!res.ok)throw Error(json.error||'HTTP '+res.status);
  return json;
 }finally{clearTimeout(timeout);}
}
async function refreshPublic(){
 try{
  const res=await fetch(BASE+'/live/runtime',{cache:'no-store'});
  if(!res.ok)throw Error('HTTP '+res.status);
  const data=await res.json();runtime=data.live_runtime||null;
 }catch(err){
  runtime=null;
  if(!adminToken())lastError='Status publik tidak tersedia: '+String(err.message||err);
 }
 render();
}
async function refresh(){
 await refreshPublic();
 if(requesting)return;
 if(!adminToken()){snapshot=null;render();return;}
 requesting=true;
 try{const result=await call('/live/overview');snapshot=result.live_overview;lastError='';}
 catch(e){lastError='Status LIVE private gagal: '+String(e.message||e);snapshot=null;}
 finally{requesting=false;render();}
}
async function verify(){
 const t=adminToken();
 if(!t){lastError='Isi Admin Token di kolom panel ini lalu tekan VERIFY ACCESS.';render();hosts[0]?.querySelector('[data-hub-token]')?.focus();return;}
 if(busy)return;
 busy=true;lastError='Memverifikasi Admin Token…';render();
 try{
  const answer=await call('/live/overview');
  if(!answer.live_overview)throw Error('Backend tidak mengirim data LIVE');
  sessionStorage.setItem('baba_control_token_v1',t);
  ['w1dAdminToken','strongControlToken','strongLiveToken'].forEach(id=>{if(el(id))el(id).value=t;});
  snapshot=answer.live_overview;lastError='';
  global.W1DOperations?.refresh(true);
  global.StrongLiveStage5?.load();
 }catch(e){snapshot=null;lastError='VERIFY gagal: '+String(e.message||e);}
 finally{busy=false;render();}
}
async function act(action){
 if(busy)return;
 if(!snapshot){
  lastError='Untuk RUN/PAUSE, isi Admin Token dan tekan VERIFY ACCESS dahulu.';
  render();hosts[0]?.querySelector('[data-hub-token]')?.focus();return;
 }
 const isRun=action==='run-both';
 if(isRun&&(runtime?.shared.risk_state!=='MONITORING'||!snapshot.strong.worker_healthy)){
  lastError='RUN ditolak sebelum dikirim: risk harian atau worker Strong belum siap.';render();return;
 }
 const question=isRun?
  'RUN kedua strategi LIVE? W1D dan Strong akan menerima entry baru sesuai sinyal PAPER masing-masing, dengan daily risk $5 bersama.':
  'PAUSE entry W1D dan Strong sekaligus? EXIT posisi milik kedua strategi tetap berjalan.';
 if(!global.confirm(question))return;
 busy=true;lastError='Memproses '+action+'…';render();
 try{
  await call('/live/control/'+action,{method:'POST',body:{
   expected_strong_updated_at:snapshot.strong.updated_at}});
  lastError='';await refresh();
 }catch(e){lastError='Kontrol ditolak: '+String(e.message||e);await refresh();if(!lastError)lastError='Permintaan gagal; periksa status aktual.';}
 finally{busy=false;render();}
}
function inject(pane){
 if(!pane||pane.querySelector('[data-live-ops-hub]'))return;
 const root=document.createElement('section');root.className='live-ops-hub';
 root.dataset.liveOpsHub='true';
 root.innerHTML=`<div class="live-ops-heading"><div><div class="live-ops-kicker">BINANCE FUTURES · SHARED ACCOUNT</div><strong>W1D + Strong LIVE Operations</strong></div><span class="live-ops-tip">Kontrol entry independen · shared risk $5</span></div>
 <div class="live-ops-auth"><label>ADMIN TOKEN <input type="password" autocomplete="off" spellcheck="false" data-hub-token placeholder="Paste Admin Token di sini"></label><button type="button" data-hub-verify>VERIFY ACCESS</button><span data-hub-verified>NOT VERIFIED</span></div>
 <div class="live-ops-stats">
  <div><span>W1D ENTRY</span><strong data-hub-w1d>—</strong><small data-hub-w1d-activity>—</small></div><div><span>STRONG ENTRY</span><strong data-hub-strong>—</strong><small data-hub-strong-activity>—</small></div>
  <div><span>GLOBAL / DAY RISK</span><strong data-hub-shared>—</strong></div><div><span>DAILY LOSS CAP</span><strong data-hub-risk>—</strong></div>
  <div><span>W1D ORDERS</span><strong data-hub-w1d-orders>—</strong></div><div><span>STRONG ENTRY / EXIT</span><strong data-hub-strong-orders>—</strong></div>
  <div><span>PENDING RISK EXIT</span><strong data-hub-pending-risk>—</strong></div><div><span>STRONG WORKER</span><strong data-hub-strong-worker>—</strong></div>
 </div>
 <div class="live-ops-actions"><button type="button" data-dual="run-both">RUN BOTH</button>
 <button type="button" data-dual="pause-all">PAUSE ALL ENTRIES</button><button type="button" data-hub-refresh>REFRESH STATUS</button></div>
 <p class="live-ops-message" data-hub-message>Masukkan Admin Token untuk membaca status.</p>
 <div class="live-ops-table-wrap"><strong>Posisi aktual per strategi</strong><div class="live-ops-scroll"><table data-hub-table="positions"><thead><tr><th>Engine</th><th>Symbol</th><th>Side</th><th>State</th><th>Remaining Qty</th><th>Entry Avg</th></tr></thead><tbody></tbody></table></div></div>
 <div class="live-ops-table-wrap"><strong>Kepemilikan simbol (anti-double-entry)</strong><div class="live-ops-scroll"><table data-hub-table="ownership"><thead><tr><th>Owner</th><th>Symbol</th><th>State</th><th>Source ID</th></tr></thead><tbody></tbody></table></div></div>
 <div class="live-ops-table-wrap"><strong>Ledger order LIVE terbaru (max 50)</strong><div class="live-ops-scroll"><table data-hub-table="orders"><thead><tr><th>Engine</th><th>Symbol</th><th>Side</th><th>Order State</th><th>Requested Qty</th><th>Executed Qty</th></tr></thead><tbody></tbody></table></div></div>
 <p class="live-ops-note">Tombol PAUSE hanya menghentikan entry baru. Tidak membatalkan paper, tidak membatalkan CLOSE, dan tidak mengubah batas risiko global. Semua angka bersumber dari backend, bukan PnL simulasi.</p>`;
 pane.prepend(root);hosts.push(root);
 root.querySelectorAll('button[data-dual]').forEach(b=>b.addEventListener('click',()=>act(b.dataset.dual)));
 root.querySelector('[data-hub-refresh]').addEventListener('click',refresh);
 root.querySelector('[data-hub-verify]').addEventListener('click',verify);
 root.querySelector('[data-hub-token]').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();verify();}});

}
function init(){
 const st=document.createElement('style');st.textContent=`
 .live-runtime-strip{display:flex;gap:12px;flex-wrap:wrap;padding:8px 12px;background:#10202d;border-bottom:1px solid #36506c;color:#dbe8fa}
 .live-runtime-strip>div{min-width:180px;flex:1}.live-runtime-strip span{display:block;color:#91a7bb;font-size:8px}.live-runtime-strip strong{display:block;font-size:10px;margin-top:3px}
 .live-ops-auth{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:12px 0;padding:11px;background:#111d2a;border:1px solid #324963;font-size:9px}
 .live-ops-auth input{background:#0d1520;border:1px solid #436184;color:#fff;border-radius:4px;padding:8px;font-size:11px;min-width:200px}
 .live-ops-auth button{background:#2e577c;border:1px solid #5686b1;color:#fff;border-radius:4px;padding:8px;cursor:pointer}
 .live-ops-auth span{color:#aac3df;font-size:9px}
 .live-ops-stats small{display:block;color:#8aafd0;font-size:9px;margin-top:4px}
 .live-ops-hub{padding:13px;border:1px solid #293544;background:#0d131b;margin:10px 12px 14px;border-radius:6px;color:#eaecef}
 .live-ops-heading,.live-ops-actions{display:flex;justify-content:space-between;align-items:center;gap:9px;flex-wrap:wrap}
 .live-ops-heading strong{font-size:13px}.live-ops-kicker{font-size:8px;letter-spacing:.05em;color:#70a4e6;margin-bottom:4px}
 .live-ops-tip,.live-ops-note,.live-ops-message{font-size:9px;color:#9caabe;line-height:1.5}
 .live-ops-stats{display:grid;grid-template-columns:repeat(4,minmax(115px,1fr));gap:7px;margin:11px 0}
 .live-ops-stats>div{border:1px solid #253040;background:#111c27;padding:9px;min-width:0}
 .live-ops-stats span{display:block;color:#91a1b2;font-size:8px}.live-ops-stats strong{display:block;font-size:12px;margin-top:5px;overflow-wrap:anywhere}
 .live-ops-actions{justify-content:flex-start}.live-ops-actions button{background:#19293a;color:#dbe8fa;border:1px solid #36506c;border-radius:4px;font-size:10px;padding:8px 11px;cursor:pointer}
 .live-ops-actions button[data-dual="run-both"]{color:#2ce5a8;border-color:#156e51}.live-ops-actions button[data-dual="pause-all"]{color:#ffcb69;border-color:#77582a}
 .live-ops-actions button:disabled{opacity:.4;cursor:not-allowed}.live-ops-table-wrap{margin-top:13px;font-size:10px}
 .live-ops-scroll{overflow-x:auto;margin-top:6px}.live-ops-hub table{width:100%;border-collapse:collapse;font-size:9px}
 .live-ops-hub th,.live-ops-hub td{border-bottom:1px solid #253040;padding:8px;text-align:left;overflow-wrap:anywhere}.live-ops-hub th{color:#91a1b2;font-weight:600}
 @media(max-width:900px){.live-ops-stats{grid-template-columns:repeat(2,minmax(130px,1fr))}}
 `;document.head.appendChild(st);
 inject(document.querySelector('[data-pane="w1dcontrols"]'));
 inject(document.querySelector('[data-pane="strongcontrol"]'));
 ['w1dAdminToken','strongControlToken'].forEach(id=>el(id)?.addEventListener('input',()=>{render();refresh();}));
 refresh();setInterval(refresh,12000);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
global.LiveOpsHub={refresh,get snapshot(){return snapshot;}};
})(window);
