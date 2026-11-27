/* Signal-source health indicator (display only). Reads the VPS2 strong-source watchdog summary
   relayed inside GET /m07/research. Never pauses, closes or changes anything. */
(function (global) {
  "use strict";
  const API = "https://core-prod.43-153-193-103.sslip.io/m07";
  const WATCHDOG_DEAD_MS = 180000;
  const el = (id) => document.getElementById(id);
  const UNIT = {
    "md-s8b-research-source": "scanner", "md-s8c1-research-approval": "approval AI",
    "md-research-native-paper-source": "sumber Original A", "md-research-strong-frozen-paper": "STRONG paper",
    "md-research-ip02-local-adapter": "adapter ip02", "md-research-ip04b-shared-clock": "clock ip04b",
    "md-m068-research-snapshot-vps1": "sinkron dashboard", "md-research-strong-m04-m05-modular-paper": "paper M04–M05",
    "md-research-strong-r30-d2-independent-paper": "paper M06–M08", "md-m07-original-a-vps1-shadow-relay": "relay sinyal M07",
    "md-m07-official-paper-exit-vps1-relay": "relay close M07", "md-research-ip03-strong-public-ws": "WS ip03",
  };
  const PREFIX = {
    TIMER_NOT_ACTIVE_ENABLED: "Timer mati", SERVICE_FAILURE: "Service gagal", SERVICE_LOG_STALE: "Service tidak jalan",
    RUNNER_NOT_ACTIVE: "Proses mati", RUNNER_LOG_STALE: "Proses diam", MONITOR_QUERY_FAILED: "Tidak bisa dicek",
  };
  let last = null;

  const ago = (s) => { if (s === null || s === undefined || !isFinite(s)) return "?"; s = Math.max(0, s);
    return s < 90 ? Math.round(s) + " dtk" : s < 5400 ? Math.round(s / 60) + " mnt" : s < 172800 ? (s / 3600).toFixed(1) + " jam" : (s / 86400).toFixed(1) + " hari"; };
  function unitName(raw) { const base = String(raw || "").replace(/\.(service|timer)$/, ""); return UNIT[base] || base; }
  function issueText(code, scan) {
    scan = scan || {};
    switch (code) {
      case "SCAN_RECEIPT_STALE_OR_CLOCK_INVALID": return "Scanner VPS2 berhenti: scan terakhir " + ago(scan.receipt_age_s) + " lalu";
      case "SCAN_CANDLE_STALE_OR_CLOCK_INVALID": return "Data candle scanner basi (" + ago(scan.candle_age_s) + ")";
      case "SCAN_RESULT_NOT_PASS": return "Scan terakhir tidak lulus (" + (scan.result || "?") + ")";
      case "SCAN_UNIVERSE_INCOMPLETE": return "Scan tidak lengkap (" + (scan.completed ?? "?") + "/" + (scan.scanned ?? "?") + " koin, gagal " + (scan.failed ?? "?") + ")";
      case "SCAN_RATE_LIMIT_OR_BREAKER": return "Scanner kena limit Binance / circuit breaker";
      case "SCAN_RECEIPT_UNREADABLE": return "Hasil scan tidak terbaca";
    }
    const i = code.indexOf(":");
    if (i > 0 && PREFIX[code.slice(0, i)]) return PREFIX[code.slice(0, i)] + ": " + unitName(code.slice(i + 1));
    return code;
  }

  function evaluate(resp) {
    const now = Date.now();
    if (!resp || !resp.research) return { level: "dead", label: "RELAY VPS2 ?", detail: ["Snapshot VPS2 belum diterima VPS1."] };
    const r = resp.research;
    if (!resp.fresh) return { level: "dead", label: "RELAY VPS2 TERPUTUS",
      detail: ["Snapshot VPS2 terakhir " + ago((resp.age_ms || 0) / 1000) + " lalu. Status sumber sinyal tidak bisa dipastikan."] };
    const w = r.watchdog;
    if (!w) return { level: "unknown", label: "WATCHDOG ?", detail: ["Status watchdog VPS2 belum dikirim."] };
    if (!w.available) return { level: "dead", label: "WATCHDOG MATI", detail: ["Status watchdog VPS2 tidak terbaca (" + (w.error || "?") + ")."] };
    const wAge = now - w.checked_ms;
    if (wAge > WATCHDOG_DEAD_MS) return { level: "dead", label: "WATCHDOG MATI",
      detail: ["Watchdog VPS2 terakhir mengecek " + ago(wAge / 1000) + " lalu (harusnya tiap 1 menit)."] };
    const sc = w.scan || {};
    const base = "Scan VPS2 terakhir " + ago(sc.receipt_age_s) + " lalu · " + (sc.completed ?? "?") + "/" + (sc.scanned ?? "?") + " koin · watchdog cek " + ago(wAge / 1000) + " lalu";
    if (w.health === "OK") return { level: "ok", label: "SUMBER OK", detail: [base] };
    const det = (w.issues || []).map((c) => issueText(c, sc));
    return { level: "alert", label: "SUMBER ALERT", detail: (det.length ? det : ["Watchdog melaporkan masalah."]).concat([base]) };
  }

  function render(st) {
    last = st;
    const pill = el("srcHealth");
    if (pill) {
      pill.className = "src-pill " + st.level;
      pill.querySelector(".src-label").textContent = st.label;
      pill.title = st.detail.join("\n");
    }
    const note = el("m7SrcNote");
    if (note) {
      note.className = "m7-src-note " + st.level;
      note.replaceChildren();
      const head = document.createElement("strong"); head.textContent = "Sumber sinyal VPS2: " + st.label; note.appendChild(head);
      st.detail.forEach((d) => { const s = document.createElement("span"); s.textContent = d; note.appendChild(s); });
      if (st.level !== "ok") { const s = document.createElement("span"); s.className = "m7-src-hint";
        s.textContent = "Selama sumber bermasalah, sinyal M07 baru tidak akan masuk. Posisi yang sudah terbuka tetap dijaga executor + stop loss."; note.appendChild(s); }
    }
  }

  async function load() {
    try {
      const r = await fetch(API + "/research", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      render(evaluate(await r.json()));
    } catch (e) {
      render({ level: "dead", label: "VPS1 ?", detail: ["Tidak bisa membaca status dari VPS1 (" + (e.message || "error") + ")."] });
    }
  }
  function init() {
    load();
    setInterval(() => { if (!document.hidden) load(); }, 30000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) load(); });
  }
  global.SourceHealth = { init, load, evaluate, last: () => last };
})(window);
