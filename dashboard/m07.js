/* M07 Live Terminal: browser -> VPS1 m07-api. No keys, no tokens, PIN only for ON / LIVE. */
(() => {
  "use strict";
  const API = "https://core-prod.43-153-193-103.sslip.io/m07";
  const CONFIRM_LIVE = "M07 LIVE REAL MONEY";
  const $ = (id) => document.getElementById(id);
  const S = { status: null, positions: [], signals: [], iv: "1m", chartSym: null, busy: false };

  // ---------- helpers ----------
  const wib = (ms) => ms ? new Date(ms).toLocaleString("id-ID", { timeZone: "Asia/Jakarta", day: "2-digit",
    month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "—";
  const num = (v, d = 2) => (v === null || v === undefined || v === "" || isNaN(+v)) ? "—" : (+v).toFixed(d);
  const usd = (v) => num(v) === "—" ? "—" : "$" + num(v);
  const px = (v) => { if (v === null || v === undefined || v === "" || isNaN(+v)) return "—";
    const n = +v; return n >= 100 ? n.toFixed(2) : n >= 1 ? n.toFixed(4) : n.toPrecision(5); };
  const age = (ms) => ms === null || ms === undefined ? "—" : ms < 1000 ? ms + " ms" : (ms / 1000).toFixed(1) + " dtk";
  function cell(tr, text, cls) { const td = document.createElement("td"); td.textContent = text ?? "—";
    if (cls) td.className = cls; tr.appendChild(td); return td; }
  function emptyRow(tbody, cols, text) { tbody.replaceChildren(); const tr = document.createElement("tr");
    const td = cell(tr, text, "empty"); td.colSpan = cols; tbody.appendChild(tr); }
  function toast(msg) { const t = $("toast"); t.textContent = msg; t.classList.add("show");
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
    NO_COMPLETED_SHADOW_CYCLE: "belum ada 1 siklus SHADOW yang selesai",
    EXECUTOR_LOCKED: "executor LOCKED", UNRESOLVED_ORDER_OUTBOX: "ada order belum terverifikasi",
    SHADOW_POSITION_STILL_OPEN: "posisi SHADOW masih terbuka", PIN_NOT_CONFIGURED: "PIN belum dipasang",
  };
  function errText(code) {
    code = String(code || "");
    let m = code.match(/^PIN_LOCKED_UNTIL_(\d+)$/);
    if (m) return "Terlalu banyak salah. PIN terkunci sampai " + wib(+m[1]) + " WIB.";
    m = code.match(/^PIN_SAME_AS_SLOT_(\d)$/);
    if (m) return "PIN ini sama dengan PIN slot " + m[1] + ". Pakai angka lain.";
    if (code.startsWith("LIVE_REFUSED:"))
      return "LIVE ditolak: " + code.slice(13).split(",").map((p) => PROB[p] || p).join(", ") + ".";
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
    if (doc.status) renderStatus(doc.status);
    return doc;
  }

  // ---------- dialog ----------
  const dlg = $("dlg");
  function ask({ title, text, fields = [], okText = "OK", okClass = "on", submit }) {
    $("dlgTitle").textContent = title; $("dlgText").textContent = text || ""; $("dlgErr").textContent = "";
    const box = $("dlgFields"); box.replaceChildren();
    for (const f of fields) {
      const lab = document.createElement("label"); lab.textContent = f.label; lab.htmlFor = "f_" + f.name;
      let inp;
      if (f.options) {
        inp = document.createElement("select");
        for (const [v, t] of f.options) { const o = document.createElement("option"); o.value = v; o.textContent = t; inp.appendChild(o); }
      } else {
        inp = document.createElement("input"); inp.type = f.type || "text"; inp.autocomplete = "off";
        if (f.pin) { inp.type = "password"; inp.inputMode = "numeric"; inp.maxLength = 6; inp.pattern = "[0-9]{6}"; inp.placeholder = "6 angka"; }
        if (f.placeholder) inp.placeholder = f.placeholder;
        inp.required = !f.optional; inp.spellcheck = false;
      }
      inp.id = "f_" + f.name; inp.name = f.name;
      box.append(lab, inp);
    }
    const ok = $("dlgOk"); ok.textContent = okText; ok.className = "btn " + okClass; ok.disabled = false;
    $("dlgForm").onsubmit = async (ev) => {
      ev.preventDefault();
      const vals = {}; for (const f of fields) vals[f.name] = $("f_" + f.name).value.trim();
      ok.disabled = true; $("dlgErr").textContent = "";
      try { const msg = await submit(vals); dlg.close(); if (msg) toast(msg); }
      catch (e) { $("dlgErr").textContent = errText(e.message); }
      finally { ok.disabled = false; for (const f of fields) if (f.pin) $("f_" + f.name).value = ""; }
    };
    $("dlgCancel").onclick = () => dlg.close();
    dlg.showModal();
    const first = box.querySelector("input,select"); if (first) first.focus();
  }

  // ---------- status ----------
  function renderStatus(st) {
    S.status = st;
    const c = st.control || {}, ex = st.executor || {}, pin = st.pin || {}, a = st.account;
    const big = $("bigState");
    let txt = "—", cls = "";
    if (c.mode === "RUN") { txt = "ON · " + c.send_mode; cls = c.send_mode === "LIVE" ? "live" : "run"; }
    else if (c.mode === "PAUSE") { txt = "OFF"; cls = "pause"; }
    else if (c.mode === "EXIT_ONLY") { txt = "EXIT ONLY"; cls = "pause"; }
    else if (c.mode === "LOCKED") { txt = "LOCKED"; cls = "locked"; }
    big.textContent = txt; big.className = "big " + cls;
    const modeHelp = c.send_mode === "SHADOW" ? "SHADOW = cuma mencatat, tidak kirim order ke Binance."
      : "LIVE = order asli ke Binance (uang asli).";
    $("stateSub").textContent = modeHelp + " Terakhir diubah " + wib(c.updated_at_ms) + " oleh " + (c.updated_by || "—") + " (" + (c.reason || "—") + ")";

    $("btnOn").disabled = c.mode === "RUN" || c.mode === "LOCKED";
    $("btnOff").disabled = c.mode === "PAUSE" || c.mode === "LOCKED";
    $("btnUnlock").classList.toggle("hidden", c.mode !== "LOCKED");
    $("btnShadow").disabled = c.send_mode === "SHADOW";
    $("btnLive").disabled = c.send_mode === "LIVE";
    const probs = st.live_problems || [];
    $("liveNote").textContent = c.send_mode === "LIVE" ? "Mode LIVE aktif."
      : probs.length ? "LIVE belum bisa: " + probs.map((p) => PROB[p] || p).join(", ") + "." : "Syarat LIVE terpenuhi. LIVE butuh PIN + kalimat konfirmasi.";

    if (a) {
      $("sWallet").textContent = usd(a.usdt_total_wallet_balance);
      $("sAvail").textContent = "tersedia " + usd(a.usdt_available_balance) + " · unrealized " + usd(a.usdt_total_unrealized_profit);
      const flat = (a.signed_nonflat_symbols || []).length === 0 && !a.signed_regular_orders_count && !a.signed_algo_orders_count;
      $("sAcct").textContent = flat ? "FLAT" : "ADA POSISI/ORDER";
      $("sAcct").className = "val " + (flat ? "" : "neg");
      const p = a.api_permissions || {};
      $("sAcctSub").textContent = "posisi " + (a.signed_nonflat_symbols || []).length + " · order " + (a.signed_regular_orders_count ?? "—") + " · stop " + (a.signed_algo_orders_count ?? "—") +
        " · withdraw " + (p.enableWithdrawals ? "ON ⚠" : "OFF") + " · cek " + wib(a.checked_at_ms);
    } else { $("sWallet").textContent = "—"; $("sAvail").textContent = "akun belum terbaca"; $("sAcct").textContent = "—"; }
    const today = st.m07_realized_today_usdt;
    $("sToday").textContent = usd(today); $("sToday").className = "val " + (+today > 0 ? "pos" : +today < 0 ? "neg" : "");
    $("sExec").textContent = ex.alive ? "HIDUP" : "MATI"; $("sExec").className = "val " + (ex.alive ? "pos" : "neg");
    $("sSource").textContent = "sinyal VPS2: " + (ex.source_fresh ? "tersambung" : "TERPUTUS") + " (heartbeat " + age(ex.source_heartbeat_age_ms) + ")";

    const slots = pin.slots || [];
    const pp = $("pinPill");
    pp.textContent = pin.locked ? "TERKUNCI" : slots.length ? slots.length + " PIN aktif" : "BELUM ADA";
    pp.className = "pill " + (pin.locked ? "bad" : slots.length ? "ok" : "warn");
    const names = slots.map((s) => s === 1 ? "utama" : "cadangan").join(" + ");
    const sc = pin.setup_code || {};
    $("pinInfo").textContent = (slots.length ? "PIN terpasang: " + names + "." : "PIN belum dipasang. Selama belum ada PIN, ON cuma bisa ke SHADOW dan LIVE ditolak.") +
      (pin.locked ? " Terkunci sampai " + wib(pin.until_ms) + " WIB." : "") +
      (sc.pending ? " Kode setup aktif sampai " + wib(sc.expires_ms) + " WIB." : "");
    $("btnPinChange").disabled = !slots.length;

    const tw = st.twin || {}, par = st.parity || {};
    const kv = [
      ["Stop loss", "-1,8% dari harga beli (dipasang setelah BUY)"],
      ["Batas rugi M07", "$1 per hari (WIB)"],
      ["Batas drawdown akun", "$5 per hari"],
      ["Ukuran posisi", "$49,5 notional · isolated · leverage 10–25x · maks 1 posisi"],
      ["Exit", "ikut CLOSE paper VPS2 · cadangan: kembaran exit VPS1 · batas waktu 602 dtk"],
      ["Kembaran exit (VPS1)", tw.alive ? "HIDUP" : "MATI"],
      ["Paritas entry", par.sources ? par.vps1_scanner_matches + "/" + par.sources + " sinyal cocok" : "—"],
      ["Tutup-semua terakhir", st.close_now_requested_ms ? wib(st.close_now_requested_ms) : "—"],
    ];
    const box = $("safety"); box.replaceChildren();
    for (const [k, v] of kv) { const a1 = document.createElement("span"); a1.textContent = k; const b = document.createElement("div"); b.textContent = v; box.append(a1, b); }
  }

  // ---------- tables ----------
  function renderPositions(list) {
    S.positions = list; const tb = $("posBody");
    const active = list.filter((p) => !/FLAT|CANCELLED/.test(p.state));
    $("posCount").textContent = active.length + " aktif";
    if (!list.length) return emptyRow(tb, 9, "Belum ada posisi M07.");
    tb.replaceChildren();
    for (const p of list) {
      const tr = document.createElement("tr");
      cell(tr, p.symbol);
      const m = cell(tr, ""); const t = document.createElement("span"); t.className = "tag " + p.send_mode.toLowerCase(); t.textContent = p.send_mode; m.appendChild(t);
      cell(tr, p.state); cell(tr, px(p.entry_avg)); cell(tr, px(p.stop_trigger)); cell(tr, px(p.exit_avg));
      const pnl = p.realized_pnl; cell(tr, pnl == null ? "—" : usd(pnl), +pnl > 0 ? "pos" : +pnl < 0 ? "neg" : "");
      cell(tr, wib(p.opened_at_ms)); cell(tr, p.close_reason || "—");
      tb.appendChild(tr);
    }
  }
  function renderSignals(list) {
    S.signals = list; const tb = $("sigBody"); $("sigCount").textContent = list.length + " sinyal";
    if (!list.length) return emptyRow(tb, 6, "Belum ada sinyal M07 sejak SHADOW dimulai. Menunggu…");
    tb.replaceChildren();
    for (const s of list) {
      const tr = document.createElement("tr");
      cell(tr, wib(s.picked_at_ms)); cell(tr, s.symbol); cell(tr, s.send_mode); cell(tr, s.outcome); cell(tr, s.reason || "—");
      cell(tr, age(s.received_at_ms && s.opened_at_ms ? s.received_at_ms - s.opened_at_ms : null));
      tb.appendChild(tr);
    }
  }
  function renderOrders(list) {
    const tb = $("ordBody");
    if (!list.length) return emptyRow(tb, 4, "Belum ada order.");
    tb.replaceChildren();
    for (const o of list.slice(0, 30)) {
      const tr = document.createElement("tr");
      cell(tr, wib(o.updated_at_ms || o.reserved_at_ms)); cell(tr, o.action); cell(tr, o.state); cell(tr, o.source_key || "—", "wrap");
      tb.appendChild(tr);
    }
  }
  function renderEvents(list) {
    const tb = $("evBody");
    if (!list.length) return emptyRow(tb, 3, "Belum ada kejadian.");
    tb.replaceChildren();
    for (const e of list.slice(0, 40)) {
      const tr = document.createElement("tr");
      cell(tr, wib(e.at_ms)); cell(tr, e.kind);
      let d = e.detail_json || "";
      try { const o = JSON.parse(d); d = Object.entries(o).map(([k, v]) => k + "=" + (typeof v === "object" ? JSON.stringify(v) : v)).join("  "); } catch (_) {}
      cell(tr, (e.source_key ? e.source_key + "  " : "") + d, "wrap");
      tb.appendChild(tr);
    }
  }

  // ---------- chart ----------
  function pickChartSymbol() {
    const act = S.positions.find((p) => !/FLAT|CANCELLED/.test(p.state));
    return act ? act.symbol : (S.positions[0] || S.signals[0] || {}).symbol || null;
  }
  async function drawChart() {
    const sym = pickChartSymbol(); S.chartSym = sym;
    const cv = $("chart"), ctx = cv.getContext("2d");
    const W = cv.clientWidth * devicePixelRatio, H = 260 * devicePixelRatio; cv.width = W; cv.height = H;
    ctx.clearRect(0, 0, W, H);
    $("chartTitle").textContent = sym ? "Chart " + sym + " (Binance Futures)" : "Chart";
    if (!sym) { $("chartNote").textContent = "Chart muncul saat ada posisi / sinyal M07."; return; }
    let k;
    try { k = (await get("/market/klines?symbol=" + encodeURIComponent(sym) + "&interval=" + S.iv + "&limit=120")).klines; }
    catch (e) { $("chartNote").textContent = "Chart tidak tersedia (" + e.message + ")."; return; }
    if (!Array.isArray(k) || !k.length) { $("chartNote").textContent = "Data candle kosong."; return; }
    const pos = S.positions.find((p) => p.symbol === sym);
    const lines = [];
    if (pos && pos.entry_avg) lines.push([+pos.entry_avg, "#1e80ff", "entry"]);
    if (pos && pos.stop_trigger) lines.push([+pos.stop_trigger, "#f6465d", "stop loss"]);
    let lo = Math.min(...k.map((c) => +c[3]), ...lines.map((l) => l[0])), hi = Math.max(...k.map((c) => +c[2]), ...lines.map((l) => l[0]));
    const pad = (hi - lo) * 0.06 || hi * 0.01; lo -= pad; hi += pad;
    const right = 70 * devicePixelRatio, cw = (W - right) / k.length;
    const y = (v) => H - ((v - lo) / (hi - lo)) * H;
    ctx.font = 11 * devicePixelRatio + "px Arial"; ctx.fillStyle = "#5e6673";
    for (let i = 0; i <= 4; i++) { const v = lo + (hi - lo) * i / 4; ctx.fillText(px(v), W - right + 6, Math.min(H - 4, Math.max(12 * devicePixelRatio, y(v) + 4))); ctx.fillStyle = "#1a1f26"; ctx.fillRect(0, y(v), W - right, 1); ctx.fillStyle = "#5e6673"; }
    k.forEach((c, i) => {
      const o = +c[1], h = +c[2], l = +c[3], cl = +c[4], x = i * cw + cw / 2;
      ctx.strokeStyle = ctx.fillStyle = cl >= o ? "#0ecb81" : "#f6465d";
      ctx.beginPath(); ctx.moveTo(x, y(h)); ctx.lineTo(x, y(l)); ctx.lineWidth = Math.max(1, devicePixelRatio); ctx.stroke();
      ctx.fillRect(x - cw * 0.35, Math.min(y(o), y(cl)), cw * 0.7, Math.max(1, Math.abs(y(o) - y(cl))));
    });
    for (const [v, col, name] of lines) { ctx.fillStyle = col; ctx.fillRect(0, y(v), W - right, devicePixelRatio); ctx.fillText(name + " " + px(v), 6, y(v) - 4); }
    $("chartNote").textContent = "Terakhir " + px(k[k.length - 1][4]) + " · " + S.iv + " · " + wib(Date.now());
  }

  // ---------- polling ----------
  function setConn(ok, text) { const c = $("conn"); c.className = "conn " + (ok ? "ok" : "bad"); $("connText").textContent = text; }
  async function pollStatus() {
    try { renderStatus(await get("/status")); setConn(true, "VPS1 tersambung · " + wib(Date.now())); }
    catch (e) { setConn(false, "VPS1 tidak terjangkau"); }
  }
  async function pollTables() {
    const tasks = [["/positions", (d) => renderPositions(d.positions || [])], ["/signals", (d) => renderSignals(d.signals || [])],
      ["/orders", (d) => renderOrders(d.orders || [])], ["/events?limit=40", (d) => renderEvents(d.events || [])]];
    await Promise.all(tasks.map(([p, fn]) => get(p).then(fn).catch(() => {})));
    if (pickChartSymbol() !== S.chartSym) drawChart();
  }
  function loop(fn, ms) { const run = async () => { if (!document.hidden) await fn(); setTimeout(run, ms); }; run(); }

  // ---------- actions ----------
  $("btnOn").onclick = () => {
    const pinOn = (S.status?.pin?.slots || []).length > 0;
    ask({ title: "Nyalakan M07 (ON)", okText: "ON",
      text: "Mode kirim tetap " + (S.status?.control?.send_mode || "—") + "." + (pinOn ? " Masukkan PIN." : " PIN belum dipasang, jadi ON hanya boleh di SHADOW."),
      fields: pinOn ? [{ name: "pin", label: "PIN", pin: true }] : [],
      submit: async (v) => { await post("on", pinOn ? { pin: v.pin } : {}); return "M07 ON."; } });
  };
  $("btnOff").onclick = () => ask({ title: "Matikan M07 (OFF)", okText: "OFF", okClass: "off",
    text: "Tidak ada entry baru. Posisi yang sedang terbuka tetap dijaga sampai exit normal / stop loss.",
    submit: async () => { await post("off"); return "M07 OFF."; } });
  $("btnClose").onclick = () => ask({ title: "Tutup semua posisi M07 sekarang?", okText: "TUTUP SEMUA", okClass: "danger",
    text: "M07 jadi OFF dan semua posisi M07 ditutup MARKET sekarang juga (dicoba ulang sampai flat). Tidak butuh PIN.",
    submit: async () => { await post("close-now"); return "Perintah tutup semua terkirim."; } });
  $("btnUnlock").onclick = () => ask({ title: "UNLOCK executor", okText: "UNLOCK",
    text: "Pastikan penyebab LOCK sudah dicek. Setelah unlock, M07 jadi OFF (bukan langsung ON).",
    submit: async () => { await post("unlock"); return "Executor di-unlock (OFF)."; } });
  $("btnShadow").onclick = () => ask({ title: "Kembali ke SHADOW", okText: "KE SHADOW",
    text: "Order asli berhenti. Sinyal berikutnya hanya dicatat. Tidak butuh PIN.",
    submit: async () => { await post("shadow"); return "Mode SHADOW."; } });
  $("btnLive").onclick = () => ask({ title: "Aktifkan LIVE (uang asli)", okText: "AKTIFKAN LIVE", okClass: "danger",
    text: "Sinyal M07 berikutnya akan BUY sungguhan di Binance. Ketik persis: " + CONFIRM_LIVE,
    fields: [{ name: "pin", label: "PIN", pin: true }, { name: "confirm", label: "Kalimat konfirmasi", placeholder: CONFIRM_LIVE }],
    submit: async (v) => { await post("live", { pin: v.pin, confirm: v.confirm }); return "LIVE aktif."; } });

  $("btnPinSetup").onclick = () => ask({ title: "Pasang / reset PIN", okText: "SIMPAN PIN",
    text: "Masukkan kode setup dari Claude (berlaku 30 menit, sekali pakai). PIN lama (kalau ada) akan diganti.",
    fields: [{ name: "code", label: "Kode setup", placeholder: "XXXX-XXXX" },
      { name: "pin", label: "PIN utama", pin: true }, { name: "pin2", label: "Ulangi PIN utama", pin: true },
      { name: "pin_backup", label: "PIN cadangan (opsional)", pin: true, optional: true }, { name: "pin_backup2", label: "Ulangi PIN cadangan", pin: true, optional: true }],
    submit: async (v) => {
      if (v.pin !== v.pin2) throw new Error("PIN utama dan ulangannya tidak sama.");
      if (v.pin_backup !== v.pin_backup2) throw new Error("PIN cadangan dan ulangannya tidak sama.");
      await post("pin-setup", { code: v.code, pin: v.pin, pin_backup: v.pin_backup || null });
      return "PIN tersimpan.";
    } });
  $("btnPinChange").onclick = () => ask({ title: "Ganti / tambah PIN", okText: "SIMPAN",
    text: "Pakai PIN yang sekarang (utama atau cadangan) untuk mengganti salah satu slot.",
    fields: [{ name: "pin", label: "PIN sekarang", pin: true },
      { name: "slot", label: "Slot yang diganti", options: [["1", "PIN utama"], ["2", "PIN cadangan"]] },
      { name: "new_pin", label: "PIN baru", pin: true }, { name: "new_pin2", label: "Ulangi PIN baru", pin: true }],
    submit: async (v) => {
      if (v.new_pin !== v.new_pin2) throw new Error("PIN baru dan ulangannya tidak sama.");
      await post("pin-change", { pin: v.pin, slot: +v.slot, new_pin: v.new_pin });
      return "PIN diganti.";
    } });

  $("ivSeg").onclick = (e) => { const b = e.target.closest("button"); if (!b) return;
    S.iv = b.dataset.iv; for (const x of $("ivSeg").children) x.classList.toggle("act", x === b); drawChart(); };
  addEventListener("resize", () => { clearTimeout(drawChart._r); drawChart._r = setTimeout(drawChart, 200); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { pollStatus(); pollTables(); } });

  loop(pollStatus, 3000);
  loop(pollTables, 10000);
  loop(drawChart, 15000);
})();
