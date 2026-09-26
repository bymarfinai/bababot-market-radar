# BabaBot Market Radar — Frozen Blueprint

**Status:** FROZEN PLAN  
**Purpose:** Dokumen acuan utama untuk development BabaBot Market Radar.  
**Rule:** Development tidak boleh menambah, mengubah, atau menggeser scope inti tanpa keputusan eksplisit baru.

---

## 1. Tujuan Utama

BabaBot Market Radar adalah sistem live untuk memantau seluruh Binance USDT Perpetual, mendeteksi coin yang mulai bergerak, menilai arah LONG/SHORT, dan menghasilkan keputusan akhir yang dapat diinspeksi oleh AI melalui MCP.

BabaBot Market Radar **bukan** engine backtest dan **bukan** tempat discovery strategy.

Backtest, discovery, eksperimen, optimisasi parameter, dan riset historis tetap berada di:

`bymarfinai/bababot-discovery`

Production/live system berada di:

`bymarfinai/bababot-market-radar`

---

# 2. Frozen Core Plan

Urutan/fungsi inti BabaBot Market Radar adalah:

1. **Scan semua Binance USDT Perpetual tiap ±5 menit**
2. **Deteksi coin yang mulai bergerak**
3. **Klasifikasi `IGNITION / EXPANSION / EXHAUSTION`**
4. **Hitung `LONG_SCORE / SHORT_SCORE`**
5. **Baca volume, breakout/breakdown, taker flow, OI, funding, market regime**
6. **Hasil akhirnya `LONG / SHORT / NO TRADE`**
7. **Expose data lewat MCP supaya AI bisa inspeksi**
8. **Dashboard live + alert**
9. **Nantinya bisa diteruskan ke execution**

Urutan ini adalah blueprint utama dan tidak boleh diganti dengan flow lain tanpa keputusan eksplisit.

---

# 3. Flow Sistem

```text
Binance USDT Perpetual
        │
        ▼
Scan seluruh market ±5 menit
        │
        ▼
Moving Coin Detector
        │
        ▼
Deteksi coin yang mulai bergerak
        │
        ▼
IGNITION / EXPANSION / EXHAUSTION
        │
        ▼
LONG_SCORE / SHORT_SCORE
        │
        ▼
Market Context
├── Volume
├── Breakout / Breakdown
├── Taker Flow
├── Open Interest
├── Funding
└── Existing Market Regime
        │
        ▼
LONG / SHORT / NO TRADE
        │
        ▼
MCP
        │
        ▼
AI Inspection
        │
        ▼
Dashboard Live + Alert
        │
        ▼
Future Execution Layer
```

---

# 4. Moving Coin Detector

Moving Coin Detector atau **MCD** adalah detector baru yang menjadi core dari BabaBot Market Radar.

MCD bertugas menjawab pertanyaan utama:

> Coin mana yang sedang mulai bergerak, ke arah mana tekanan dominannya, dan apakah pergerakan tersebut cukup valid untuk masuk ke radar LONG atau SHORT?

MCD bukan backtesting engine.

MCD bukan strategy discovery engine.

MCD bekerja pada market data live.

---

# 5. Step 1 — Scan Semua Binance USDT Perpetual

Market Radar melakukan scanning terhadap universe Binance USDT Perpetual.

Target cadence:

```text
± setiap 5 menit
```

Scan harus berorientasi pada closed market data yang tersedia pada saat proses berjalan.

Tujuannya bukan memilih top gainer/top loser berdasarkan hasil akhir, tetapi mengidentifikasi secara live coin yang menunjukkan tanda awal pergerakan.

Output awal scanner minimal:

```text
symbol
timestamp
price
market_activity_snapshot
```

---

# 6. Step 2 — Deteksi Coin yang Mulai Bergerak

Setelah market scan, MCD mencari perubahan kondisi yang menunjukkan coin mulai keluar dari kondisi normal.

Fokus utama adalah **early movement detection**, bukan mengejar coin yang sudah terlalu jauh bergerak.

Detector harus membedakan antara:

```text
noise
normal movement
early movement
strong continuation
late / exhausted movement
```

Coin yang tidak menunjukkan movement yang relevan tidak perlu diteruskan ke tahap berikutnya.

---

# 7. Step 3 — Movement Stage

Setiap candidate diklasifikasikan ke salah satu stage utama:

## IGNITION

