/* W1D Stage12: static read-only snapshot. No control/order API. */
(function(){
'use strict';
const id=x=>document.getElementById(x);
const state={data:null,rows:[]};
function n(v,d=2){if(v===null||v===undefined||v==='')return 'N/A';const x=Number(v);return Number.isFinite(x)?x.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}):'N/A';}
function whole(v){return v===null||v===undefined?'N/A':Number(v).toLocaleString('en-US');}
function money(v){if(v===null||v===undefined)return 'N/A';let x=Number(v);return Number.isFinite(x)?(x>=0?'+':'−')+'$'+n(Math.abs(x),4):'N/A';}
function percent(v){return v===null||v===undefined?'N/A':n(v,2)+'%';}
function date(ms){if(ms===null||ms===undefined)return '—';let d=new Date(Number(ms));return Number.isNaN(d.getTime())?'—':d.toLocaleString('id-ID',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Jakarta'})+' WIB';}
function value(k,p){return p&&Object.hasOwn(p,k)?p[k]:null;}
function text(k,v){const node=id(k);if(node)node.textContent=String(v);}
function moneyClass(node,v){node.classList.remove('positive','negative');if(v===null||v===undefined)return;let x=Number(v);if(x>0)node.classList.add('positive');if(x<0)node.classList.add('negative');}
function cell(tr,content){const td=document.createElement('td');td.textContent=String(content);tr.appendChild(td);return td;}
function renderTable(d){
 const p=d.paper,l=d.live,tbody=id('compareRows');tbody.replaceChildren();
 const entries=[
  ['Posisi OPEN',whole(value('open',p)),whole(value('open',l)),'OPEN saat snapshot, bukan jumlah order'],
  ['Posisi CLOSED',whole(value('closed',p)),whole(value('closed',l)),'CLOSED paper vs VERIFIED CLOSED LIVE'],
  ['WIN',whole(value('wins',p)),whole(value('wins',l)),'Net PnL positif'],
  ['LOSS',whole(value('losses',p)),whole(value('losses',l)),'Net PnL negatif'],
  ['BREAK-EVEN',whole(value('breakeven',p)),whole(value('breakeven',l)),'Dihitung dalam penyebut WR'],
  ['WIN RATE',percent(value('wr_pct',p)),percent(value('wr_pct',l)),'WIN / CLOSED · hanya sertifikasi LIVE'],
  ['GROSS PNL',money(value('gross_pnl_usdt',p)),money(value('gross_pnl_usdt',l)),'Sebelum fee transaksi'],
  ['TRADING FEE','−$'+n(value('trading_fees_usdt',p),4),value('trading_fees_usdt',l)===null?'N/A':'−$'+n(value('trading_fees_usdt',l),4),'Fee masuk dan keluar'],
  ['FUNDING','Tidak dimodelkan',money(value('funding_usdt',l)),'Funding Binance memerlukan riwayat lengkap'],
  ['NET PNL',money(value('net_pnl_usdt',p)),money(value('net_pnl_usdt',l)),'Gross − trading fee + funding (LIVE)'],
 ];
 entries.forEach(row=>{const tr=document.createElement('tr');row.forEach(x=>cell(tr,x));tbody.appendChild(tr);});
}
function renderHistory(){
 let s=(id('symbolFilter').value||'').trim().toUpperCase(),filter=id('stateFilter').value;
 const rows=state.rows.filter(r=>(!s||r.symbol.includes(s))&&(filter==='ALL'||r.state===filter));
 const tbody=id('historyRows');tbody.replaceChildren();
 for(const r of rows){
  const tr=document.createElement('tr');
  let pair=cell(tr,r.symbol),kind=cell(tr,r.state),entry=cell(tr,r.entry_fill===null?'—':'$'+n(r.entry_fill,5));
  const exit=cell(tr,r.exit_fill===null?'—':'$'+n(r.exit_fill,5));
  const pnl=cell(tr,money(r.net_pnl_usdt));moneyClass(pnl,r.net_pnl_usdt);
  cell(tr,r.exit_reason||'—');tbody.appendChild(tr);
 }
 if(!rows.length){const tr=document.createElement('tr');let td=cell(tr,'Tidak ada posisi sesuai filter');td.colSpan=6;tbody.appendChild(tr);}
 text('historyMeta',whole(rows.length)+' baris ditampilkan · maksimal 100 posisi dari snapshot W1D. Sumber: paper, bukan Binance.');
}
function render(d){
 if(d.schema!=='w1d.paper-live.dashboard.v1'||!d.paper||!d.live)throw Error('SCHEMA_MISMATCH');
 state.data=d;state.rows=Array.isArray(d.paper.rows)?d.paper.rows:[];
 const p=d.paper,l=d.live;
 text('paperNet',money(p.net_pnl_usdt));moneyClass(id('paperNet'),p.net_pnl_usdt);
 text('paperClosed',whole(p.closed));text('paperWinLoss',whole(p.wins)+' / '+whole(p.losses));
 text('paperWr',percent(p.wr_pct));text('paperOpen',whole(p.open));
 text('liveNet',money(l.net_pnl_usdt));moneyClass(id('liveNet'),l.net_pnl_usdt);
 text('liveClosed',whole(l.verified_closed));text('liveWinLoss',whole(l.wins)+' / '+whole(l.losses));
 text('liveWr',percent(l.wr_pct));text('liveUnverified',whole(l.uncertified_closed));
 let reason=l.status==='NO_REGISTERED_ACCOUNTS'?'AKUN LIVE 0':l.status==='PRIVATE_ACCOUNT_DATA_NOT_EXPOSED'?'PRIVATE · N/A':'BELUM TERVERIFIKASI';
 text('liveStatus',reason);
 const paused=d.controls&&d.controls.global_mode==='PAUSE',disabled=d.controls&&d.controls.execution_gate==='DISABLED';
 text('systemStatus',paused&&disabled?'GLOBAL PAUSE · EXEC DISABLED':'STATUS '+String(d.controls?.global_mode||'UNKNOWN'));
 id('systemStatus').previousElementSibling?.classList.toggle('ok',paused&&disabled);
 const generated=new Date(d.generated_at_utc),valid=!Number.isNaN(generated.getTime());
 const age=valid?Date.now()-generated.getTime():Infinity;
 text('timestamp','Snapshot: '+(valid?generated.toLocaleString('id-ID',{dateStyle:'medium',timeStyle:'medium',timeZone:'Asia/Jakarta'})+' WIB':'waktu tidak diketahui'));
 text('freshness',age>120000?'SNAPSHOT LAMA':'SNAPSHOT READ-ONLY');
 const note=id('notice');
 if(!valid||age>600000){note.classList.add('error');}
 else note.classList.remove('error');
 note.textContent=l.status==='NO_REGISTERED_ACCOUNTS'?
  'LIVE belum terhubung: 0 akun Binance terdaftar. WR dan PnL LIVE = N/A. Data paper adalah simulasi.' :
  'LIVE tidak ditampilkan tanpa autentikasi/sertifikasi akun. Tidak ada order yang dapat dikirim dari halaman ini.';
 if(age>120000)note.textContent+=' Snapshot lebih dari 2 menit; Refresh hanya memuat ulang snapshot yang tersimpan.';
 renderTable(d);renderHistory();
}
async function refresh(){
 const btn=id('refresh');btn.disabled=true;btn.textContent='Mengambil snapshot…';
 try{
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),8000);
  let response;
  try{response=await fetch('/w1d-stage12-summary.json',{cache:'no-store',signal:controller.signal});}
  finally{clearTimeout(timeout);}
  if(!response.ok)throw Error('HTTP '+response.status);
  const d=await response.json();render(d);
 }catch(error){
  const note=id('notice');note.classList.add('error');
  note.textContent='Data snapshot W1D belum tersedia / gagal dibaca. Tidak ada angka LIVE yang diisi otomatis. '+String(error.message||'');
  text('systemStatus','DATA TIDAK TERSEDIA');
 }finally{btn.disabled=false;btn.textContent='↻ Refresh snapshot';}
}
id('refresh').addEventListener('click',refresh);
id('symbolFilter').addEventListener('input',renderHistory);
id('stateFilter').addEventListener('change',renderHistory);
refresh();
})();