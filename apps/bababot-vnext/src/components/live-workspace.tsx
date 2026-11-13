"use client";

import type { ReactNode } from "react";

export type LiveSection = "overview" | "positions" | "orders" | "risk" | "activity" | "integration";

/** Stage LIVE-SHELL: no client fetch to VPS1 and no execution controls. */
function NullMetric({ label, description }: { label: string; description: string }) {
  return <div className="live-metric">
    <div className="live-metric-label">{label}</div>
    <strong aria-label={label + ": no data available"}>—</strong>
    <small>{description}</small>
  </div>;
}

function EmptyLedger({ eyebrow, title, message, headings }: {
  eyebrow: string; title: string; message: string; headings: string[];
}) {
  return <section className="panel live-table-panel">
    <div className="panel-head"><div><div className="section-eyebrow">{eyebrow}</div><h2>{title}</h2>
      <p>{message}</p></div><span className="live-readonly-pill">READ ONLY · NO SOURCE</span></div>
    <div className="table-wrap">
      <table className="data-table live-table">
        <thead><tr>{headings.map(h=><th key={h}>{h}</th>)}</tr></thead>
        <tbody><tr><td colSpan={headings.length}><div className="live-empty">
          <span aria-hidden="true">◇</span><strong>No VPS1 data connected</strong>
          <p>Rows remain empty until a verified, read-only LIVE snapshot is available. This is not confirmation of zero positions or zero orders.</p>
        </div></td></tr></tbody>
      </table>
    </div>
  </section>;
}

function IntegrationItem({ step, title, children }: { step: string; title: string; children: ReactNode }) {
  return <div className="live-integration-step">
    <div className="live-integration-index">{step}</div>
    <div><h3>{title}</h3><p>{children}</p></div>
  </div>;
}
function LiveSafety(){
  return <section className="panel live-safety">
    <div className="section-eyebrow">ENVIRONMENT SEPARATION</div><h2>Execution remains isolated</h2>
    <div className="live-boundaries">
      <div><span>✓</span> VPS1 execution engine remains untouched</div>
      <div><span>✓</span> No Binance keys or VPS1 credentials in the browser</div>
      <div><span>✓</span> No BUY, SELL, CLOSE, CANCEL, PAUSE or leverage controls</div>
      <div><span>✓</span> Research PAPER PnL never appears in LIVE cards</div>
      <div><span>✓</span> Unavailable values render “—”, never a fabricated zero</div>
    </div>
  </section>;
}