Pergerakan baru mulai terbentuk.

Karakter umum:

```text
momentum mulai muncul
activity meningkat
volume mulai meningkat
direction mulai terbentuk
belum terlalu extended
```

## EXPANSION

Pergerakan sudah terkonfirmasi dan sedang berkembang.

Karakter umum:

```text
momentum kuat
direction jelas
volume/activity mendukung
structure mendukung
pressure masih berlanjut
```

## EXHAUSTION

Pergerakan sudah terlalu jauh, kehilangan confirmation, atau menunjukkan risiko terlambat masuk.

Karakter umum:

```text
extension terlalu tinggi
momentum melemah
flow tidak lagi mendukung
breakout/breakdown kehilangan tenaga
risk/reward memburuk
```

Stage ini merupakan klasifikasi movement, bukan keputusan final trade.

---

# 8. Step 4 — LONG_SCORE / SHORT_SCORE

Setiap candidate dihitung dengan dua score terpisah:

```text
LONG_SCORE
SHORT_SCORE
```

LONG dan SHORT tidak boleh diasumsikan sebagai mirror sederhana satu sama lain.

Tujuan scoring:

```text
mengukur kekuatan bukti LONG
mengukur kekuatan bukti SHORT
mengukur gap antar arah
mendeteksi konflik arah
```

Contoh output:

```text
SOLUSDT

LONG_SCORE  : 84
SHORT_SCORE : 21
STAGE       : IGNITION
```

Jika dua score terlalu dekat atau bukti saling bertentangan, sistem harus mampu memilih:

```text
NO TRADE
```

---

# 9. Step 5 — Market Context yang Dibaca

MCD dan Direction Scoring membaca konteks berikut:

## 9.1 Volume

Digunakan untuk melihat apakah movement didukung peningkatan activity nyata.

Fokus utama:

```text
current volume
relative volume
volume expansion
volume confirmation
```

## 9.2 Breakout / Breakdown

Digunakan untuk melihat apakah price structure menunjukkan pelepasan dari range atau level penting.

Output harus dapat membedakan:

```text
breakout
breakdown
failed breakout
failed breakdown
no structural break
```

## 9.3 Taker Flow

Digunakan untuk membaca agresivitas buyer dan seller.

Tujuannya adalah melihat apakah movement price didukung oleh market taker pressure.

## 9.4 Open Interest

Open Interest harus menggunakan **raw open interest**, bukan USD-valued open interest sebagai dasar perubahan posisi.

Interpretasi dasar:

```text
Price ↑ + OI ↑
= fresh long participation / new positioning

Price ↑ + OI ↓
= short covering

Price ↓ + OI ↑
= fresh short participation / new positioning

Price ↓ + OI ↓
= long liquidation
```

OI adalah confirmation/context, bukan satu-satunya sumber keputusan.

## 9.5 Funding

Funding digunakan sebagai market positioning context.

Funding tidak berdiri sendiri sebagai trigger LONG/SHORT.

## 9.6 Market Regime

Market regime **sudah existing di BabaBot**.

Market Radar tidak membuat Regime Engine baru sebagai project terpisah.

Market Radar hanya membaca atau menggunakan output market regime existing apabila diperlukan sebagai context.

Contoh context:

```text
BULL
BEAR
SIDEWAYS
```

Regime bukan detector baru yang sedang dikembangkan dalam Market Radar.

---

# 10. Step 6 — Final Decision

Setelah stage, score, dan market context tersedia, sistem menghasilkan salah satu dari tiga keputusan final:

```text
LONG
SHORT
NO TRADE
```

Contoh:

```text
symbol      : SOLUSDT
stage       : IGNITION
long_score  : 84
short_score : 21
decision    : LONG
```

Atau:

```text
symbol      : ENAUSDT
stage       : EXPANSION
long_score  : 54
short_score : 57
decision    : NO TRADE
```

`NO TRADE` adalah keputusan valid dan penting.

Sistem tidak diwajibkan menghasilkan trade pada setiap scan.

---

# 11. Step 7 — MCP

Data Market Radar harus diexpose melalui MCP sehingga AI dapat melakukan inspection berdasarkan data live.

Tujuan MCP:

```text
AI dapat membaca hasil radar
AI dapat inspect symbol tertentu
AI dapat melihat score dan stage
AI dapat melihat market context
AI dapat membandingkan candidate
AI tidak perlu menebak market data
```

