"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import VelaPaperChart from "./vela-paper-chart";
import TradeJournal from "./trade-journal";
import type { StrongApiResponse, StrongStrategy, StrongTrade } from "@/lib/strong-types";

type View = "overview" | "strategies" | "compare" | "trades" | "journal" | "chart" | "system";

const NAV: { id: View; label: string; description: string; symbol: string }[] = [
  { id: "overview", label: "Overview", description: "Strategy health", symbol: "▦" },
  { id: "strategies", label: "Strategies", description: "Independent PAPER", symbol: "▤" },
  { id: "compare", label: "Matched Compare", description: "Same source event", symbol: "⇄" },
  { id: "trades", label: "Trade Explorer", description: "Entry & exit detail", symbol: "⌕" },
  { id: "journal", label: "Trade Journal", description: "PnL & matched analytics", symbol: "▥" },
  { id: "chart", label: "Vela Chart & Replay", description: "Futures PAPER fills", symbol: "◈" },
  { id: "system", label: "Data & System", description: "Source health", symbol: "◈" }
];

const BLANK: StrongApiResponse = { mode: "unconfigured", snapshot: null, warning: null };
const REFRESH_MS = 60000; // read-only refresh; does not trade or mutate PAPER
const fmtMoney = (n: number | null | undefined, digits = 2) =>
  n == null ? "—" : `${n > 0 ? "+" : n < 0 ? "−" : ""}$${Math.abs(n).toFixed(digits)}`;
const fmtNumber = (n: number | null | undefined) => n == null ? "—" : n.toLocaleString("en-US");
const fmtPct = (n: number | null | undefined) => n == null ? "—" : `${n.toFixed(2)}%`;
const fmtTime = (ms: number | null | undefined) =>
  ms == null ? "—" : new Date(ms).toLocaleString("id-ID", {
    timeZone: "Asia/Jakarta", day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  }) + " WIB";
const pnlClass = (n: number | null | undefined) => n == null ? "neutral" : n > 0 ? "positive" : n < 0 ? "negative" : "neutral";
const fmtPrice = (v: number | null) =>
  v == null ? "—" : v.toLocaleString("en-US", { maximumFractionDigits: 10, minimumFractionDigits: 2 });
const shortSource = (s: string) => s.length > 39 ? s.slice(0, 20) + "…" + s.slice(-12) : s;

