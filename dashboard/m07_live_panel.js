/* LIVE · M07 (SL-M04-R30D2) panel for the BabaBot terminal. Browser -> VPS1 m07-api.
   No keys, no admin token. PIN only for ON / LIVE. OFF, close-all, unlock and SHADOW are free. */
(function (global) {
  "use strict";
  const API = "https://core-prod.43-153-193-103.sslip.io/m07";
  const CONFIRM_LIVE = "M07 LIVE REAL MONEY";
  const el = (id) => document.getElementById(id);
  const S = { active: false, status: null, positions: [], signals: [], orders: [], events: [], tFast: null, tSlow: null };

  // ---------- helpers ----------
  const wib = (ms) => ms ? new Date(ms).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "—";
  const usd = (v) => (v === null || v === undefined || v === "" || !isFinite(+v)) ? "—" : "$" + (+v).toFixed(2);
  const px = (v) => { if (v === null || v === undefined || v === "" || !isFinite(+v)) return "—"; const n = +v;
    return n >= 100 ? n.toFixed(2) : n >= 1 ? n.toFixed(4) : n.toPrecision(5); };
  const age = (ms) => ms === null || ms === undefined ? "—" : ms < 1000 ? ms + " ms" : (ms / 1000).toFixed(1) + " dtk";
  const isActivePos = (p) => !/FLAT|CANCELLED/.test(p.state || "");
  function node(tag, cls, text) { const n = document.createElement(tag); if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text; return n; }
  function td(tr, text, cls) { const c = node("td", cls, text === null || text === undefined || text === "" ? "—" : String(text)); tr.appendChild(c); return c; }
  function emptyRow(tb, cols, text) { tb.replaceChildren(); const tr = node("tr"), c = node("td", "empty", text); c.colSpan = cols; tr.appendChild(c); tb.appendChild(tr); }
  function toast(msg) { const t = el("m7Toast"); if (!t) return; t.textContent = msg; t.classList.add("show");
    clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), 4000); }

  const ERR = {
    PIN_WRONG: "PIN salah.", PIN_NOT_CONFIGURED: "PIN belum dipasang.",
    PIN_MUST_BE_6_DIGITS: "PIN harus 6 angka.", PIN_BACKUP_MUST_DIFFER: "PIN cadangan harus beda dari PIN utama.",
    SETUP_CODE_WRONG: "Kode setup salah.", SETUP_CODE_EXPIRED: "Kode setup sudah kedaluwarsa. Minta kode baru.",
    SETUP_CODE_NOT_ISSUED: "Belum ada kode setup aktif. Minta kode baru ke Claude.",
    CONFIRM_PHRASE_REQUIRED: "Kalimat konfirmasi harus persis: " + CONFIRM_LIVE,
    EXECUTOR_LOCKED_UNLOCK_FIRST: "Executor LOCKED. Tekan UNLOCK dulu.", NOT_LOCKED: "Executor tidak sedang LOCKED.",
    PIN_REQUIRED_FOR_LIVE_ON: "Mode LIVE: ON butuh PIN.", PIN_SLOT_MUST_BE_1_OR_2: "Slot PIN harus 1 atau 2.",
    NETWORK: "Tidak bisa menghubungi VPS1.",
  };
  const PROB = {
    NO_COMPLETED_SHADOW_CYCLE: "belum ada 1 siklus SHADOW yang selesai", EXECUTOR_LOCKED: "executor LOCKED",
    UNRESOLVED_ORDER_OUTBOX: "ada order belum terverifikasi", SHADOW_POSITION_STILL_OPEN: "posisi SHADOW masih terbuka",
    PIN_NOT_CONFIGURED: "PIN belum dipasang",
  };
  function errText(code) {
    code = String(code || "");
    let m = code.match(/^PIN_LOCKED_UNTIL_(\d+)$/);
    if (m) return "Terlalu banyak salah. PIN terkunci sampai " + wib(+m[1]) + " WIB.";
    m = code.match(/^PIN_SAME_AS_SLOT_(\d)$/);
    if (m) return "PIN ini sama dengan PIN slot " + m[1] + ". Pakai angka lain.";
    if (code.startsWith("LIVE_REFUSED:")) return "LIVE ditolak: " + code.slice(13).split(",").map((p) => PROB[p] || p).join(", ") + ".";
    return ERR[code] || code;
  }

  async function get(path) {
    const r = await fetch(API + path, { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }
  async function post(action, body) {
    let r;
    try {
      r = await fetch(API + "/control/" + action, { method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
    } catch (e) { throw new Error("NETWORK"); }
    const doc = await r.json().catch(() => ({}));
    if (!r.ok || !doc.ok) throw new Error(doc.error || "HTTP_" + r.status);
    if (doc.status) { S.status = doc.status; renderStatus(); }
    return doc;
  }

  // ---------- dialog ----------
  function ask({ title, text, fields = [], okText = "OK", okClass = "primary", submit }) {
    const dlg = el("m7Dlg");
    el("m7DlgTitle").textContent = title; el("m7DlgText").textContent = text || ""; el("m7DlgErr").textContent = "";
    const box = el("m7DlgFields"); box.replaceChildren();
    for (const f of fields) {
      const lab = node("label", "", f.label); lab.htmlFor = "m7f_" + f.name;
      let inp;
      if (f.options) { inp = document.createElement("select");
        for (const [v, t] of f.options) { const o = node("option", "", t); o.value = v; inp.appendChild(o); }
      } else {
        inp = document.createElement("input"); inp.type = "text"; inp.autocomplete = "off"; inp.spellcheck = false;
        if (f.pin) { inp.type = "password"; inp.inputMode = "numeric"; inp.maxLength = 6; inp.pattern = "[0-9]{6}"; inp.placeholder = "6 angka"; }
        if (f.placeholder) inp.placeholder = f.placeholder;
        inp.required = !f.optional;
      }
      inp.id = "m7f_" + f.name; inp.name = f.name; box.append(lab, inp);
    }
    const ok = el("m7DlgOk"); ok.textContent = okText; ok.className = "btn " + okClass; ok.disabled = false;
    el("m7DlgForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const vals = {}; for (const f of fields) vals[f.name] = el("m7f_" + f.name).value.trim();
      ok.disabled = true; el("m7DlgErr").textContent = "";
      try { const msg = await submit(vals); dlg.close(); if (msg) toast(msg); }
      catch (e) { el("m7DlgErr").textContent = errText(e.message); }
      finally { ok.disabled = false; for (const f of fields) if (f.pin) el("m7f_" + f.name).value = ""; }
    };
    el("m7DlgCancel").onclick = () => dlg.close();
    dlg.showModal();
    const first = box.querySelector("input,select"); if (first) first.focus();
  }

  // ---------- render ----------
  function setText(id, v, cls) { const n = el(id); if (!n) return; n.textContent = v; if (cls !== undefined) n.className = cls; }
  function renderStatus() {
    const st = S.status; if (!st) return;
    const c = st.control || {}, ex = st.executor || {}, pin = st.pin || {}, a = st.account;
    let txt = "—", cls = "";
    if (c.mode === "RUN") { txt = "ON · " + c.send_mode; cls = c.send_mode === "LIVE" ? "yellow" : "green"; }
    else if (c.mode === "PAUSE") { txt = "OFF"; cls = "muted"; }
    else if (c.mode === "EXIT_ONLY") { txt = "EXIT ONLY"; cls = "yellow"; }
    else if (c.mode === "LOCKED") { txt = "LOCKED"; cls = "red"; }
    setText("m7State", txt, "m7-big " + cls);
    setText("m07StrategyStatus", txt);
    setText("m07Meta", txt);
    setText("m7StateSub", (c.send_mode === "SHADOW" ? "SHADOW = cuma mencatat, tidak kirim order ke Binance." : "LIVE = order asli ke Binance (uang asli).") +
      " Diubah " + wib(c.updated_at_ms) + " WIB oleh " + (c.updated_by || "—") + " (" + (c.reason || "—") + ")");
    el("m7On").disabled = c.mode === "RUN" || c.mode === "LOCKED";
    el("m7Off").disabled = c.mode === "PAUSE" || c.mode === "LOCKED";
    el("m7Unlock").classList.toggle("m7-hidden", c.mode !== "LOCKED");
    el("m7Shadow").disabled = c.send_mode === "SHADOW";
    el("m7Live").disabled = c.send_mode === "LIVE";
    const probs = st.live_problems || [];
    setText("m7LiveNote", c.send_mode === "LIVE" ? "Mode LIVE aktif." : probs.length
      ? "LIVE belum bisa: " + probs.map((p) => PROB[p] || p).join(", ") + "." : "Syarat LIVE terpenuhi. LIVE butuh PIN + kalimat konfirmasi.");

    const flat = a ? (a.signed_nonflat_symbols || []).length === 0 && !a.signed_regular_orders_count && !a.signed_algo_orders_count : null;
    const p = (a && a.api_permissions) || {};
    const today = st.m07_realized_today_usdt;
    const kv = [
      ["Saldo wallet", a ? usd(a.usdt_total_wallet_balance) : "—", ""],
      ["Tersedia / unrealized", a ? usd(a.usdt_available_balance) + " / " + usd(a.usdt_total_unrealized_profit) : "—", ""],
      ["PnL M07 hari ini (WIB)", usd(today), +today > 0 ? "green" : +today < 0 ? "red" : ""],
      ["Akun Binance", flat === null ? "—" : flat ? "FLAT" : "ADA POSISI / ORDER", flat === false ? "red" : ""],
      ["Executor", ex.alive ? "HIDUP" : "MATI", ex.alive ? "green" : "red"],
      ["Sinyal VPS2", (ex.source_fresh ? "tersambung" : "TERPUTUS") + " · " + age(ex.source_heartbeat_age_ms), ex.source_fresh ? "green" : "red"],
      ["Kembaran exit VPS1", (st.twin || {}).alive ? "HIDUP" : "MATI", (st.twin || {}).alive ? "green" : "red"],
      ["Withdraw API", p.enableWithdrawals ? "ON ⚠" : "OFF", p.enableWithdrawals ? "red" : "green"],
    ];
    const box = el("m7Kv"); box.replaceChildren();
    kv.forEach(([k, v, c2]) => { const d = node("div"); d.appendChild(node("span", "", k)); d.appendChild(node("strong", c2, v)); box.appendChild(d); });

    const slots = pin.slots || [], sc = pin.setup_code || {};
    setText("m7PinPill", pin.locked ? "TERKUNCI" : slots.length ? slots.length + " PIN AKTIF" : "BELUM ADA",
      "badge " + (pin.locked ? "red" : slots.length ? "green" : "yellow"));
    setText("m7PinInfo", (slots.length ? "PIN terpasang: " + slots.map((s2) => s2 === 1 ? "utama" : "cadangan").join(" + ") + "."
      : "PIN belum dipasang. Selama belum ada PIN, ON hanya ke SHADOW dan LIVE ditolak.") +
      (pin.locked ? " Terkunci sampai " + wib(pin.until_ms) + " WIB." : "") + (sc.pending ? " Kode setup aktif sampai " + wib(sc.expires_ms) + " WIB." : ""));
    el("m7PinChange").disabled = !slots.length;
    if (S.active && global.BabaChart) global.BabaChart.refreshTop();
  }

  function renderTables() {
    let tb = el("m7PosRows");
    const act = S.positions.filter(isActivePos).length;
    setText("m7PosMeta", act + " aktif · " + S.positions.length + " total");
    if (!S.positions.length) emptyRow(tb, 10, "Belum ada posisi M07. Muncul otomatis saat sinyal M07 masuk.");
    else { tb.replaceChildren(); S.positions.forEach((p) => {
      const tr = node("tr", "v2-row"); td(tr, wib(p.opened_at_ms), "mono"); td(tr, p.symbol);
      const m = td(tr, ""); m.appendChild(node("span", "badge " + (p.send_mode === "LIVE" ? "yellow" : "muted"), p.send_mode));
      td(tr, p.state); td(tr, px(p.entry_avg), "mono"); td(tr, px(p.stop_trigger), "mono red"); td(tr, px(p.exit_avg), "mono");
      td(tr, p.leverage ? p.leverage + "x" : "—"); td(tr, p.realized_pnl == null ? "—" : usd(p.realized_pnl), +p.realized_pnl > 0 ? "green" : +p.realized_pnl < 0 ? "red" : "");
      td(tr, p.close_reason);
      tr.onclick = () => global.BabaChart && global.BabaChart.openTrade(p.symbol, p.opened_at_ms, p.entry_avg, "M07-" + p.position_id);
      tb.appendChild(tr); }); }

    tb = el("m7SigRows");
    if (!S.signals.length) emptyRow(tb, 7, "Belum ada sinyal M07 sejak SHADOW dimulai. Menunggu sinyal dari VPS2…");
    else { tb.replaceChildren(); S.signals.forEach((s) => { const tr = node("tr");
      td(tr, wib(s.picked_at_ms), "mono"); td(tr, s.symbol); td(tr, s.send_mode); td(tr, s.outcome); td(tr, s.reason);
      td(tr, age(s.received_at_ms && s.opened_at_ms ? s.received_at_ms - s.opened_at_ms : null));
      td(tr, s.within_4s === undefined || s.within_4s === null ? "—" : s.within_4s ? "≤4 dtk" : "> 4 dtk", s.within_4s === false ? "red" : "");
      tb.appendChild(tr); }); }

    tb = el("m7OrdRows");
    if (!S.orders.length) emptyRow(tb, 4, "Belum ada order.");
    else { tb.replaceChildren(); S.orders.slice(0, 50).forEach((o) => { const tr = node("tr");
      td(tr, wib(o.updated_at_ms || o.reserved_at_ms), "mono"); td(tr, o.action); td(tr, o.state); td(tr, o.source_key, "m7-wrap"); tb.appendChild(tr); }); }

    tb = el("m7EvRows");
    if (!S.events.length) emptyRow(tb, 3, "Belum ada kejadian.");
    else { tb.replaceChildren(); S.events.slice(0, 60).forEach((e) => { const tr = node("tr");
      td(tr, wib(e.at_ms), "mono"); td(tr, e.kind);
      let d = e.detail_json || "";
      try { const o = JSON.parse(d); d = Object.entries(o).map(([k, v]) => k + "=" + (typeof v === "object" ? JSON.stringify(v) : v)).join("  "); } catch (_) {}
      td(tr, (e.source_key ? e.source_key + "  " : "") + d, "m7-wrap"); tb.appendChild(tr); }); }
  }

  // ---------- polling ----------
  async function loadStatus() { try { S.status = await get("/status"); renderStatus(); } catch (e) { setText("m07StrategyStatus", "VPS1 ?"); } }
  async function loadTables() {
    const jobs = [["/positions", (d) => { S.positions = d.positions || []; }], ["/signals", (d) => { S.signals = d.signals || []; }],
      ["/orders", (d) => { S.orders = d.orders || []; }], ["/events?limit=60", (d) => { S.events = d.events || []; }]];
    await Promise.all(jobs.map(([p, f]) => get(p).then(f).catch(() => {})));
    renderTables();
    if (S.active && global.BabaChart) global.BabaChart.redraw();
  }

  // ---------- public ----------
  function renderTop() {
    const st = S.status || {}, c = st.control || {}, a = st.account || {};
    const act = S.positions.filter(isActivePos);
    setText("stOpenLabel", "M07 posisi aktif / mode"); setText("stOpen", act.length);
    setText("stWr", c.mode ? (c.mode === "RUN" ? "ON " : c.mode + " ") + (c.send_mode || "") : "—");
    setText("stLongPerfLabel", "M07 PnL hari ini (WIB)");
    const t = st.m07_realized_today_usdt;
    setText("stLongPerf", usd(t), "value " + (+t > 0 ? "green" : +t < 0 ? "red" : ""));
    setText("stShortPerfLabel", "Akun Binance"); setText("stShortPerf",
      a.signed_nonflat_symbols ? ((a.signed_nonflat_symbols || []).length ? "ADA POSISI" : "FLAT") : "—", "value");
    setText("stPnlLabel", "Saldo wallet (USDT)"); setText("stPnl", usd(a.usdt_total_wallet_balance), "value");
    setText("stClosed", S.positions.filter((p) => !isActivePos(p)).length);
  }
  function chartMarkers(symbol) {
    const out = [];
    S.positions.filter((p) => p.symbol === symbol).forEach((p) => {
      const t = +p.opened_at_ms;
      if (p.entry_avg) out.push({ id: "M7E-" + p.position_id, symbol, side: "LONG", kind: "ENTRY", time: t, price: +p.entry_avg,
        isOpen: isActivePos(p), status: p.state, source: "M07_" + p.send_mode });
      if (isActivePos(p) && p.stop_trigger) out.push({ id: "M7S-" + p.position_id, symbol, side: "LONG", kind: "LINE", time: t,
        price: +p.stop_trigger, label: "STOP LOSS", color: "#F6465D" });
      if (isActivePos(p) && p.entry_avg) out.push({ id: "M7L-" + p.position_id, symbol, side: "LONG", kind: "LINE", time: t,
        price: +p.entry_avg, label: "ENTRY " + p.send_mode, color: "#1E80FF" });
      if (p.closed_at_ms && p.exit_avg) out.push({ id: "M7X-" + p.position_id, symbol, side: "LONG", kind: "EXIT", time: +p.closed_at_ms,
        price: +p.exit_avg, label: p.close_reason || "", color: +p.realized_pnl >= 0 ? "#0ECB81" : "#F6465D" });
    });
    return out;
  }
  function activate(on) {
    S.active = !!on;
    clearInterval(S.tFast); clearInterval(S.tSlow);
    S.tFast = setInterval(() => { if (!document.hidden) loadStatus(); }, on ? 3000 : 20000);
    S.tSlow = setInterval(() => { if (!document.hidden) loadTables(); }, on ? 10000 : 60000);
    if (on) { loadStatus(); loadTables(); }
  }
  function init() {
    el("m7On").onclick = () => {
      const pinOn = ((S.status || {}).pin || {}).slots && S.status.pin.slots.length > 0;
      ask({ title: "Nyalakan M07 (ON)", okText: "ON", okClass: "primary",
        text: "Mode kirim tetap " + (((S.status || {}).control || {}).send_mode || "—") + "." + (pinOn ? " Masukkan PIN." : " PIN belum dipasang, ON hanya boleh di SHADOW."),
        fields: pinOn ? [{ name: "pin", label: "PIN", pin: true }] : [],
        submit: async (v) => { await post("on", pinOn ? { pin: v.pin } : {}); return "M07 ON."; } });
    };
    el("m7Off").onclick = () => ask({ title: "Matikan M07 (OFF)", okText: "OFF", okClass: "secondary",
      text: "Tidak ada entry baru. Posisi yang sedang terbuka tetap dijaga sampai exit normal / stop loss.",
      submit: async () => { await post("off"); return "M07 OFF."; } });
    el("m7Close").onclick = () => ask({ title: "Tutup semua posisi M07 sekarang?", okText: "TUTUP SEMUA", okClass: "m7-danger",
      text: "M07 jadi OFF dan semua posisi M07 ditutup MARKET sekarang (dicoba ulang sampai flat). Tidak butuh PIN.",
      submit: async () => { await post("close-now"); return "Perintah tutup semua terkirim."; } });
    el("m7Unlock").onclick = () => ask({ title: "UNLOCK executor", okText: "UNLOCK", okClass: "secondary",
      text: "Pastikan penyebab LOCK sudah dicek. Setelah unlock, M07 jadi OFF (bukan langsung ON).",
      submit: async () => { await post("unlock"); return "Executor di-unlock (OFF)."; } });
    el("m7Shadow").onclick = () => ask({ title: "Kembali ke SHADOW", okText: "KE SHADOW", okClass: "secondary",
      text: "Order asli berhenti. Sinyal berikutnya hanya dicatat. Tidak butuh PIN.",
      submit: async () => { await post("shadow"); return "Mode SHADOW."; } });
    el("m7Live").onclick = () => ask({ title: "Aktifkan LIVE (uang asli)", okText: "AKTIFKAN LIVE", okClass: "m7-danger",
      text: "Sinyal M07 berikutnya akan BUY sungguhan di Binance. Ketik persis: " + CONFIRM_LIVE,
      fields: [{ name: "pin", label: "PIN", pin: true }, { name: "confirm", label: "Kalimat konfirmasi", placeholder: CONFIRM_LIVE }],
      submit: async (v) => { await post("live", { pin: v.pin, confirm: v.confirm }); return "LIVE aktif."; } });
    el("m7PinSetup").onclick = () => ask({ title: "Pasang / reset PIN", okText: "SIMPAN PIN", okClass: "primary",
      text: "Masukkan kode setup dari Claude (berlaku 30 menit, sekali pakai). PIN lama (kalau ada) diganti.",
      fields: [{ name: "code", label: "Kode setup", placeholder: "XXXX-XXXX" },
        { name: "pin", label: "PIN utama", pin: true }, { name: "pin2", label: "Ulangi PIN utama", pin: true },
        { name: "pin_backup", label: "PIN cadangan (opsional)", pin: true, optional: true }, { name: "pin_backup2", label: "Ulangi PIN cadangan", pin: true, optional: true }],
      submit: async (v) => {
        if (v.pin !== v.pin2) throw new Error("PIN utama dan ulangannya tidak sama.");
        if (v.pin_backup !== v.pin_backup2) throw new Error("PIN cadangan dan ulangannya tidak sama.");
        await post("pin-setup", { code: v.code, pin: v.pin, pin_backup: v.pin_backup || null }); return "PIN tersimpan."; } });
    el("m7PinChange").onclick = () => ask({ title: "Ganti / tambah PIN", okText: "SIMPAN", okClass: "primary",
      text: "Pakai PIN yang sekarang (utama atau cadangan) untuk mengganti salah satu slot.",
      fields: [{ name: "pin", label: "PIN sekarang", pin: true }, { name: "slot", label: "Slot yang diganti", options: [["1", "PIN utama"], ["2", "PIN cadangan"]] },
        { name: "new_pin", label: "PIN baru", pin: true }, { name: "new_pin2", label: "Ulangi PIN baru", pin: true }],
      submit: async (v) => { if (v.new_pin !== v.new_pin2) throw new Error("PIN baru dan ulangannya tidak sama.");
        await post("pin-change", { pin: v.pin, slot: +v.slot, new_pin: v.new_pin }); return "PIN diganti."; } });
    loadStatus(); loadTables();
  }
  global.M07Live = { init, activate, renderTop, chartMarkers, onTab: () => {} };
})(window);