MCP bukan pengganti Moving Coin Detector.

MCP adalah interface antara Market Radar dan AI.

---

# 12. AI Inspection Layer

AI bekerja setelah Market Radar menghasilkan data deterministic.

AI bukan sumber market data.

AI melakukan inspection terhadap candidate yang sudah dihasilkan sistem.

Flow:

```text
Market Radar
     │
     ▼
Candidate + Feature Snapshot
     │
     ▼
MCP
     │
     ▼
AI Inspection
```

AI dapat memberikan analisis tambahan berdasarkan informasi yang tersedia, tetapi source market state tetap berasal dari Market Radar.

---

# 13. Step 8 — Dashboard Live + Alert

Market Radar mempunyai dashboard live untuk melihat kondisi sistem secara real time.

Dashboard minimal harus mampu menampilkan:

```text
market scanner
moving coins
symbol
current price
IGNITION / EXPANSION / EXHAUSTION
LONG_SCORE
SHORT_SCORE
LONG / SHORT / NO TRADE
volume context
breakout / breakdown
taker flow
OI
funding
market regime
AI inspection result
signal history
system status
```

Contoh tampilan conceptual:

```text
┌────────────────────────────────────────────────────┐
│ BABABOT MARKET RADAR                         LIVE  │
├──────────────┬──────────────────────┬──────────────┤
│ MARKET       │ SYMBOL / CHART       │ AI VIEW      │
│ SCANNER      │                      │              │
│              │ SOLUSDT              │ LONG         │
│ SOL LONG 84  │ IGNITION             │ confirmation │
│ SUI LONG 76  │                      │ context      │
│ ENA SHORT 73 │ LONG 84 / SHORT 21   │ risk         │
├──────────────┴──────────────────────┴──────────────┤
│ Signals │ History │ Outcomes │ System Status      │
└────────────────────────────────────────────────────┘
```

Alert digunakan untuk candidate penting, bukan untuk setiap market scan.

---

# 14. Step 9 — Future Execution

Execution bukan scope awal Market Radar.

Namun arsitektur Market Radar harus memungkinkan output yang sudah matang nantinya diteruskan ke execution layer.

Flow masa depan:

```text
Market Radar
    │
    ▼
LONG / SHORT / NO TRADE
    │
    ▼
AI / Risk Confirmation
    │
    ▼
Execution Engine
    │
    ▼
Binance Order
```

Execution hanya ditambahkan setelah Market Radar terbukti stabil dalam live observation.

---

# 15. Live Outcome Tracking

Market Radar boleh menyimpan hasil live signal untuk audit.

Ini **bukan backtest**.

Contoh:

```text
08:10 SOLUSDT
IGNITION
LONG_SCORE 78
SHORT_SCORE 24
decision LONG

08:15
EXPANSION
LONG_SCORE 86

08:30
MFE +1.1%
MAE -0.2%
```

Tujuannya:

```text
audit detector
mengukur kualitas live signal
mendeteksi false signal
menilai apakah stage transition bekerja
menilai apakah LONG/SHORT scoring konsisten
```

Jika hasil live menunjukkan masalah, research dilakukan kembali di `bababot-discovery`.

---

# 16. Pemisahan Repo

## bababot-discovery

Fungsi:

```text
backtest
historical research
strategy discovery
parameter exploration
regime research
validation
experimentation
```

## bababot-market-radar

Fungsi:

```text
live market scan
Moving Coin Detector
IGNITION / EXPANSION / EXHAUSTION
LONG_SCORE / SHORT_SCORE
market context
LONG / SHORT / NO TRADE
MCP data exposure
dashboard live
alerts
live outcome tracking
future execution integration
```

Tidak boleh memindahkan backtest/discovery ke Market Radar tanpa keputusan baru.

---

# 16A. Runtime Independence — Wajib

BabaBot Market Radar adalah **produk MCD live yang berdiri sendiri**.

Market Radar **tidak boleh bergantung secara runtime** pada `bymarfinai/bababot-discovery`.

Artinya, ketika Market Radar sudah production, seluruh kebutuhan berikut harus tersedia langsung di dalam Market Radar:

```text
scan Binance USDT Perpetual
Moving Coin Detector
IGNITION / EXPANSION / EXHAUSTION
LONG_SCORE / SHORT_SCORE
volume context
breakout / breakdown
taker flow
raw Open Interest
funding
market regime logic yang diperlukan
LONG / SHORT / NO TRADE
API
MCP-facing data
dashboard data
alert data
```