function EquityLine({ trades }: { trades: StrongTrade[] }) {
  const series = useMemo(() => {
    const ordered = trades.filter(t => t.status === "CLOSED" && t.closedAtMs != null && t.netPnl != null)
      .sort((a, b) => (a.closedAtMs ?? 0) - (b.closedAtMs ?? 0));
    let running = 0;
    return [0, ...ordered.map(t => { running += t.netPnl ?? 0; return running; })];
  }, [trades]);
  if (series.length < 2) return <div className="empty-chart">Belum ada cukup transaksi CLOSED untuk menggambar equity.</div>;
  const width = 680, height = 186, pad = 16;
  const hi = Math.max(...series, 0), lo = Math.min(...series, 0), span = Math.max(hi - lo, 1);
  const x = (i: number) => pad + i / (series.length - 1) * (width - 2 * pad);
  const y = (v: number) => height - pad - (v - lo) / span * (height - 2 * pad);
  const line = series.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(2)} ${y(v).toFixed(2)}`).join(" ");
  const zero = y(0);
  return (
    <div className="equity-chart" role="img" aria-label="Kurva kumulatif PnL dari transaksi CLOSED, urutan waktu closing">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="equityFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#27c6b2" stopOpacity=".22"/>
            <stop offset="1" stopColor="#27c6b2" stopOpacity="0"/>
          </linearGradient>
        </defs>
        {Array.from({ length: 5 }, (_, i) => <line key={i} x1={pad} x2={width-pad} y1={pad + i*(height-2*pad)/4} y2={pad + i*(height-2*pad)/4} stroke="#283546" strokeDasharray="4 7"/>)}
        <line x1={pad} x2={width-pad} y1={zero} y2={zero} stroke="#a3aec1" opacity=".35" strokeDasharray="5 4"/>
        <path d={line + ` L${x(series.length - 1)} ${height - pad} L${x(0)} ${height - pad} Z`} fill="url(#equityFill)"/>
        <path d={line} fill="none" stroke="#32c7b4" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx={x(series.length - 1)} cy={y(series.at(-1) ?? 0)} r="4" fill="#32c7b4" stroke="#101820" strokeWidth="2"/>
      </svg>
      <div className="chart-axis"><span>{series.length-1} CLOSED</span><span>Net {fmtMoney(series.at(-1))}</span></div>
    </div>
  );
}

function StatusChip({ status }: { status: string }) {
  const cls = status === "ACTIVE" || status === "CLOSED" ? "success" :
    status === "PAUSED" || status === "DATA_GAP" ? "warning" :
    status === "OPEN" ? "info" : "muted";
  return <span className={`status-chip ${cls}`}>{status === "CENSORED_30MIN" ? "CENSORED" : status}</span>;
}

function StrategyTable({ strategies, selected, onSelect }: {
  strategies: StrongStrategy[]; selected: string; onSelect: (s: string) => void;
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead><tr><th>Strategy</th><th>Enrollment</th><th className="num">Closed</th><th className="num">W / L</th><th className="num">WR</th><th className="num">Net PnL</th></tr></thead>
        <tbody>
          {strategies.map(s => <tr key={s.id} onClick={() => onSelect(s.id)}
            className={`clickable ${selected === s.id ? "selected" : ""}`} tabIndex={0}
            onKeyDown={e => { if(e.key==="Enter" || e.key===" ") { e.preventDefault(); onSelect(s.id); } }}>
            <td><strong className="strategy-code">{s.label}</strong><small className="table-subtitle">{s.moduleLabel}</small></td>
            <td><StatusChip status={s.activity}/></td>
            <td className="num">{s.closed}</td>
            <td className="num">{s.wins} / {s.losses}</td>
            <td className="num">{fmtPct(s.winRate)}</td>
            <td className={`num mono ${pnlClass(s.netPnl)}`}>{fmtMoney(s.netPnl)}</td>
          </tr>)}
        </tbody>
      </table>
    </div>
  );
}

function TradeTable({ trades, onSelect, selectedId }: {
  trades: StrongTrade[]; onSelect: (t: StrongTrade) => void; selectedId?: string;
}) {
  if (!trades.length) return <div className="empty-chart">Tidak ada transaksi yang cocok dengan filter.</div>;
  return <div className="table-wrap">
    <table className="data-table">
      <thead><tr><th>Opened (WIB)</th><th>Symbol</th><th>Strategy</th><th>Status</th><th className="num">Net PnL</th><th>Close reason</th></tr></thead>
      <tbody>{trades.map(t => <tr key={t.id} className={`clickable ${selectedId === t.id ? "selected" : ""}`}
        tabIndex={0} onClick={() => onSelect(t)}
        onKeyDown={e => { if(e.key==="Enter" || e.key===" ") { e.preventDefault(); onSelect(t); } }}>
        <td className="date-cell">{fmtTime(t.openedAtMs)}</td>
        <td><strong>{t.symbol}</strong></td>
        <td><span className="mini-tag">{t.strategyId}</span></td>
        <td><StatusChip status={t.status}/></td>
        <td className={`num mono ${pnlClass(t.netPnl)}`}>{fmtMoney(t.netPnl)}</td>
        <td className="reason-cell">{t.closeReason ?? "—"}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

function TradeDetails({ trade, matches, onOpenChart }: { trade: StrongTrade; matches: StrongTrade[]; onOpenChart: () => void }) {
  return <div className="details-panel">
    <div className="details-heading">
      <div><div className="section-eyebrow">TRADE INSPECTOR</div><h3>{trade.symbol} <span className="mini-tag">{trade.strategyId}</span></h3></div>
      <StatusChip status={trade.status}/>
    </div>
    <div className="detail-grid">
      <div><small>Entry (WIB)</small><strong>{fmtTime(trade.openedAtMs)}</strong></div>
      <div><small>Close (WIB)</small><strong>{fmtTime(trade.closedAtMs)}</strong></div>
      <div><small>Entry price</small><strong className="mono">{fmtPrice(trade.entryPrice)}</strong></div>
      <div><small>Exit price</small><strong className="mono">{fmtPrice(trade.exitPrice)}</strong></div>
      <div><small>Net realized</small><strong className={`mono ${pnlClass(trade.netPnl)}`}>{fmtMoney(trade.netPnl)}</strong></div>
      <div><small>Close reason</small><strong>{trade.closeReason ?? "—"}</strong></div>
    </div>
    <div className="source-id"><small>Original source_event_id</small><code>{trade.sourceEventId}</code></div>
    {trade.decision && <p className="details-note">Pre-entry decision: <strong>{trade.decision}</strong> {trade.decisionReason ? "(" + trade.decisionReason + ")" : ""}</p>}
    <div className="details-divider"/>
    <h4>Same source event <span className="muted-text">({matches.length} branch records)</span></h4>
    <div className="match-list">
      {matches.map(m => <div key={m.id} className="match-row">
        <span>{m.strategyId}</span><StatusChip status={m.status}/><span className={`mono ${pnlClass(m.netPnl)}`}>{fmtMoney(m.netPnl)}</span>
      </div>)}
    </div>
    <button type="button" className="text-action" onClick={onOpenChart}>Open Binance Futures Vela Chart & Replay →</button>
    <p className="microcopy">Matched comparison menggunakan source event yang identik, bukan sekadar symbol. Branch yang tidak memiliki record tidak dianggap WIN, LOSS, atau SKIP.</p>
  </div>;
}

export default function StrongWorkspace() {
  const [payload, setPayload] = useState<StrongApiResponse>(BLANK);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>("overview");
  const [strategyId, setStrategyId] = useState("M03");
  const [search, setSearch] = useState("");
  const [tradeId, setTradeId] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/strong", { cache: "no-store", signal });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const data = (await response.json()) as StrongApiResponse;
      if (!signal?.aborted) setPayload(data);
    } catch (e) {
      if (!signal?.aborted) setError(e instanceof Error ? e.message : "Failed to load API");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const ctrl = new AbortController();
    void reload(ctrl.signal);
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void reload(); }, REFRESH_MS);
    return () => { ctrl.abort(); window.clearInterval(timer); };
  }, [reload]);

  const snapshot = payload.snapshot;
  const strategies = snapshot?.strategies ?? [];
  const trades = snapshot?.trades ?? [];
  const selected = strategies.find(s => s.id === strategyId) ?? strategies.find(s => s.id === "M03") ?? strategies[0];
  const currentId = selected?.id ?? strategyId;
  const ownTrades = useMemo(() => trades.filter(t => t.strategyId === currentId), [trades, currentId]);
  const selectedTrade = trades.find(t => t.id === tradeId) ?? null;
  const chartTrade = selectedTrade ?? trades.find(t => t.strategyId === "M03" && t.status === "CLOSED") ?? trades[0] ?? null;
  const matchingTrades = useMemo(() => selectedTrade
    ? trades.filter(t => t.sourceEventId === selectedTrade.sourceEventId).sort((a,b) => a.strategyId.localeCompare(b.strategyId))
    : [], [trades, selectedTrade]);
  const chartMatched = useMemo(() => chartTrade
    ? trades.filter(t => t.sourceEventId === chartTrade.sourceEventId).sort((a,b) => a.strategyId.localeCompare(b.strategyId))
    : [], [trades, chartTrade]);
  const grouped = useMemo(() => {
    const groups = new Map<string, StrongTrade[]>();
    for (const t of trades) {
      const list = groups.get(t.sourceEventId) ?? [];
      list.push(t);
      groups.set(t.sourceEventId, list);
    }
    return [...groups.entries()].filter(([,t]) => t.length >= 2)
      .sort((a,b) => Math.max(...b[1].map(t => t.openedAtMs)) - Math.max(...a[1].map(t => t.openedAtMs)));
  }, [trades]);
  const chosenGroup = grouped.find(([id]) => id === sourceFilter) ?? grouped[0] ?? null;
  const explorerTrades = useMemo(() => trades.filter(t => {
    const q = search.trim().toLowerCase();
    return (!q || t.symbol.toLowerCase().includes(q) || t.strategyId.toLowerCase().includes(q) ||
      t.closeReason?.toLowerCase().includes(q) || t.sourceEventId.toLowerCase().includes(q));
  }).sort((a,b) => b.openedAtMs-a.openedAtMs).slice(0,250), [trades, search]);
  const latestClosed = useMemo(() => ownTrades.filter(t => t.status === "CLOSED")
    .sort((a,b) => (b.closedAtMs ?? 0) - (a.closedAtMs ?? 0)).slice(0,7), [ownTrades]);

  const selectTrade = (trade: StrongTrade) => { setTradeId(trade.id); setView("trades"); };
  const chartOpen = (trade: StrongTrade) => { setTradeId(trade.id); setView("chart"); };
  const configured = snapshot !== null;

  return <div className="app-shell">
    <aside className="sidebar">
      <a href="/" className="brand" aria-label="BabaBot home">
        <span className="brand-logo">B<span>✦</span></span>
        <span className="brand-copy"><strong>BABABOT</strong><small>RESEARCH PLATFORM</small></span>
      </a>
      <div className="sidebar-caption">WORKSPACES</div>
      <div className="workspace-current"><span className="workspace-mark">↗</span><div><strong>STRONG LONG</strong><small>Independent PAPER</small></div><span className="workspace-chevron">⌄</span></div>
      <div className="sidebar-scroll" role="region" aria-label="Daftar menu STRONG LONG" tabIndex={0}>
        <div className="sidebar-caption nav-caption">STRONG LONG</div>
        <nav aria-label="STRONG LONG">
          {NAV.map(item => <button key={item.id} type="button" onClick={() => setView(item.id)}
            className={`nav-item ${view === item.id ? "active" : ""}`}
            title={item.label} aria-current={view === item.id ? "page" : undefined}>
            <span className="nav-icon">{item.symbol}</span><span className="nav-copy"><strong>{item.label}</strong><small>{item.description}</small></span>
          </button>)}
        </nav>
      </div>
      <div className="sidebar-bottom">
        <a href="https://bababot-market-radar.vercel.app" target="_blank" rel="noreferrer" className="legacy-link">↗ Open Legacy BabaBot</a>
        <div className="sidebar-guard"><span className="guard-dot"/><div><strong>READ-ONLY MODE</strong><small>No LIVE / PAPER controls</small></div></div>
        <div className="sidebar-version">vNext 0.4 · Stages 01–04</div>
      </div>
    </aside>

    <div className="main">
      <header className="topbar">
        <div className="breadcrumb"><span>BabaBot</span><span className="breadcrumb-sep">/</span><strong>STRONG LONG</strong><span className="breadcrumb-sep">/</span><strong>{NAV.find(n => n.id === view)?.label}</strong></div>
        <div className="top-actions"><span className="top-date">VPS2 RESEARCH</span><span className={`source-mode ${payload.mode}`}>{payload.mode === "sync" ? "PAPER SYNC" : payload.mode === "live" ? "PAPER DIRECT" : payload.mode === "snapshot" ? "SNAPSHOT" : "NO SOURCE"}</span><button type="button" className="refresh-btn" disabled={loading} onClick={() => void reload()}>{loading ? "Loading..." : "↻ Refresh"}</button></div>
      </header>

      <div className="main-content">
        <div className="page-heading">
          <div><div className="section-eyebrow">MARKET DETEKTOR / STRONG LONG</div><h1>{NAV.find(n => n.id === view)?.label}</h1><p>{view === "overview" ? "Monitor forward PAPER outcomes and research branches in one place." : view === "compare" ? "Compare independent strategies only on identical source events." : view === "trades" ? "Inspect actual entry, exit, and source-event attribution." : view === "journal" ? "Realized PAPER PnL, WIB calendar, risk path and fair matched-event comparison." : view === "chart" ? "Recorded PAPER fills on real Binance Futures candles. Replay without look-ahead." : view === "system" ? "Verify provenance, freshness, and read-only integration status." : "Independent modular branches, separated from LIVE execution."}</p></div>
          <span className="paper-indicator"><span/> PAPER ONLY</span>
        </div>

        {(payload.warning || error) && <div className="notice" role="status"><span className="notice-symbol">ⓘ</span><div><strong>{error ? "Data API error" : payload.mode === "snapshot" ? "Timestamped source snapshot" : payload.mode === "sync" ? "Research sync status" : "Source configuration"}</strong><p>{error ?? payload.warning}</p></div></div>}

        {!configured ? <div className="unconfigured panel">
          <div className="empty-icon">◫</div><h2>VPS2 data source belum tersedia</h2><p>Frontend sudah terpasang. Data riset sengaja tidak dipalsukan: konfigurasi authenticated read bridge atau snapshot Vercel Preview diperlukan.</p>
          <code>GET /api/strong</code>
          <div className="empty-links"><button onClick={() => setView("system")}>Data integration details</button><a href="https://bababot-market-radar.vercel.app" target="_blank" rel="noreferrer">Open production terminal ↗</a></div>
        </div> : <>
          {view === "overview" && <>
            <div className="filter-heading"><div className="context-select"><label htmlFor="overview-strategy">STRATEGY FOCUS</label><select id="overview-strategy" value={currentId} onChange={e => setStrategyId(e.target.value)}>{strategies.map(s => <option value={s.id} key={s.id}>{s.label}</option>)}</select></div><div className="filter-asof">As of {fmtTime(Date.parse(snapshot!.generatedAt))}</div></div>
            <div className="kpi-grid">
              <div className="kpi"><span>Net Realized PnL</span><strong className={pnlClass(selected?.netPnl)}>{fmtMoney(selected?.netPnl)}</strong><small>Only CLOSED · {selected?.label}</small></div>
              <div className="kpi"><span>Win Rate</span><strong>{fmtPct(selected?.winRate)}</strong><small>{selected?.wins} WIN / {selected?.losses} LOSS</small></div>
              <div className="kpi"><span>Closed Trades</span><strong>{fmtNumber(selected?.closed)}</strong><small>{selected?.open ?? 0} open · {selected?.dataGap ?? 0} data gaps</small></div>
              <div className="kpi"><span>Research Enrollment</span><strong className="status-value">{selected?.activity}</strong><small>Registry configuration · not process heartbeat</small></div>
            </div>
            {(selected?.closed ?? 0) < 20 && <div className="subtle-alert">Sample warning: {selected?.label} memiliki {selected?.closed} CLOSED trade. WR dan PnL belum membuktikan keunggulan yang konsisten.</div>}
            <div className="overview-grid">
              <section className="panel chart-panel">
                <div className="panel-head"><div><div className="section-eyebrow">PERFORMANCE</div><h2>Realized Equity Curve</h2><p>Cumulative net PnL, ordered by close time</p></div><span className="mini-tag">SOURCE LEDGER</span></div>
                <EquityLine trades={ownTrades}/>
              </section>
              <section className="panel small-panel">
                <div className="panel-head"><div><div className="section-eyebrow">STRATEGY DEFINITION</div><h2>{selected?.label} Modules</h2></div><StatusChip status={selected?.activity ?? ""}/></div>
                <div className="module-showcase">{selected?.moduleLabel}</div>
                <div className="metrics-stack">
                  <div><span>First-order source</span><strong>VPS2 ledger</strong></div>
                  <div><span>Execution account</span><strong>PAPER only</strong></div>
                  <div><span>Last activity</span><strong>{fmtTime(selected?.lastActivityAtMs)}</strong></div>
                  <div><span>Compare mode</span><strong>Same source event</strong></div>
                </div>
                <button className="text-action" onClick={() => setView("compare")}>Explore matched cohorts →</button>
              </section>
            </div>
            <section className="panel"><div className="panel-head"><div><div className="section-eyebrow">RECENT ACTIVITY</div><h2>Latest Closed Trades — {selected?.label}</h2></div><button className="text-action" onClick={() => setView("trades")}>View all trades →</button></div><TradeTable trades={latestClosed} onSelect={selectTrade}/></section>
          </>}

          {view === "strategies" && <>
            <div className="section-metrics"><span>{strategies.length} Registered strategy definitions</span><span>{strategies.filter(s => s.activity === "ACTIVE").length} Configured active branches</span><span>Original A as reference</span></div>
            <section className="panel"><div className="panel-head"><div><div className="section-eyebrow">INDEPENDENT PORTFOLIOS</div><h2>Strategy Registry</h2><p>Results are per branch. Do not add overlapping branches together as portfolio returns.</p></div></div><StrategyTable strategies={strategies} selected={currentId} onSelect={setStrategyId}/></section>
            <div className="panel details-panel"><div className="section-eyebrow">SELECTED BRANCH</div><h2>{selected?.label}</h2><div className="module-showcase">{selected?.moduleLabel}</div><p className="microcopy">Branch {selected?.family}. Transaksi mempunyai identitas PAPER masing-masing, tetapi dapat berasal dari satu kualifikasi sinyal yang sama.</p><button className="text-action" onClick={() => setView("overview")}>Open strategy performance →</button></div>
          </>}

          {view === "compare" && <>
            <div className="subtle-alert">Matched cohort: hanya record dari <strong>source_event_id</strong> yang sama. Cabang yang tidak masuk event tersebut tidak otomatis dihitung sebagai kalah.</div>
            <section className="panel"><div className="panel-head"><div><div className="section-eyebrow">MATCHED FORWARD EVENT</div><h2>Choose Source Signal</h2><p>{grouped.length} qualifying signals have two or more branch records.</p></div></div>
              <div className="compare-filter"><label htmlFor="source-event">ORIGINAL QUALIFICATION</label><select id="source-event" value={chosenGroup?.[0] ?? ""} onChange={e => setSourceFilter(e.target.value)}>{grouped.map(([id, list]) => <option key={id} value={id}>{list[0].symbol} · {fmtTime(list[0].openedAtMs)} · {list.length} branches</option>)}</select></div>
              {chosenGroup ? <><div className="event-banner"><div><small>SYMBOL</small><strong>{chosenGroup[1][0].symbol}</strong></div><div><small>BRANCH RECORDS</small><strong>{chosenGroup[1].length}</strong></div><div><small>SOURCE EVENT</small><code>{shortSource(chosenGroup[0])}</code></div></div>
              <TradeTable trades={[...chosenGroup[1]].sort((a,b)=>a.strategyId.localeCompare(b.strategyId))} onSelect={selectTrade}/></> : <div className="empty-chart">Belum ada matched source events.</div>}
            </section>
          </>}

          {view === "trades" && <>
            <div className="trade-search"><label htmlFor="trade-search-input">SEARCH RECORDS</label><input id="trade-search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Symbol, strategy, close reason, source ID..."/><span>{explorerTrades.length} displayed / {trades.length} total</span></div>
            <div className="explorer-grid">
              <section className="panel"><div className="panel-head"><div><div className="section-eyebrow">READ-ONLY AUDIT TRAIL</div><h2>Independent PAPER Ledger</h2><p>Click a record for details and matched strategy outcomes.</p></div></div><TradeTable trades={explorerTrades} onSelect={selectTrade} selectedId={selectedTrade?.id}/></section>
              <aside className="panel inspector">{selectedTrade ? <TradeDetails trade={selectedTrade} matches={matchingTrades} onOpenChart={() => chartOpen(selectedTrade)}/> : <div className="inspector-empty"><span>⌕</span><h3>Select a trade</h3><p>Entry, exit, reason and cross-branch comparison appear here.</p></div>}</aside>
            </div>
          </>}

          {view === "journal" && <TradeJournal snapshot={snapshot!} onOpenChart={chartOpen}/>}

          {view === "chart" && <>
            {chartTrade ? <>
              <div className="chart-intro"><label htmlFor="chart-trade">SELECT ACTUAL PAPER RECORD</label>
                <select id="chart-trade" value={chartTrade.id} onChange={e => setTradeId(e.target.value)}>
                  {trades.map(t => <option value={t.id} key={t.id}>{t.symbol} · {t.strategyId} · {fmtTime(t.openedAtMs)} · {t.status} · {fmtMoney(t.netPnl)}</option>)}
                </select>
              </div>
              <VelaPaperChart trade={chartTrade} matched={chartMatched}/>
              <section className="panel"><div className="panel-head"><div><div className="section-eyebrow">MATCHED EVENT COHORT</div><h2>Same source event — {chartTrade.symbol}</h2><p>Only branches that actually recorded this event are shown.</p></div></div>
                <TradeTable trades={chartMatched} selectedId={chartTrade.id} onSelect={chartOpen}/>
              </section>
            </> : <div className="panel empty-chart">PAPER ledger is empty — no chart event to display.</div>}
          </>}

          {view === "system" && <>
            <div className="system-grid">
              <section className="panel"><div className="section-eyebrow">DATA PROVENANCE</div><h2>Research Source</h2><div className="metrics-stack">
                <div><span>Source</span><strong>VPS2 Independent PAPER</strong></div>
                <div><span>API schema</span><strong>v{snapshot?.schemaVersion}</strong></div>
                <div><span>Serving mode</span><StatusChip status={payload.mode === "sync" ? "PAPER SYNC" : payload.mode.toUpperCase()}/></div>
                <div><span>Latest VPS2 sync</span><strong>{fmtTime(Date.parse(snapshot!.generatedAt))}</strong></div>
                <div><span>Normalized trades</span><strong>{trades.length}</strong></div>
                <div><span>Ledger families</span><strong>5 · read-only</strong></div>
                <div><span>Browser refresh</span><strong>60 seconds (visible tab)</strong></div>
              </div></section>
              <section className="panel"><div className="section-eyebrow">SAFETY BOUNDARIES</div><h2>Execution Isolation</h2><div className="guard-list">
                <div><span>✓</span> No POST, RUN or PAUSE controls in vNext</div>
                <div><span>✓</span> Original VPS1 LIVE engine untouched</div>
                <div><span>✓</span> SQLite opened read-only, query-only</div>
                <div><span>✓</span> No source events are deduplicated by symbol</div>
                <div><span>✓</span> All times rendered Asia/Jakarta</div>
              </div></section>
            </div>
            <div className="subtle-alert">PAPER sync reads a private object uploaded from VPS2. This is not LIVE trading. The sync timestamp indicates the last successful publisher upload; it is separate from the latest trade activity.</div>
          </>}
        </>}
        <footer className="content-footer"><span>BabaBot vNext · Independent Research</span><span>VPS1 LIVE isolated • No orders • Source truth: VPS2</span></footer>
      </div>
    </div>
  </div>;
}
