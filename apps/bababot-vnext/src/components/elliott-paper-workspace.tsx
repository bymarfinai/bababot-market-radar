"use client";

export type ElliottView = "overview" | "strategies" | "trades" | "integration";

/**
 * Reserved Elliott Wave PAPER presentation. This component intentionally
 * receives NO Strong Long snapshot and makes NO network/ledger calls.
 */
function UnavailableMetric({ label, context }: { label: string; context: string }) {
  return <div className="elliott-metric">
    <span>{label}</span><strong aria-label={label + ": no connected PAPER data"}>—</strong><small>{context}</small>
  </div>;
}

function EmptyElliottTable({ title, description, columns }: {
  title: string; description: string; columns: string[];
}) {
  return <section className="panel elliott-panel">
    <div className="panel-head"><div><div className="section-eyebrow">ELLIOTT WAVE / VPS2</div>
      <h2>{title}</h2><p>{description}</p></div>
      <span className="elliott-not-connected">NOT CONNECTED</span>
    </div>
    <div className="table-wrap"><table className="data-table">
      <thead><tr>{columns.map(c=><th key={c}>{c}</th>)}</tr></thead>
      <tbody><tr><td colSpan={columns.length}><div className="elliott-empty">
        <strong>No Elliott Wave PAPER ledger connected</strong>
        <p>No entries, exits, W/L counts or strategy statuses are being inferred from STRONG LONG or historical research summaries.</p>
      </div></td></tr></tbody>
    </table></div>
  </section>;
}

export default function ElliottPaperWorkspace({
  view, onViewChange, onSelectStrongLong
}: {
  view: ElliottView;
  onViewChange: (view: ElliottView) => void;
  onSelectStrongLong: () => void;
}) {
  return <div className="elliott-root">
    <div className="elliott-alert" role="status">
      <div className="elliott-alert-glyph" aria-hidden="true">∿</div>
      <div>
        <div className="section-eyebrow">PAPER · VPS2 · ELLIOTT WAVE</div>
        <h2>Strategy workspace is ready — source not connected</h2>
        <p>This space is reserved for Elliott Wave PAPER strategies. It is separate from STRONG LONG, with no live, paper or backtest data fabricated.</p>
      </div>
      <span className="elliott-not-connected">NO SOURCE</span>
    </div>

    {view==="overview" && <>
      <div className="elliott-kpis">
        <UnavailableMetric label="Net realized PAPER PnL" context="USD · awaiting EW ledger"/>
        <UnavailableMetric label="Win Rate" context="No CLOSED EW trades retrieved"/>
        <UnavailableMetric label="CLOSED trades" context="Unavailable — not zero"/>
        <UnavailableMetric label="Active EW branches" context="Registry not connected"/>
      </div>
      <div className="elliott-two-column">
        <section className="panel elliott-panel">
          <div className="section-eyebrow">PAPER PERFORMANCE</div><h2>Elliott Wave Equity & Outcomes</h2>
          <div className="elliott-empty"><strong>Awaiting an Elliott Wave PAPER source</strong>
            <p>Equity, drawdown and outcomes must be computed from authoritative closed EW records, independently of STRONG LONG branches.</p>
          </div>
          <button type="button" className="text-action" onClick={()=>onViewChange("integration")}>View integration requirements →</button>
        </section>
        <section className="panel elliott-panel">
          <div className="section-eyebrow">STRATEGY DIRECTORY</div><h2>Independent EW Models</h2>
          <div className="elliott-empty"><strong>No strategy registry loaded</strong>
            <p>The actual 4H, 1H and other Elliott Wave research branches will be displayed after a verified registry is connected, not inferred from previous analyses.</p>
          </div>
          <button type="button" className="text-action" onClick={()=>onViewChange("strategies")}>Open strategy directory →</button>
        </section>
      </div>
    </>}

    {view==="strategies" && <EmptyElliottTable
      title="Elliott Wave PAPER Strategy Registry"
      description="Each independent variant will retain its own parent ID, timeframe, status, and outcomes."
      columns={["Parent / Strategy","Timeframe","Paper state","CLOSED","W / L","Net realized USD"]}/>}

    {view==="trades" && <EmptyElliottTable
      title="Elliott Wave PAPER Trade Explorer"
      description="Once verified, browse exact entry, exit, decision and source-event provenance."
      columns={["Open (WIB)","Symbol","EW Strategy","Status","Entry / Exit","Net PnL","Close reason"]}/>}

    {view==="integration" && <>
      <section className="panel elliott-panel">
        <div className="panel-head"><div><div className="section-eyebrow">RESEARCH INTEGRATION · FUTURE TASK</div>
          <h2>Elliott Wave independent PAPER sync</h2>
          <p>Connect a vetted VPS2 read-only Elliott Wave ledger without reusing STRONG LONG records.</p></div>
          <span className="elliott-not-connected">NOT STARTED</span></div>
        <div className="elliott-pipeline">
          <div><small>VPS2 EW ledgers</small><strong>Authoritative source</strong></div><span>→</span>
          <div><small>Isolated export</small><strong>Read-only normalization</strong></div><span>→</span>
          <div><small>Private snapshot</small><strong>Separate schema & ID</strong></div><span>→</span>
          <div><small>BabaBot PAPER</small><strong>Elliott Wave UI</strong></div>
        </div>
        <div className="elliott-rules">
          <h3>Release gates</h3>
          <p>Confirm the actual EW strategies and PAPER ledgers on VPS2; normalize trades and parent/variant references; preserve independent source_event_id; audit fees, timestamps and signal lineage; compare resulting numbers against each originating ledger before enabling charts or statistics.</p>
          <p>Research source changes and LIVE trading are out of scope for this UI-only change. No OPEN row may be counted as realized PnL, and missing EW data must never fall back to STRONG LONG.</p>
        </div>
      </section>
      <section className="panel elliott-panel">
        <div className="section-eyebrow">SOURCE CONTRACT</div><h2>Read-only connection state</h2>
        <code className="elliott-endpoint">GET /api/paper/elliott/status</code>
        <p className="elliott-contract-note">Returns NOT_CONNECTED with a null snapshot. Future EW data endpoints are not implemented.</p>
      </section>
    </>}

    <div className="elliott-footer">
      <span>PAPER strategies remain independent · ELLIOTT WAVE unconnected</span>
      <button type="button" onClick={onSelectStrongLong}>← Back to connected STRONG LONG</button>
    </div>
  </div>;
}
