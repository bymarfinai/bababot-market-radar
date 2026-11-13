"use client";

import { useMemo, useState } from "react";
import type { StrongSnapshot, StrongTrade, StrongStrategy } from "@/lib/strong-types";
import {
  availableCloseMonths, classifyTrade, filterStrategyMonth, isRealized, journalOverview,
  matchedOverview, wibDateKey, type DateBucket, type JournalEquityPoint, type JournalOutcome
} from "@/lib/journal-analytics";

type OutcomeFilter = "ALL" | JournalOutcome;
const OUTCOMES: {value:OutcomeFilter;label:string}[] = [
  {value:"ALL",label:"All outcomes"}, {value:"WIN",label:"WIN"},
  {value:"LOSS",label:"LOSS"}, {value:"BREAKEVEN",label:"BE"},
  {value:"OPEN",label:"OPEN"}, {value:"UNRESOLVED",label:"DATA GAP"}
];
const fMoney=(n:number|null|undefined)=>
  n==null||!Number.isFinite(n)?"—":(n>0?"+":n<0?"−":"")+"$"+Math.abs(n).toFixed(2);
const fPercent=(n:number|null)=>n==null?"—":n.toFixed(2)+"%";
const fNumber=(n:number|null)=>n==null?"—":Number.isFinite(n)?n.toFixed(2):"∞";
const fDate=(n:number|null)=>n==null?"—":new Date(n).toLocaleString("id-ID",{
  timeZone:"Asia/Jakarta",day:"2-digit",month:"short",year:"numeric",
  hour:"2-digit",minute:"2-digit"
})+" WIB";
const duration=(n:number|null)=>{
  if(n==null)return "—";
  return n>=3_600_000?(n/3_600_000).toFixed(1)+"h":
    Math.round(n/60_000)+"m";
};
const pnlClass=(n:number|null)=>n==null?"neutral":n>0?"positive":n<0?"negative":"neutral";
const fileSafe=(v:string)=>v.replace(/[^a-zA-Z0-9_-]/g,"_");
const csvText=(s:string)=>{
  const escaped=/^[=+\-@\t\r]/.test(s)?"'"+s:s;
  return '"'+escaped.replaceAll('"','""')+'"';
};
function exportJournalCsv(records:StrongTrade[],strategyId:string){
  const header=["strategy_id","source_event_id","symbol","status","opened_at_utc","closed_at_utc",
    "entry_price","exit_price","net_pnl_usd","close_reason","decision","decision_reason"];
  const rows=records.map(t=>[
    csvText(t.strategyId),csvText(t.sourceEventId),csvText(t.symbol),csvText(t.status),
    csvText(new Date(t.openedAtMs).toISOString()),
    csvText(t.closedAtMs!=null?new Date(t.closedAtMs).toISOString():""),
    t.entryPrice==null?"":String(t.entryPrice),
    t.exitPrice==null?"":String(t.exitPrice),
    t.netPnl==null?"":String(t.netPnl),
    csvText(t.closeReason??""),csvText(t.decision??""),csvText(t.decisionReason??"")
  ].join(","));
  const content="\uFEFF"+[header.join(","),...rows].join("\r\n");
  const url=URL.createObjectURL(new Blob([content],{type:"text/csv;charset=utf-8"}));
  const a=document.createElement("a");
  a.href=url;a.download=\`bababot-paper-journal-\${fileSafe(strategyId)}-\${wibDateKey(Date.now())}.csv\`;
  document.body.appendChild(a);a.click();a.remove();
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function Metric({name,value,caption,polarity}:{name:string;value:string;caption?:string;polarity?:number|null}){
  return <div className="j-metric"><span>{name}</span>
    <strong className={polarity===undefined?"":pnlClass(polarity)}>{value}</strong>
    {caption&&<small>{caption}</small>}
  </div>;
}

function JournalCurve({points}: {points:JournalEquityPoint[]}) {
  if(points.length<2)return <div className="j-empty">No CLOSED PAPER records in this period.</div>;
  const W=740,H=238,pl=48,pr=18,pt=19,pb=28;
  const highs=points.map(p=>p.equity);
  const hi=Math.max(0,...highs),lo=Math.min(0,...highs);
  const range=Math.max(hi-lo,0.1);
  const x=(i:number)=>pl+(W-pl-pr)*i/(points.length-1);
  const y=(v:number)=>pt+(H-pt-pb)*(hi-v)/range;
  const path=points.map((p,i)=>\`\${i?"L":"M"}\${x(i).toFixed(2)},\${y(p.equity).toFixed(2)}\`).join(" ");
  const last=points.at(-1)!;
  const axis=[hi,(hi+lo)/2,lo];
  return <div className="j-equity">
    <svg role="img" aria-label="Cumulative net realized PAPER PnL in USD by chronological close time" viewBox={\`0 0 \${W} \${H}\`} preserveAspectRatio="none">
      <defs><linearGradient id="j_equity_area" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#35cdb4" stopOpacity=".25"/>
        <stop offset="1" stopColor="#35cdb4" stopOpacity="0"/>
      </linearGradient></defs>
      {axis.map((v,i)=><g key={i}>
        <line x1={pl} y1={y(v)} x2={W-pr} y2={y(v)} stroke="#304150" strokeDasharray="4 6"/>
        <text x={pl-7} y={y(v)+4} fontSize="10" fill="#8a9fac" textAnchor="end">{v.toFixed(1)}</text>
      </g>)}
      <line x1={pl} y1={y(0)} x2={W-pr} y2={y(0)} stroke="#778ea1" opacity=".45" strokeDasharray="2 4"/>
      <path d={path+\` L\${x(points.length-1)},\${H-pb} L\${x(0)},\${H-pb} Z\`} fill="url(#j_equity_area)"/>
      <path d={path} fill="none" stroke="#39cfb9" strokeWidth="2.8" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx={x(points.length-1)} cy={y(last.equity)} r="4.7" fill="#39cfb9" stroke="#11212a" strokeWidth="2"/>
      <text x={pl} y={H-6} fill="#7e93a3" fontSize="10">CLOSED 1</text>
      <text x={W-pr} y={H-6} fill="#7e93a3" fontSize="10" textAnchor="end">CLOSED {points.length-1}</text>
    </svg>
    <div className="j-curve-foot"><span>Chronological close-time · zero initial realized PnL</span>
      <strong className={pnlClass(last.equity)}>End {fMoney(last.equity)}</strong></div>
  </div>;
}
function JournalDrawdown({points}: {points:JournalEquityPoint[]}) {
  if(points.length<2)return <div className="j-empty">No drawdown until a PAPER trade closes.</div>;
  const W=740,H=112,pl=48,pr=18,pt=9,pb=12;
  const max=Math.max(...points.map(p=>p.drawdown),0.001);
  const x=(i:number)=>pl+(W-pl-pr)*i/(points.length-1);
  const y=(v:number)=>pt+(H-pt-pb)*v/max;
  const path=points.map((p,i)=>\`\${i?"L":"M"}\${x(i).toFixed(2)},\${y(p.drawdown).toFixed(2)}\`).join(" ");
  return <div className="j-drawdown"><svg role="img" aria-label="Drawdown in USD from prior cumulative realized PnL peak; not account balance drawdown" viewBox={\`0 0 \${W} \${H}\`} preserveAspectRatio="none">
    <line x1={pl} y1={pt} x2={W-pr} y2={pt} stroke="#304150" strokeDasharray="3 5"/>
    <line x1={pl} y1={H-pb} x2={W-pr} y2={H-pb} stroke="#304150" strokeDasharray="3 5"/>
    <text x={pl-7} y={pt+4} fill="#8295a5" textAnchor="end" fontSize="10">$0</text>
    <text x={pl-7} y={H-pb+4} fill="#8295a5" textAnchor="end" fontSize="10">{max.toFixed(1)}</text>
    <path d={path} fill="none" stroke="#eb7c87" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg></div>;
}

function monthOffset(month:string,delta:number){
  const [y,m]=month.split("-").map(Number);
  const date=new Date(Date.UTC(y,m-1+delta,1));
  return \`\${date.getUTCFullYear()}-\${String(date.getUTCMonth()+1).padStart(2,"0")}\`;
}
function dayEntries(month:string){
  const [y,m]=month.split("-").map(Number);
  if(!y||!m||m<1||m>12)return [];
  const first=new Date(Date.UTC(y,m-1,1)).getUTCDay();
  const days=new Date(Date.UTC(y,m,0)).getUTCDate();
  return [...Array.from({length:first},()=>null),
    ...Array.from({length:days},(_,i)=>\`\${month}-\${String(i+1).padStart(2,"0")}\`)] as (string|null)[];
}
function PnlCalendar({month,days,chosenDay,onChangeMonth,onSelectDay}:{
  month:string;days:DateBucket[];chosenDay:string|null;
  onChangeMonth:(delta:number)=>void;onSelectDay:(s:string|null)=>void;
}){
  const dates=dayEntries(month);
  const map=new Map(days.map(x=>[x.date,x]));
  const scoped=days.filter(d=>d.date.startsWith(month));
  const pnl=scoped.reduce((a,d)=>a+d.netPnl,0);
  const max=Math.max(...scoped.map(d=>Math.abs(d.netPnl)),0.001);
  return <section className="panel j-calendar-panel">
    <div className="panel-head j-head">
      <div><div className="section-eyebrow">REALIZED CLOSE DATE · WIB</div><h2>Trading Calendar</h2>
        <p>Click a day to filter the ledger below.</p></div>
      <div className="j-month-nav">
        <button type="button" aria-label="Previous month" onClick={()=>onChangeMonth(-1)}>‹</button>
        <strong>{new Date(month+"-01T00:00:00Z").toLocaleDateString("id-ID",{month:"short",year:"numeric",timeZone:"UTC"})}</strong>
        <button type="button" aria-label="Next month" onClick={()=>onChangeMonth(1)}>›</button>
      </div>
    </div>
    <div className="j-calendar-grid">
      {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((day,i)=><div key={i} className="j-day-name">{day}</div>)}
      {dates.map((date,i)=>{
        if(!date)return <div key={\`empty-\${i}\`} className="j-day blank"/>;
        const s=map.get(date);
        const intensity=s?0.08+Math.abs(s.netPnl)/max*0.28:0;
        const rgb=s?.netPnl===0?"102,134,164":(s?.netPnl??0)>0?"39,179,145":"223,107,122";
        return <button key={date} type="button" onClick={()=>onSelectDay(chosenDay===date?null:date)}
          className={\`j-day \${s?"has-trade":""} \${chosenDay===date?"chosen":""}\`}
          aria-pressed={chosenDay===date} title={\`\${date} · \${s?.trades??0} close(s) · \${fMoney(s?.netPnl??0)}\`}
          style={{backgroundColor:s?\`rgba(\${rgb},\${intensity})\`:undefined}}>
          <span className="j-day-number">{date.slice(-2)}</span>
          {s&&<><strong className={pnlClass(s.netPnl)}>{fMoney(s.netPnl)}</strong>
            <small>{s.trades} closed</small></>}
        </button>;
      })}
    </div>
    <div className="j-calendar-foot">
      <span>{scoped.length} active close-days</span>
      <span>Month net: <strong className={pnlClass(pnl)}>{fMoney(pnl)}</strong></span>
    </div>
  </section>;
}
function SmallStats({title,entries,onSelectSymbol}:{
  title:"symbols"|"reasons";entries:{key:string;count:number;value:number;detail:string}[];
  onSelectSymbol?:(symbol:string)=>void;
}){
  const max=Math.max(...entries.map(e=>Math.abs(e.value)),0.001);
  return <div className="j-group">
    {entries.length===0?<div className="j-empty">No CLOSED PAPER records.</div>:
    entries.slice(0,8).map(item=><div className="j-group-row" key={item.key}>
      <div className="j-group-main">
        <div className="j-group-name">{onSelectSymbol?
          <button type="button" onClick={()=>onSelectSymbol(item.key)}>{item.key}</button>
          : <strong title={item.key}>{item.key}</strong>}
          <span>{item.count} · {item.detail}</span></div>
        <strong className={pnlClass(item.value)}>{fMoney(item.value)}</strong>
      </div>
      <div className="j-bar"><span style={{width:\`\${Math.min(100,Math.abs(item.value)/max*100)}%\`,
        background:item.value>=0?"#329c86":"#bd6674"}}/></div>
    </div>)}
    {entries.length>8&&<span className="j-more">{entries.length-8} additional group(s) not shown</span>}
  </div>;
}
function JournalInspector({trade,onOpenChart}:{trade:StrongTrade|null;onOpenChart:(t:StrongTrade)=>void}){
  if(!trade)return <div className="j-inspector-empty"><strong>⌕ Select a trade</strong><p>Review source events and recorded PAPER fills. Open Vela for historical market context.</p></div>;
  return <div className="j-inspector">
    <div className="section-eyebrow">SOURCE LEDGER · READ ONLY</div>
    <h3>{trade.symbol} <span className="mini-tag">{trade.strategyId}</span></h3>
    <div className="j-inspector-status"><span className="status-chip">{classifyTrade(trade)}</span></div>
    <dl>
      <div><dt>Entry (WIB)</dt><dd>{fDate(trade.openedAtMs)}</dd></div>
      <div><dt>Close (WIB)</dt><dd>{fDate(trade.closedAtMs)}</dd></div>
      <div><dt>Entry / exit</dt><dd className="mono">{trade.entryPrice??"—"} / {trade.exitPrice??"—"}</dd></div>
      <div><dt>Net realized USD</dt><dd className={\`mono \${pnlClass(trade.netPnl)}\`}>{fMoney(trade.netPnl)}</dd></div>
      <div><dt>Close reason</dt><dd>{trade.closeReason||"Not recorded"}</dd></div>
    </dl>
    <div className="j-source"><small>source_event_id</small><code>{trade.sourceEventId}</code></div>
    <button type="button" className="j-primary" onClick={()=>onOpenChart(trade)}>
      Open Futures Chart & Replay ↗
    </button>
  </div>;
}

export default function TradeJournal({snapshot,onOpenChart}:{
  snapshot:StrongSnapshot;onOpenChart:(t:StrongTrade)=>void;
}){
  const {strategies,trades}=snapshot;
  const [strategyId,setStrategyId]=useState("M03");
  const [period,setPeriod]=useState("all");
  const [calendarOverride,setCalendarOverride]=useState<string|null>(null);
  const [selectedDay,setSelectedDay]=useState<string|null>(null);
  const [outcome,setOutcome]=useState<OutcomeFilter>("ALL");
  const [query,setQuery]=useState("");
  const [selectedId,setSelectedId]=useState<string|null>(null);
  const [left,setLeft]=useState("M03");
  const [right,setRight]=useState("M04");
  const selectedStrategy=strategies.find(s=>s.id===strategyId)??strategies[0];
  const strategy=selectedStrategy?.id??"M03";
  const own=useMemo(()=>trades.filter(t=>t.strategyId===strategy),[trades,strategy]);
  const months=useMemo(()=>availableCloseMonths(own),[own]);
  const calendarMonth=calendarOverride??(period!=="all"?period:months[0]??wibDateKey(Date.now()).slice(0,7));
  const periodTrades=useMemo(()=>filterStrategyMonth(trades,strategy,period),[trades,strategy,period]);
  const journal=useMemo(()=>journalOverview(periodTrades),[periodTrades]);
  const compared=useMemo(()=>matchedOverview(trades,left,right),[trades,left,right]);
  const tableRows=useMemo(()=>{
    const lower=query.trim().toLowerCase();
    return periodTrades.filter(t=>{
      if(selectedDay && (!isRealized(t)||wibDateKey(t.closedAtMs!)!==selectedDay))return false;
      if(outcome!=="ALL"&&classifyTrade(t)!==outcome)return false;
      return !lower||t.symbol.toLowerCase().includes(lower)||
        t.sourceEventId.toLowerCase().includes(lower)||
        (t.closeReason??"").toLowerCase().includes(lower);
    }).sort((a,b)=> (b.closedAtMs??b.openedAtMs)-(a.closedAtMs??a.openedAtMs) || a.id.localeCompare(b.id));
  },[periodTrades,selectedDay,outcome,query]);
  const focus=tableRows.find(t=>t.id===selectedId)??null;
  const m=journal.metrics;
  const headMonth=()=>setPeriod("all");
  function updateStrategy(s:string){setStrategyId(s);setPeriod("all");setCalendarOverride(null);setSelectedDay(null);setSelectedId(null);setOutcome("ALL");setQuery("");}
  function updatePeriod(v:string){setPeriod(v);setCalendarOverride(v==="all"?null:v);setSelectedDay(null);setSelectedId(null);}
  function changeMonth(by:number){
    const next=monthOffset(calendarMonth,by);
    setCalendarOverride(next);
    if(period!=="all")setPeriod(next);
    setSelectedDay(null);
  }
  const selectedMonth=period!=="all";
  const symbols=journal.symbols.map(x=>({key:x.symbol,count:x.trades,value:x.netPnl,detail:\`\${x.wins}W / \${x.losses}L\`}));
  const reasons=journal.reasons.map(x=>({key:x.reason,count:x.trades,value:x.netPnl,detail:\`\${x.wins}W / \${x.losses}L\`}));
  return <div className="j-root">
    <section className="j-control-bar">
      <div><label htmlFor="j-strategy">INDEPENDENT STRATEGY</label>
        <select id="j-strategy" value={strategy} onChange={e=>updateStrategy(e.target.value)}>
          {strategies.map(s=><option key={s.id} value={s.id}>{s.label} · {s.activity}</option>)}
        </select></div>
      <div><label htmlFor="j-period">PERFORMANCE PERIOD</label>
        <select id="j-period" value={period} onChange={e=>updatePeriod(e.target.value)}>
          <option value="all">All recorded history</option>
          {months.map(month=><option value={month} key={month}>{month}</option>)}
        </select></div>
      <div className="j-source-note"><span className="j-dot"/> VPS2 PAPER · {selectedStrategy?.moduleLabel}</div>
    </section>

    <div className="j-warning">
      <strong>Independent ledger scope:</strong> Semua statistik di halaman ini hanya untuk <strong>{strategy}</strong>
      {selectedMonth?<> selama <strong>{period}</strong></>:" untuk seluruh histori yang tercatat"}.
      Jangan menjumlahkan PnL antarcabang karena sumber sinyal dapat sama. WR dan PnL bersifat deskriptif.
    </div>
    <div className="j-kpis">
      <Metric name="Net realized PnL" value={fMoney(m.netPnl)} caption="USD · ledger CLOSED only" polarity={m.netPnl}/>
      <Metric name="Win rate" value={fPercent(m.winRate)} caption={\`\${m.wins}W / \${m.losses}L / \${m.breakevens} BE\`}/>
      <Metric name="CLOSED trades" value={String(m.closed)} caption={\`\${m.open} OPEN · \${m.unresolved} unresolved\`}/>
      <Metric name="Profit factor" value={fNumber(m.profitFactor)} caption="gross winning net ÷ losing net"/>
      <Metric name="Expectancy / trade" value={fMoney(m.expectancy)} caption="Average realized net USD" polarity={m.expectancy}/>
      <Metric name="Max realized drawdown" value={m.closed?"$"+m.maxDrawdownUsd.toFixed(2):"—"} caption="USD peak-to-trough; not equity %" />
    </div>
    {m.sampleWarning&&<p className="j-sample-alert">⚠ {m.sampleWarning}</p>}

    <div className="j-insights-grid">
      <section className="panel j-performance-panel">
        <div className="panel-head j-head"><div>
          <div className="section-eyebrow">REALIZED PAPER PERFORMANCE</div>
          <h2>Cumulative Net PnL</h2><p>Chronological close time; no unrealized marks</p>
        </div><span className="mini-tag">{strategy} ONLY</span></div>
        <JournalCurve points={journal.equity}/>
        <div className="j-divider"/>
        <div className="panel-head j-head"><div>
          <div className="section-eyebrow">RISK PATH</div><h2>Realized drawdown</h2>
          <p>Relative to highest cumulative net PnL, baseline $0</p></div>
        </div>
        <JournalDrawdown points={journal.equity}/>
        <div className="j-mini-stats">
          <div><span>Avg win</span><strong className="positive">{fMoney(m.avgWin)}</strong></div>
          <div><span>Avg loss magnitude</span><strong className="negative">{m.avgLossAbs==null?"—":"$"+m.avgLossAbs.toFixed(2)}</strong></div>
          <div><span>Payoff ratio</span><strong>{fNumber(m.payoffRatio)}</strong></div>
          <div><span>Median holding</span><strong>{duration(m.medianDurationMs)}</strong></div>
          <div><span>Max W streak</span><strong>{m.maxWinStreak}</strong></div>
          <div><span>Max L streak</span><strong>{m.maxLossStreak}</strong></div>
        </div>
      </section>
      <PnlCalendar month={calendarMonth} days={journal.days} chosenDay={selectedDay}
        onChangeMonth={changeMonth} onSelectDay={setSelectedDay}/>
    </div>

    <div className="j-insights-grid j-bottom-grid">
      <section className="panel j-breakdown">
        <div className="panel-head j-head"><div><div className="section-eyebrow">PER SYMBOL</div><h2>Symbol Contribution</h2>
          <p>Net PnL and actual closed sample sizes</p></div></div>
        <SmallStats title="symbols" entries={symbols} onSelectSymbol={symbol=>{setQuery(symbol);setSelectedDay(null);}}/>
      </section>
      <section className="panel j-breakdown">
        <div className="panel-head j-head"><div><div className="section-eyebrow">EXIT LOG</div><h2>Recorded Close Reasons</h2>
          <p>Raw VPS2 close reasons; not inferred loss causes</p></div></div>
        <SmallStats title="reasons" entries={reasons}/>
      </section>
    </div>

    <section className="panel j-compare-panel">
      <div className="panel-head j-head"><div>
        <div className="section-eyebrow">APPLES-TO-APPLES RESEARCH</div>
        <h2>Matched Source-Event Comparison</h2>
        <p>Compares only common CLOSED events; never sums independent strategies into a portfolio.</p>
      </div><span className="mini-tag">SAME SOURCE ID</span></div>
      <div className="j-pair-controls">
        <label htmlFor="j-pair-left">LEFT BRANCH</label>
        <select id="j-pair-left" value={left} onChange={e=>{setLeft(e.target.value);if(e.target.value===right)setRight(strategies.find(s=>s.id!==e.target.value)?.id??right);}}>
          {strategies.map(s=><option value={s.id} key={s.id}>{s.label}</option>)}
        </select><span className="j-pair-vs">vs.</span>
        <label htmlFor="j-pair-right">RIGHT BRANCH</label>
        <select id="j-pair-right" value={right} onChange={e=>{setRight(e.target.value);if(e.target.value===left)setLeft(strategies.find(s=>s.id!==e.target.value)?.id??left);}}>
          {strategies.map(s=><option value={s.id} key={s.id}>{s.label}</option>)}
        </select>
      </div>
      <div className="j-pair-stats">
        <div><small>Common CLOSED events</small><strong>{compared.matchedCount}</strong></div>
        <div><small>{left} matched net USD</small><strong className={pnlClass(compared.leftNet)}>{fMoney(compared.leftNet)}</strong></div>
        <div><small>{right} matched net USD</small><strong className={pnlClass(compared.rightNet)}>{fMoney(compared.rightNet)}</strong></div>
        <div><small>Only {left} / only {right}</small><strong>{compared.missingRight} / {compared.missingLeft}</strong></div>
      </div>
      {compared.matchedCount<20&&<p className="j-sample-inline">Matched sample is only {compared.matchedCount}. This is not evidence of statistical superiority; exclusion, selectivity and event overlap must be interpreted separately.</p>}
      {compared.events.length?<div className="table-wrap"><table className="data-table j-pair-table">
        <thead><tr><th>Source event / symbol</th><th>{left} outcome</th><th>{right} outcome</th><th className="num">Δ net USD (L−R)</th><th>Replay</th></tr></thead>
        <tbody>{compared.events.slice(0,35).map(e=><tr key={e.sourceEventId}>
          <td><strong>{e.symbol}</strong><small className="table-subtitle" title={e.sourceEventId}>{e.sourceEventId}</small></td>
          <td className={pnlClass(e.leftNet)}>{fMoney(e.leftNet)}</td><td className={pnlClass(e.rightNet)}>{fMoney(e.rightNet)}</td>
          <td className={\`num mono \${pnlClass(e.deltaLeftMinusRight)}\`}>{fMoney(e.deltaLeftMinusRight)}</td>
          <td><button type="button" className="j-table-action" onClick={()=>onOpenChart(e.left)}>Open chart ↗</button></td>
        </tr>)}</tbody>
      </table></div>:<div className="j-empty">No common CLOSED source events for this pair. No comparison is inferred.</div>}
    </section>

    <section className="panel j-ledger-panel">
      <div className="panel-head j-head"><div><div className="section-eyebrow">AUDITABLE RECORDS</div>
        <h2>PAPER Trade Explorer</h2><p>Same strategy and period as the KPI summary. Table filters do not change summary metrics.</p>
      </div><button type="button" className="j-export" disabled={!tableRows.length}
        onClick={()=>exportJournalCsv(tableRows,strategy)}>↓ Export filtered CSV</button></div>
      <div className="j-table-filters">
        <div><label htmlFor="j-search">SYMBOL / SOURCE ID / CLOSE REASON</label>
          <input id="j-search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search ledger records..."/></div>
        <div><label htmlFor="j-outcome">TRADE OUTCOME</label>
          <select id="j-outcome" value={outcome} onChange={e=>setOutcome(e.target.value as OutcomeFilter)}>
            {OUTCOMES.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}
          </select></div>
        <div className="j-filter-status"><span>{tableRows.length} matching records</span>
          {(selectedDay||outcome!=="ALL"||query||period!=="all")&&<button type="button" onClick={()=>{
            headMonth();setCalendarOverride(null);setSelectedDay(null);setQuery("");setOutcome("ALL");setSelectedId(null);
          }}>Clear filters</button>}</div>
      </div>
      {selectedDay&&<div className="j-day-active">Close date: <strong>{selectedDay} WIB</strong>
        <button type="button" onClick={()=>setSelectedDay(null)}>Remove day filter ×</button></div>}
      <div className="j-explorer-grid">
        <div className="table-wrap">
          {tableRows.length?<table className="data-table j-trades-table"><thead><tr>
            <th>Close (WIB)</th><th>Symbol</th><th>Outcome</th><th className="num">Net USD</th><th>Reason</th>
          </tr></thead><tbody>{tableRows.slice(0,200).map(t=><tr key={t.id} onClick={()=>setSelectedId(t.id)}
            className={\`clickable \${focus?.id===t.id?"selected":""}\`} tabIndex={0}
            onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();setSelectedId(t.id);}}}>
            <td className="date-cell">{fDate(t.closedAtMs??t.openedAtMs)}</td>
            <td><strong>{t.symbol}</strong></td><td><span className={\`j-outcome \${classifyTrade(t).toLowerCase()}\`}>{classifyTrade(t)}</span></td>
            <td className={\`num mono \${pnlClass(t.netPnl)}\`}>{fMoney(t.netPnl)}</td>
            <td className="reason-cell">{t.closeReason??"—"}</td>
          </tr>)}</tbody></table>:<div className="j-empty">No ledger record matches the selected filters.</div>}
          {tableRows.length>200&&<p className="j-more">Showing newest 200 of {tableRows.length} records. CSV exports all matching rows.</p>}
        </div>
        <aside className="j-inspector-panel"><JournalInspector trade={focus} onOpenChart={onOpenChart}/></aside>
      </div>
    </section>
    <footer className="j-methodology">Methodology: USD figures are authoritative <strong>net realized PnL</strong> from VPS2 PAPER ledgers, sorted by close timestamp. Daily/monthly buckets use Asia/Jakarta.
      Profit factor uses positive/negative net-PnL sums; drawdown uses a $0 realized-PnL baseline, not account equity or percentage of capital.
      No leverage-adjusted returns, gross fees, MAE/MFE, or R-multiples are inferred without corresponding source fields.
      Matching is strictly by source_event_id. Source snapshot: {fDate(Date.parse(snapshot.generatedAt))}.</footer>
  </div>;
}
