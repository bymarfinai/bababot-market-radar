/* Shared trade journal for the BabaBot terminal (vanilla port of the vNext Trade Journal ideas).
   Input rows are already-realized ledger outcomes; PnL is never recomputed here.
   Row: {id, symbol, open_ms, close_ms, entry, exit, pnl, reason, status}. CLOSED rows only count. */
(function (global) {
  "use strict";
  const WIB = 7 * 3600e3;
  const states = {};
  const node = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text; return n; };
  const usd = (v) => (v === null || v === undefined || !isFinite(+v)) ? "—" : (+v >= 0 ? "+$" : "-$") + Math.abs(+v).toFixed(2);
  const px = (v) => { if (v === null || v === undefined || !isFinite(+v)) return "—"; const n = +v;
    return n >= 100 ? n.toFixed(2) : n >= 1 ? n.toFixed(4) : n.toPrecision(5); };
  const dayKey = (ms) => new Date(ms + WIB).toISOString().slice(0, 10);
  const monthKey = (ms) => dayKey(ms).slice(0, 7);
  const wib = (ms) => ms ? new Date(ms).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit", hour12: false }) : "—";
  const hold = (s) => s === null || !isFinite(s) ? "—" : s < 60 ? Math.round(s) + " dtk" : Math.floor(s / 60) + " mnt " + Math.round(s % 60) + " dtk";
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

  function realized(rows) {
    return rows.filter((r) => r.status === "CLOSED" && r.close_ms && r.pnl !== null && r.pnl !== undefined && isFinite(+r.pnl))
      .sort((a, b) => a.close_ms - b.close_ms);
  }
  function overview(closed) {
    let wins = 0, losses = 0, be = 0, gp = 0, gl = 0, net = 0, peak = 0, dd = 0, cur = 0, ws = 0, ls = 0, bws = 0, bls = 0, holdSum = 0, holdN = 0;
    let best = null, worst = null;
    closed.forEach((r) => {
      const p = +r.pnl; net += p;
      if (p > 0) { wins++; gp += p; ws++; ls = 0; } else if (p < 0) { losses++; gl -= p; ls++; ws = 0; } else { be++; ws = 0; ls = 0; }
      bws = Math.max(bws, ws); bls = Math.max(bls, ls);
      cur += p; peak = Math.max(peak, cur); dd = Math.max(dd, peak - cur);
      if (best === null || p > best) best = p; if (worst === null || p < worst) worst = p;
      if (r.open_ms && r.close_ms) { holdSum += (r.close_ms - r.open_ms) / 1000; holdN++; }
    });
    const n = closed.length, dec = wins + losses;
    return { n, wins, losses, be, net, wr: dec ? wins / dec * 100 : null, pf: gl ? gp / gl : gp ? Infinity : null,
      exp: n ? net / n : null, avgWin: wins ? gp / wins : null, avgLoss: losses ? -gl / losses : null,
      best, worst, maxDD: dd, avgHold: holdN ? holdSum / holdN : null, bws, bls };
  }

  function drawLines(canvas, pts, opts) {
    const dpr = global.devicePixelRatio || 1, W = canvas.clientWidth || 300, H = opts.h || 150;
    canvas.width = Math.floor(W * dpr); canvas.height = Math.floor(H * dpr); canvas.style.height = H + "px";
    const c = canvas.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
    c.fillStyle = "#0b0e11"; c.fillRect(0, 0, W, H);
    c.font = "9px ui-monospace,SFMono-Regular,Menlo,monospace"; c.fillStyle = "#5e6673";
    if (pts.length < 2) { c.fillText(opts.empty || "Belum cukup trade closed", 10, H / 2); return; }
    const L = 8, R = 58, T = 10, B = 16, vs = pts.map((p) => p.v).concat([0]);
    let lo = Math.min(...vs), hi = Math.max(...vs); if (hi === lo) { hi += 1; lo -= 1; }
    const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
    const x = (i) => L + (W - L - R) * i / (pts.length - 1), y = (v) => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
    c.strokeStyle = "#2b3139"; c.setLineDash([3, 3]); c.beginPath(); c.moveTo(L, y(0)); c.lineTo(W - R, y(0)); c.stroke(); c.setLineDash([]);
    [hi - pad, 0, lo + pad].forEach((v) => c.fillText(usd(v), W - R + 4, y(v) + 3));
    if (opts.area) { c.fillStyle = opts.area; c.beginPath(); c.moveTo(x(0), y(0)); pts.forEach((p, i) => c.lineTo(x(i), y(p.v)));
      c.lineTo(x(pts.length - 1), y(0)); c.closePath(); c.fill(); }
    c.strokeStyle = opts.color; c.lineWidth = 1.5; c.beginPath(); pts.forEach((p, i) => i ? c.lineTo(x(i), y(p.v)) : c.moveTo(x(i), y(p.v))); c.stroke();
    if (opts.dots) pts.forEach((p, i) => { if (!i) return; c.fillStyle = p.d >= 0 ? "#0ECB81" : "#F6465D"; c.beginPath(); c.arc(x(i), y(p.v), 2.5, 0, 7); c.fill(); });
    c.fillStyle = "#5e6673"; c.fillText(wib(pts[1].t), L, H - 4);
    const last = wib(pts[pts.length - 1].t); c.fillText(last, W - R - c.measureText(last).width, H - 4);
  }

  function card(box, label, val, cls, small) {
    const c = node("div", "shadow-stat"); c.appendChild(node("span", "", label)); c.appendChild(node("strong", cls || "", val));
    if (small) c.appendChild(node("small", "", small)); box.appendChild(c);
  }
  function table(heads, rows, empty) {
    const wrap = node("div", "table-wrap"), t = node("table"), th = node("thead"), hr = node("tr");
    heads.forEach((h) => hr.appendChild(node("th", "", h))); th.appendChild(hr); t.appendChild(th);
    const tb = node("tbody");
    if (!rows.length) { const tr = node("tr"), c = node("td", "empty", empty || "—"); c.colSpan = heads.length; tr.appendChild(c); tb.appendChild(tr); }
    rows.forEach((r) => tb.appendChild(r)); t.appendChild(tb); wrap.appendChild(t); return wrap;
  }
  function tdx(tr, v, cls) { tr.appendChild(node("td", cls, v === null || v === undefined || v === "" ? "—" : String(v))); }

  function csv(rows, name) {
    const esc = (v) => { const s = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    const lines = [["open_wib", "close_wib", "symbol", "entry", "exit", "move_pct", "hold_s", "close_reason", "pnl_usdt"].join(",")];
    rows.forEach((r) => lines.push([dayKey(r.open_ms) + " " + new Date(r.open_ms + WIB).toISOString().slice(11, 19),
      dayKey(r.close_ms) + " " + new Date(r.close_ms + WIB).toISOString().slice(11, 19), r.symbol, r.entry, r.exit,
      r.entry && r.exit ? ((r.exit / r.entry - 1) * 100).toFixed(4) : "", r.open_ms ? Math.round((r.close_ms - r.open_ms) / 1000) : "",
      r.reason, (+r.pnl).toFixed(6)].map(esc).join(",")));
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    const a = node("a"); a.href = url; a.download = name + ".csv"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function render(root, rows, opts) {
    opts = opts || {};
    const key = opts.key || "journal", st = states[key] || (states[key] = { month: "ALL", day: null });
    const all = realized(rows || []);
    const months = Array.from(new Set(all.map((r) => monthKey(r.close_ms)))).sort();
    if (st.month !== "ALL" && !months.includes(st.month)) { st.month = "ALL"; st.day = null; }
    const scope = st.month === "ALL" ? all : all.filter((r) => monthKey(r.close_ms) === st.month);
    const o = overview(scope);
    const rerender = () => render(root, rows, opts);
    root.replaceChildren();

    // filter bar
    const bar = node("div", "v2-bar");
    const left = node("div", "v2-picker");
    if (opts.extraButtons) opts.extraButtons(left);
    const sel = node("select", "j-select"); sel.setAttribute("aria-label", "Bulan (tanggal close WIB)");
    [["ALL", "Semua bulan"]].concat(months.map((m) => [m, MONTHS[+m.slice(5) - 1] + " " + m.slice(0, 4)])).forEach(([v, t]) => {
      const op = node("option", "", t); op.value = v; if (v === st.month) op.selected = true; sel.appendChild(op); });
    sel.onchange = () => { st.month = sel.value; st.day = null; rerender(); };
    left.appendChild(sel);
    const exp = node("button", "btn secondary", "Export CSV"); exp.disabled = !scope.length;
    exp.onclick = () => csv(st.day ? scope.filter((r) => dayKey(r.close_ms) === st.day) : scope, key + "_" + st.month + (st.day ? "_" + st.day : ""));
    left.appendChild(exp);
    bar.appendChild(left);
    bar.appendChild(node("div", "v2-src", opts.note || "PnL = hasil ledger (sudah termasuk fee). Hanya trade CLOSED; tanggal = tanggal close WIB."));
    root.appendChild(bar);

    if (!all.length) { root.appendChild(node("div", "j-empty", opts.emptyText || "Belum ada trade closed.")); return; }

    // overview
    const ov = node("div", "shadow-overview v2-overview j-overview");
    card(ov, "Closed · W / L / BE", o.n + " · " + o.wins + " / " + o.losses + " / " + o.be);
    card(ov, "Win rate", o.wr === null ? "—" : o.wr.toFixed(1) + "%", "", "breakeven tidak dihitung");
    card(ov, "Net PnL", usd(o.net), o.net >= 0 ? "green" : "red", "expectancy " + usd(o.exp) + " / trade");
    card(ov, "Profit factor", o.pf === null ? "—" : o.pf === Infinity ? "∞" : o.pf.toFixed(2), "", "rata menang " + usd(o.avgWin) + " · kalah " + usd(o.avgLoss));
    card(ov, "Max drawdown", o.maxDD ? "-$" + o.maxDD.toFixed(2) : "$0.00", o.maxDD ? "red" : "", "dari puncak PnL kumulatif (bukan saldo)");
    card(ov, "Streak · lama hold", o.bws + "W / " + o.bls + "L", "", "rata hold " + hold(o.avgHold) + " · terbaik " + usd(o.best) + " · terburuk " + usd(o.worst));
    root.appendChild(ov);

    // curves
    const pts = [{ t: scope.length ? scope[0].close_ms : 0, v: 0, d: 0 }]; let cum = 0, peak = 0; const ddp = [{ t: pts[0].t, v: 0 }];
    scope.forEach((r) => { cum += +r.pnl; peak = Math.max(peak, cum); pts.push({ t: r.close_ms, v: cum, d: +r.pnl }); ddp.push({ t: r.close_ms, v: cum - peak }); });
    const curves = node("div", "j-curves");
    const c1 = node("div", "j-curve"), c2 = node("div", "j-curve");
    c1.appendChild(node("div", "j-title", "Kurva PnL kumulatif (urut waktu close)"));
    c2.appendChild(node("div", "j-title", "Drawdown dari puncak (USD)"));
    const cv1 = node("canvas"), cv2 = node("canvas"); c1.appendChild(cv1); c2.appendChild(cv2);
    curves.append(c1, c2); root.appendChild(curves);
    requestAnimationFrame(() => {
      drawLines(cv1, pts, { color: o.net >= 0 ? "#0ECB81" : "#F6465D", dots: true, h: 150 });
      drawLines(cv2, ddp, { color: "#F6465D", area: "rgba(246,70,93,.18)", h: 150, empty: "Belum ada drawdown" });
    });

    // calendar + per symbol
    const lower = node("div", "j-lower");
    const calBox = node("div", "j-cal-box");
    const calMonth = st.month === "ALL" ? (months[months.length - 1] || monthKey(Date.now())) : st.month;
    calBox.appendChild(node("div", "j-title", "Kalender harian · " + MONTHS[+calMonth.slice(5) - 1] + " " + calMonth.slice(0, 4) + " (tanggal close WIB) · klik hari untuk filter"));
    const byDay = {};
    all.filter((r) => monthKey(r.close_ms) === calMonth).forEach((r) => { const k = dayKey(r.close_ms);
      const d = byDay[k] || (byDay[k] = { n: 0, net: 0 }); d.n++; d.net += +r.pnl; });
    const cal = node("div", "j-cal");
    ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"].forEach((d) => cal.appendChild(node("div", "j-dow", d)));
    const y = +calMonth.slice(0, 4), m = +calMonth.slice(5) - 1, first = new Date(Date.UTC(y, m, 1)), days = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    for (let i = 0; i < (first.getUTCDay() + 6) % 7; i++) cal.appendChild(node("div", "j-day j-pad"));
    for (let d = 1; d <= days; d++) {
      const k = calMonth + "-" + String(d).padStart(2, "0"), info = byDay[k];
      const cell = node("button", "j-day" + (info ? (info.net > 0 ? " pos" : info.net < 0 ? " neg" : " flat") : "") + (st.day === k ? " sel" : ""));
      cell.type = "button"; cell.appendChild(node("b", "", String(d)));
      if (info) { cell.appendChild(node("span", "", usd(info.net))); cell.appendChild(node("small", "", info.n + "t"));
        cell.onclick = () => { st.day = st.day === k ? null : k; if (st.month === "ALL") st.month = calMonth; rerender(); }; }
      else cell.disabled = true;
      cal.appendChild(cell);
    }
    calBox.appendChild(cal); lower.appendChild(calBox);

    const symBox = node("div", "j-sym-box");
    symBox.appendChild(node("div", "j-title", "Kontribusi per simbol"));
    const bySym = {};
    scope.forEach((r) => { const s = bySym[r.symbol] || (bySym[r.symbol] = { n: 0, w: 0, net: 0 }); s.n++; if (+r.pnl > 0) s.w++; s.net += +r.pnl; });
    const symRows = Object.keys(bySym).sort((a, b) => bySym[b].net - bySym[a].net).map((k) => {
      const s = bySym[k], tr = node("tr"); tdx(tr, k); tdx(tr, s.n); tdx(tr, s.w + "/" + (s.n - s.w));
      tdx(tr, usd(s.net), s.net >= 0 ? "green" : "red"); tdx(tr, o.net ? (s.net / Math.abs(o.net) * 100).toFixed(0) + "%" : "—"); return tr; });
    symBox.appendChild(table(["Simbol", "Trade", "W/L", "Net", "% dari |net|"], symRows));
    lower.appendChild(symBox); root.appendChild(lower);

    // journal table
    const list = (st.day ? scope.filter((r) => dayKey(r.close_ms) === st.day) : scope).slice().reverse();
    root.appendChild(node("div", "pane-meta", "Jurnal trade " + (st.day ? "tanggal " + st.day + " (klik hari yang sama untuk batal)" : st.month === "ALL" ? "semua bulan" : st.month) +
      " · " + list.length + " trade" + (opts.onTradeClick ? " · klik baris untuk buka chart" : "")));
    const trs = list.map((r) => { const tr = node("tr", opts.onTradeClick ? "v2-row" : "");
      tdx(tr, wib(r.close_ms), "mono"); tdx(tr, r.symbol); tdx(tr, px(r.entry), "mono"); tdx(tr, px(r.exit), "mono");
      const mv = r.entry && r.exit ? (r.exit / r.entry - 1) * 100 : null; tdx(tr, mv === null ? "—" : mv.toFixed(2) + "%", mv === null ? "" : mv >= 0 ? "green" : "red");
      tdx(tr, hold(r.open_ms ? (r.close_ms - r.open_ms) / 1000 : null)); tdx(tr, r.reason); tdx(tr, usd(r.pnl), +r.pnl > 0 ? "green" : +r.pnl < 0 ? "red" : "");
      if (opts.onTradeClick) tr.onclick = () => opts.onTradeClick(r);
      return tr; });
    root.appendChild(table(["Close (WIB)", "Simbol", "Entry", "Exit", "Gerak", "Lama", "Alasan close", "PnL"], trs, "Tidak ada trade di filter ini."));
  }
  global.BabaJournal = { render, overview, realized, dayKey };
})(window);