export default function LiveWorkspace({section, onSectionChange}:{
  section:LiveSection; onSectionChange:(section:LiveSection)=>void;
}){
  return <div className="live-workspace">
    <div className="live-banner" role="status">
      <div className="live-status-icon" aria-hidden="true">⌁</div>
      <div className="live-status-copy"><div className="live-status-kicker">LIVE · VPS1 / CONNECTION GATE</div>
        <h2>LIVE monitoring has not been connected yet</h2>
        <p>This is a reserved workspace, not an active trading terminal. Nothing here reads from or sends commands to VPS1. Existing LIVE execution continues independently.</p>
      </div>
      <span className="live-connection-chip">NOT CONNECTED</span>
    </div>

    {section==="overview" && <>
      <div className="live-metric-grid">
        <NullMetric label="Account equity" description="USD · awaiting read-only snapshot"/>
        <NullMetric label="Unrealized PnL" description="LIVE positions · unavailable"/>
        <NullMetric label="Open positions" description="Unknown until VPS1 connects"/>
        <NullMetric label="Daily realized PnL" description="USD · LIVE only · unavailable"/>
      </div>
      <div className="live-panels">
        <section className="panel">
          <div className="panel-head"><div><div className="section-eyebrow">OPERATIONS</div>
            <h2>LIVE account overview</h2><p>Account snapshot and position exposure once the read-only bridge is validated.</p></div></div>
          <div className="live-account-rows">
            {[
              ["Available balance","—"],["Margin in use","—"],["Active strategy","—"],
              ["Risk-guard status","—"],["Last valid VPS1 data","—"]
            ].map(([k,v])=><div key={k}><span>{k}</span><strong>{v}</strong></div>)}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><div><div className="section-eyebrow">RECENT LIVE EVENTS</div><h2>Activity feed</h2>
            <p>Order, fill, risk and account events will appear only after source validation.</p></div></div>
          <div className="live-empty"><span aria-hidden="true">⋯</span><strong>No connected event stream</strong>
            <p>No LIVE events have been retrieved by BabaBot vNext.</p></div>
          <button type="button" className="text-action" onClick={()=>onSectionChange("integration")}>
            See safe integration plan →
          </button>
        </section>
      </div>
      <LiveSafety/>
    </>}

    {section==="positions" && <>
      <div className="live-metric-grid live-metric-grid-three">
        <NullMetric label="Open positions" description="Not verified — not zero"/>
        <NullMetric label="Open notional" description="USD · no source"/>
        <NullMetric label="Unrealized PnL" description="USD · no source"/>
      </div>
      <EmptyLedger eyebrow="VPS1 LIVE" title="Open Positions" message="Position and margin information, separated from PAPER."
        headings={["Symbol","Side","Strategy","Entry","Mark","Size / Margin","Unrealized PnL","Updated"]}/>
    </>}

    {section==="orders" && <>
      <div className="live-metric-grid live-metric-grid-three">
        <NullMetric label="Working orders" description="Not verified — not zero"/>
        <NullMetric label="Filled today" description="VPS1 events unavailable"/>
        <NullMetric label="Canceled / rejected" description="No LIVE order history"/>
      </div>
      <EmptyLedger eyebrow="READ-ONLY EXECUTION AUDIT" title="Order Monitor" message="A future audit trail, not an order entry form."
        headings={["Time (WIB)","Order ID","Symbol","Side","Type","Quantity","Status","Reason"]}/>
      <div className="live-warning"><strong>Execution is intentionally disabled.</strong> This page will never send an order merely because the dashboard is open. Any future trading controls require an independent security review and explicit authorization.</div>
    </>}

    {section==="risk" && <>
      <div className="live-metric-grid">
        <NullMetric label="Risk guard state" description="No status telemetry"/>
        <NullMetric label="Daily loss used" description="USD · no source"/>
        <NullMetric label="Daily loss limit" description="Not read from VPS1"/>
        <NullMetric label="Margin exposure" description="Unverified"/>
      </div>
      <div className="live-panels">
        <section className="panel">
          <div className="section-eyebrow">RISK MONITOR</div><h2>Protections & limits</h2>
          <div className="live-account-rows">
            {["Daily loss cutoff","Max per-position notional","Leverage configuration","Reduce-only closing guard","Emergency halt state","Exchange API health"].map(k=><div key={k}><span>{k}</span><strong>—</strong></div>)}
          </div>
        </section>
        <LiveSafety/>
      </div>
      <div className="live-warning">A missing telemetry value is <strong>not</strong> evidence that a safety guard is active. Actual VPS1 execution safeguards remain outside this UI.</div>
    </>}

    {section==="activity" && <>
      <EmptyLedger eyebrow="VPS1 LIVE" title="Trading Activity & Audit" message="Timestamped fills, strategy decisions and risk events — once the backend read contract is connected."
        headings={["Time (WIB)","Event","Symbol","Strategy","Reference","Outcome","Source"]}/>
      <div className="live-warning">No events from the VPS2 PAPER journal are mixed into this LIVE audit log.</div>
    </>}

    {section==="integration" && <>
      <section className="panel live-integration">
        <div className="panel-head"><div><div className="section-eyebrow">ARCHITECTURE · FUTURE CONNECTION</div>
          <h2>Connecting LIVE safely</h2>
          <p>This blueprint does not perform a VPS1 deployment or enable remote execution.</p></div><span className="live-readonly-pill">READ-ONLY FIRST</span></div>
        <div className="live-bridge">
          <div><small>VPS1</small><strong>LIVE execution engine</strong><span>Private existing services · untouched</span></div>
          <span className="live-bridge-arrow">→</span>
          <div><small>Outbound only</small><strong>Sanitized read exporter</strong><span>Read-only projection; no trading keys</span></div>
          <span className="live-bridge-arrow">→</span>
          <div><small>Private transport</small><strong>Authenticated snapshot</strong><span>Scoped server-side access and freshness</span></div>
          <span className="live-bridge-arrow">→</span>
          <div><small>BabaBot UI</small><strong>LIVE monitor</strong><span>View-only account, orders, risk, events</span></div>
        </div>
        <div className="live-integration-list">
          <IntegrationItem step="01" title="Audit existing VPS1 source">Identify authoritative account, position, fill, strategy, and risk-guard read models. Freeze and review fields without changing trading processes.</IntegrationItem>
          <IntegrationItem step="02" title="Create separate outbound read-only exporter">Use distinct credentials and a private snapshot or signed channel. No incoming VPS1 port, no Binance execution key, no direct browser-to-VPS1 traffic.</IntegrationItem>
          <IntegrationItem step="03" title="Validate contract and freshness">Validate schema, account identifier, timestamps, duplicate event IDs, and data staleness. Stale/missing data must fail closed to “DATA UNAVAILABLE”.</IntegrationItem>
          <IntegrationItem step="04" title="Enable monitoring after tests">Wire server-side read APIs to position, order, risk and activity panels. Compare snapshots with VPS1 source, verify access controls, and release via a protected Preview gate.</IntegrationItem>
        </div>
      </section>
      <div className="live-contract-grid">
        <section className="panel"><div className="section-eyebrow">AVAILABLE TODAY</div><h2>Prepared status contract</h2>
          <code className="live-endpoint">GET /api/live/status</code><p>Returns NOT_CONNECTED, snapshot:null, no execution controls. It does not request VPS1 data.</p>
          <div className="live-connection-mini">Source: <strong>VPS1 · not connected</strong></div>
        </section>
        <section className="panel"><div className="section-eyebrow">FUTURE READ CONTRACTS · NOT IMPLEMENTED</div><h2>Monitoring data endpoints</h2>
          <div className="live-contract-list">
            <code>GET /api/live/overview</code><code>GET /api/live/positions</code><code>GET /api/live/orders</code>
            <code>GET /api/live/risk</code><code>GET /api/live/activity</code>
          </div><p>Names are proposed integration contracts, not available endpoints today.</p>
        </section>
      </div>
      <div className="live-warning"><strong>Important:</strong> Access separation is not yet complete because there is no real LIVE source. The existing VPS1 runtime, exchange permissions, and deployed BabaBot production remain unchanged.</div>
    </>}
    <div className="live-bottom-note">LIVE workspace shell · No real-time feed, no order placement, no simulation, no VPS1 connection</div>
  </div>;
}
