/* STRONG LONG · VPS2 official PAPER M06–M08. Read-only view of the VPS2 snapshot
   relayed to VPS1 (GET /m07/research, refreshed by VPS2 every 60 s). No orders, no tokens. */
(function (global) {
  "use strict";
  const API = "https://core-prod.43-153-193-103.sslip.io/m07";
  const NAMES = ["M06", "M07", "M08"];
  const PARENT_NOTE = { M06: "M03 + R30/D2", M07: "M04 E1 + R30/D2 · diikuti LIVE", M08: "M05 + R30/D2" };
  const s = { active: false, data: null, fresh: false, age: null, err: null, pick: "M07", timer: null, seq: 0 };
  const el = (id) => document.getElementById(id);
  const txt = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));
  const usd = (v) => (v === null || v === undefined || !isFinite(+v) ? "—" : (+v >= 0 ? "+$" : "-$") + Math.abs(+v).toFixed(2));
  const px = (v) => { if (v === null || v === undefined || !isFinite(+v)) return "—"; const n = +v;
    return n >= 100 ? n.toFixed(2) : n >= 1 ? n.toFixed(4) : n.toPrecision(5); };
  const wib = (ms) => ms ? new Date(ms).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) + " WIB" : "—";
  const dur = (a, b) => { if (!a || !b) return "—"; const sec = Math.round((b - a) / 1000);
    return sec < 60 ? sec + " dtk" : Math.floor(sec / 60) + " mnt " + (sec % 60) + " dtk"; };
  const pct = (e, x) => (e && x ? ((x / e - 1) * 100).toFixed(2) + "%" : "—");

  function node(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text; return n; }
  function td(tr, text, cls) { const c = node("td", cls, txt(text)); tr.appendChild(c); return c; }

  function strat() { return s.data && s.data.strategies ? s.data.strategies[s.pick] : null; }
  function stats(st) {
    const rows = st ? st.positions : [];
    const closed = rows.filter((r) => r.status === "CLOSED");
    const wins = closed.filter((r) => +r.pnl > 0).length, losses = closed.filter((r) => +r.pnl < 0).length;
    const net = closed.reduce((a, r) => a + (+r.pnl || 0), 0);
    const gp = closed.filter((r) => +r.pnl > 0).reduce((a, r) => a + +r.pnl, 0);
    const gl = closed.filter((r) => +r.pnl < 0).reduce((a, r) => a - +r.pnl, 0);
    const open = rows.filter((r) => r.status === "OPEN").length;
    const gap = rows.filter((r) => r.status === "DATA_GAP").length;
    const byReason = {};
    closed.forEach((r) => { const k = r.reason || "—"; const b = byReason[k] || (byReason[k] = { n: 0, net: 0, w: 0 });
      b.n++; b.net += +r.pnl || 0; if (+r.pnl > 0) b.w++; });
    return { rows, closed: closed.length, wins, losses, net, open, gap,
      wr: closed.length ? (wins / closed.length) * 100 : null, pf: gl ? gp / gl : gp ? Infinity : null,
      avg: closed.length ? net / closed.length : null, byReason };
  }

  async function load() {
    const seq = ++s.seq;
    try {
      const r = await fetch(API + "/research", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const d = await r.json();
      if (seq !== s.seq) return;
      s.data = d.research; s.fresh = !!d.fresh; s.age = d.age_ms; s.err = d.research ? null : "Snapshot VPS2 belum ada";
    } catch (e) { if (seq === s.seq) s.err = e.message || "gagal"; }
    render();
    if (global.BabaChart) { global.BabaChart.refreshTop(); global.BabaChart.redraw(); }
  }

  function chip() {
    const st = stats(strat());
    const c = el("vps2StrategyStatus");
    if (c) c.textContent = s.err && !s.data ? "VPS2 · tidak terhubung" : s.pick + " · " + st.closed + "t · " + usd(st.net) + (st.open ? " · " + st.open + " OPEN" : "");
  }

  function renderPicker(root) {
    const bar = node("div", "v2-bar");
    const left = node("div", "v2-picker");
    NAMES.forEach((n) => {
      const b = node("button", "btn" + (n === s.pick ? " active" : ""), n);
      b.title = PARENT_NOTE[n];
      b.onclick = () => { s.pick = n; try { sessionStorage.setItem("baba_vps2_pick", n); } catch (_) {}
        render(); if (global.BabaChart) { global.BabaChart.refreshTop(); global.BabaChart.redraw(); } };
      left.appendChild(b);
    });
    bar.appendChild(left);
    const info = node("div", "v2-src");
    const d = s.data;
    info.textContent = d ? "Sumber: VPS2 paper resmi · service " + (d.runner_active ? "HIDUP" : "MATI") + " · snapshot " +
      (s.age !== null ? Math.round(s.age / 1000) + " dtk lalu" : "—") + (s.fresh ? "" : " · TERLAMBAT") +
      " · aktif sejak " + wib(d.activation_epoch_ms) : (s.err ? "VPS2: " + s.err : "Memuat snapshot VPS2…");
    if (d && (!s.fresh || !d.runner_active)) info.classList.add("red");
    bar.appendChild(info);
    root.appendChild(bar);
  }

  function renderOverview(root, st) {
    const ov = node("div", "shadow-overview v2-overview");
    const card = (label, val, cls, small) => { const c = node("div", "shadow-stat"); c.appendChild(node("span", "", label));
      c.appendChild(node("strong", cls || "", val)); if (small) c.appendChild(node("small", "", small)); ov.appendChild(c); };
    card("Strategi", s.pick, "", PARENT_NOTE[s.pick]);
    card("Closed · W / L", st.closed + " · " + st.wins + " / " + st.losses, "", "breakeven tidak dihitung W/L");
    card("Win rate", st.wr === null ? "—" : st.wr.toFixed(1) + "%", "", "closed saja");
    card("Net PnL (paper)", usd(st.net), st.net >= 0 ? "green" : "red", "rata-rata " + usd(st.avg));
    card("Profit factor", st.pf === null ? "—" : st.pf === Infinity ? "∞" : st.pf.toFixed(2), "", "gross win / gross loss");
    card("Open / data gap", st.open + " / " + st.gap, st.open ? "yellow" : "", "posisi paper aktif");
    root.appendChild(ov);
  }

  function renderTrades(root, st) {
    root.appendChild(node("div", "pane-meta", "Klik baris untuk membuka chart di waktu trade itu (▲ entry · ■ exit). Data paper resmi VPS2, bukan order asli."));
    const wrap = node("div", "table-wrap"), t = node("table"), th = node("thead"), hr = node("tr");
    ["Entry (WIB)", "Simbol", "Status", "Harga entry", "Exit (WIB)", "Harga exit", "Gerak", "Lama", "Alasan close", "PnL"]
      .forEach((h) => hr.appendChild(node("th", "", h)));
    th.appendChild(hr); t.appendChild(th);
    const tb = node("tbody");
    const rows = st.rows.slice().sort((a, b) => b.opened_ms - a.opened_ms);
    if (!rows.length) { const tr = node("tr"), c = node("td", "empty");
      c.colSpan = 10; c.appendChild(node("strong", "", "Belum ada trade " + s.pick));
      c.appendChild(node("span", "", "Trade baru muncul otomatis begitu paper VPS2 membuka posisi.")); tr.appendChild(c); tb.appendChild(tr); }
    rows.forEach((r) => {
      const tr = node("tr", "v2-row"); tr.tabIndex = 0;
      td(tr, wib(r.opened_ms), "mono"); td(tr, r.symbol);
      const sc = td(tr, ""); sc.appendChild(node("span", "m7-tag " + (r.status === "OPEN" ? "yellow" : "muted"), r.status));
      td(tr, px(r.entry_price), "mono"); td(tr, wib(r.close_ms), "mono"); td(tr, px(r.exit_price), "mono");
      const mv = r.entry_price && r.exit_price ? r.exit_price / r.entry_price - 1 : null;
      td(tr, pct(r.entry_price, r.exit_price), mv === null ? "" : mv >= 0 ? "green" : "red");
      td(tr, r.status === "OPEN" ? dur(r.opened_ms, Date.now()) : dur(r.opened_ms, r.close_ms));
      td(tr, r.reason);
      td(tr, r.status === "CLOSED" ? usd(r.pnl) : "—", +r.pnl > 0 ? "green" : +r.pnl < 0 ? "red" : "");
      const open = () => global.BabaChart && global.BabaChart.openTrade(r.symbol, r.opened_ms, r.entry_price, "VPS2-" + r.source_id);
      tr.onclick = open; tr.onkeydown = (e) => { if (e.key === "Enter") open(); };
      tb.appendChild(tr);
    });
    t.appendChild(tb); wrap.appendChild(t); root.appendChild(wrap);
  }

  function renderStats(root, st) {
    root.appendChild(node("div", "pane-meta", "Rekap per alasan close (" + s.pick + "). Sampel kecil; belum bisa disimpulkan secara statistik."));
    const wrap = node("div", "table-wrap"), t = node("table"), th = node("thead"), hr = node("tr");
    ["Alasan close", "Jumlah", "Menang", "Net PnL", "Rata-rata"].forEach((h) => hr.appendChild(node("th", "", h)));
    th.appendChild(hr); t.appendChild(th);
    const tb = node("tbody"), keys = Object.keys(st.byReason).sort((a, b) => st.byReason[b].n - st.byReason[a].n);
    if (!keys.length) { const tr = node("tr"), c = node("td", "empty", "Belum ada trade closed."); c.colSpan = 5; tr.appendChild(c); tb.appendChild(tr); }
    keys.forEach((k) => { const b = st.byReason[k], tr = node("tr");
      td(tr, k); td(tr, b.n); td(tr, b.w); td(tr, usd(b.net), b.net >= 0 ? "green" : "red"); td(tr, usd(b.net / b.n)); tb.appendChild(tr); });
    t.appendChild(tb); wrap.appendChild(t); root.appendChild(wrap);
    const cmp = node("div", "pane-meta", "Perbandingan M06 / M07 / M08: " + NAMES.map((n) => {
      const x = stats(s.data && s.data.strategies ? s.data.strategies[n] : null);
      return n + " " + x.closed + "t " + (x.wr === null ? "—" : x.wr.toFixed(0) + "%") + " " + usd(x.net);
    }).join(" · "));
    root.appendChild(cmp);
  }

  function journalRows(st) {
    return (st ? st.positions : []).map((r) => ({ id: r.source_id, symbol: r.symbol, open_ms: r.opened_ms, close_ms: r.close_ms,
      entry: r.entry_price, exit: r.exit_price, pnl: r.pnl, reason: r.reason, status: r.status }));
  }

  function render() {
    chip();
    const st = stats(strat());
    const meta = el("vps2Meta"); if (meta) meta.textContent = st.closed + "t" + (st.open ? " · " + st.open + " open" : "");
    const a = el("vps2TradesRoot"), b = el("vps2StatsRoot"), j = el("vps2JournalRoot");
    if (a) { a.replaceChildren(); renderPicker(a); renderOverview(a, st); renderTrades(a, st); }
    if (b) { b.replaceChildren(); renderPicker(b); renderStats(b, st); }
    if (j && global.BabaJournal) {
      global.BabaJournal.render(j, journalRows(strat()), { key: "vps2_" + s.pick,
        emptyText: "Belum ada trade closed untuk " + s.pick + ".",
        note: "Paper resmi VPS2 · PnL dari ledger paper (sudah termasuk fee paper) · tanggal close WIB",
        extraButtons: (bar) => NAMES.forEach((n) => { const b2 = node("button", "btn" + (n === s.pick ? " active" : ""), n);
          b2.onclick = () => { s.pick = n; try { sessionStorage.setItem("baba_vps2_pick", n); } catch (_) {} render();
            if (global.BabaChart) { global.BabaChart.refreshTop(); global.BabaChart.redraw(); } }; bar.appendChild(b2); }),
        onTradeClick: (r) => global.BabaChart && global.BabaChart.openTrade(r.symbol, r.open_ms, r.entry, "VPS2-" + r.id) });
    }
  }

  function renderTop() {
    const st = stats(strat());
    const set = (id, v, cls) => { const n = el(id); if (n) { n.textContent = v; if (cls !== undefined) n.className = cls; } };
    set("stOpenLabel", s.pick + " PAPER Open / WR"); set("stOpen", st.open); set("stWr", st.wr === null ? "—" : st.wr.toFixed(1) + "%");
    set("stLongPerfLabel", s.pick + " LONG · Closed / WR / Net");
    set("stLongPerf", st.closed + "t · " + (st.wr === null ? "—" : st.wr.toFixed(1) + "%") + " · " + usd(st.net), "value " + (st.net >= 0 ? "green" : "red"));
    set("stShortPerfLabel", "SHORT"); set("stShortPerf", "TIDAK ADA", "value muted");
    set("stPnlLabel", s.pick + " Paper Net (VPS2)"); set("stPnl", usd(st.net), "value " + (st.net >= 0 ? "green" : "red"));
    set("stClosed", st.closed);
    chip();
  }

  function chartMarkers(symbol) {
    const st = strat(); if (!st) return [];
    const out = [];
    st.positions.filter((r) => r.symbol === symbol).forEach((r) => {
      if (r.entry_price) out.push({ id: "V2E-" + r.source_id, symbol, side: "LONG", kind: "ENTRY", time: r.opened_ms,
        price: +r.entry_price, isOpen: r.status === "OPEN", status: r.status, source: "VPS2_" + s.pick });
      if (r.close_ms && r.exit_price) out.push({ id: "V2X-" + r.source_id, symbol, side: "LONG", kind: "EXIT", time: r.close_ms,
        price: +r.exit_price, label: r.reason || "", color: +r.pnl >= 0 ? "#0ECB81" : "#F6465D", status: r.status, source: "VPS2_" + s.pick });
    });
    return out;
  }

  function activate(on) {
    s.active = !!on;
    clearInterval(s.timer);
    s.timer = setInterval(() => { if (!document.hidden) load(); }, on ? 30000 : 120000);
    if (on) load();
  }
  function init() {
    try { const p = sessionStorage.getItem("baba_vps2_pick"); if (NAMES.includes(p)) s.pick = p; } catch (_) {}
    load();
  }
  function onTab(name) { if (name === "vps2journal" || name === "vps2stats") render(); }
  function data() { return s.data; }
  global.StrongVPS2 = { init, activate, load, render, renderTop, chartMarkers, onTab, data };
})(window);