Arsitektur yang **tidak boleh** digunakan:

```text
Market Radar
    ↓
call BabaBot Discovery
    ↓
ambil regime / score / signal
```

Karena desain tersebut membuat Market Radar ikut gagal apabila Discovery mati.

Arsitektur yang benar:

```text
BabaBot Discovery
= LAB
= research
= backtest
= experimentation
= validation

        ↓
validated / approved logic
        ↓
port / freeze into production

BabaBot Market Radar
= MCD PRODUCT
= LIVE PRODUCTION
= STANDALONE RUNTIME
```

Hubungan keduanya hanya pada proses development:

```text
Discovery menemukan improvement
        ↓
research + validation
        ↓
rule dinyatakan layak
        ↓
logic dipindahkan / di-port ke Market Radar
        ↓
Market Radar tetap berjalan sendiri
```

Dengan demikian:

> **Market Radar = MCD product. Discovery = supporting research environment.**

Runtime dependency Market Radar terhadap BabaBot Discovery harus:

```text
ZERO
```

Market Radar harus tetap dapat berjalan normal walaupun service BabaBot Discovery dimatikan sepenuhnya.

---

# 17. Deployment Direction

Target deployment:

```text
GitHub
│
├── bababot-discovery
│      └── Railway
│
├── bababot-market-radar
│      └── Railway
│          └── live detector / API
│
├── Radar Dashboard
│      └── frontend deployment
│
└── Existing BabaBot MCP
       └── AI access layer
```

Railway digunakan untuk engine live.

Frontend/dashboard dipisahkan dari calculation engine.

Existing BabaBot MCP digunakan sebagai interface AI bila sesuai dengan implementasi final.

---

# 18. Non-Scope

Hal berikut **bukan** bagian dari development awal BabaBot Market Radar:

```text
❌ membuat backtesting engine baru
❌ memindahkan BabaBot Discovery ke Market Radar
❌ membuat strategy discovery engine baru
❌ membuat Regime Engine baru dari nol
❌ melakukan ML training di Market Radar
❌ langsung auto-execution sebelum live validation
❌ mengubah 9-step core plan tanpa keputusan eksplisit
```

---

# 19. Frozen Definition

BabaBot Market Radar adalah:

> Sistem live yang melakukan scan seluruh Binance USDT Perpetual sekitar setiap 5 menit, mendeteksi coin yang mulai bergerak melalui Moving Coin Detector, mengklasifikasikan movement sebagai IGNITION / EXPANSION / EXHAUSTION, menghitung LONG_SCORE dan SHORT_SCORE menggunakan market context seperti volume, breakout/breakdown, taker flow, raw open interest, funding, dan existing market regime, lalu menghasilkan LONG / SHORT / NO TRADE. Data tersebut diexpose melalui MCP untuk AI inspection, ditampilkan pada dashboard live dan alert system, serta dirancang agar nantinya dapat diteruskan ke execution layer.

---

# 20. Frozen Core Checklist

Development dianggap tetap sesuai plan hanya apabila alurnya masih mengikuti checklist berikut:

- [x] Scan semua Binance USDT Perpetual tiap ±5 menit
- [x] Detect coin yang mulai bergerak
- [ ] Classify IGNITION / EXPANSION / EXHAUSTION
- [ ] Calculate LONG_SCORE / SHORT_SCORE
- [ ] Read volume
- [ ] Read breakout / breakdown
- [ ] Read taker flow
- [ ] Read raw Open Interest
- [ ] Read funding
- [ ] Read existing market regime
- [ ] Output LONG / SHORT / NO TRADE
- [ ] Expose data through MCP
- [ ] AI can inspect live radar data
- [ ] Dashboard live available
- [ ] Alert available
- [ ] Future execution integration possible
- [ ] No backtest engine inside Market Radar
- [ ] No strategy discovery engine inside Market Radar
- [ ] No new Regime Engine developed as separate scope
- [ ] Market Radar runs independently without BabaBot Discovery
- [ ] Runtime dependency on `bababot-discovery` = ZERO
- [ ] Market Radar remains an MCD live product, not a Discovery engine

---

**This document is the frozen baseline for BabaBot Market Radar development.**
