# PP V4-1J — Clean Post-Entry MFE Rebuild

Status: **COMPLETE — CLEAN LABEL REBUILD + RUNTIME ENTRY-BOUNDARY FIX**

## Why Stage1J exists

Stage1I found that Stage12 lifecycle MFE could inherit rolling 1m/5m candle extrema that occurred before a position was opened.

That contaminated the offline benchmark used to judge 5s peak capture.

Stage1J fixes both sides of the problem:

1. runtime Stage12 position-path accounting is entry-clipped;
2. historical MFE is rebuilt from traded prices strictly after `opened_at_ms`.

## Runtime fix

Stage12 version:

`stage12-v3.1-entry-boundary`

Market-context candles are unchanged and may still look backward before entry because they describe the market, not the position path.

Position-path fields are now separate.

For MFE/MAE and hard-stop excursion accounting:

- a closed candle is eligible only if its **open timestamp is at or after position entry**;
- a candle that straddles entry is excluded from excursion high/low;
- current price is always eligible immediately after entry;
- fast 1m and thesis 5m paths use the same boundary rule;
- market-context rolling high/low can never feed position MFE/MAE or hard-stop decisions.

This is intentionally conservative. The runtime does not invent the post-entry portion of a candle that started before entry.

## Historical clean-label reconstruction

Historical source:

- partial entry/exit minute: Binance USD-M aggregate trades;
- complete minutes fully inside the position lifetime: Binance USD-M 1m klines;
- entry price is included as the zero-excursion baseline.

Candidate population was selected **without using old MFE eligibility**.

Strict same-trade coverage:

- 5s first observation <=6s after entry;
- 5s last observation <=6s before close;
- 15s first observation <=20s after entry;
- 15s last observation <=20s before close.

Population:

- strict matched 5s + 15s trades: **189**
- clean post-entry MFE >=0.30%: **99**
- old MFE >=0.30% but clean MFE <0.30%: **25**
- old MFE <0.30% but clean MFE >=0.30%: **0**

The 25 false-eligible cases confirm the Stage1I entry-boundary diagnosis.

## Clean 15s vs 5s result

| Metric | ~15s | ~5s | Delta |
|---|---:|---:|---:|
| Mean capture | 78.03% | **84.09%** | **+6.07 pp** |
| Median capture | 88.02% | **93.29%** | **+5.27 pp** |
| Aggregate peak / clean MFE | 83.81% | **87.86%** | **+4.05 pp** |
| P10 | 42.23% | **50.31%** | **+8.08 pp** |
| P25 | 70.41% | **80.90%** | **+10.49 pp** |
| >=80% share | 66.67% | **75.76%** | **+9.09 pp** |
| >=90% share | 43.43% | **56.57%** | **+13.13 pp** |
| >=95% share | 25.25% | **45.45%** | **+20.20 pp** |
| <80% share | 33.33% | **24.24%** | **-9.09 pp** |

Per trade:
- improved: **55**
- tied: **39**
- worsened: **5**

Rescue:
- old 15s <80%: 33
- moved to >=80% under 5s: **9**
- old 15s <90%: 56
- moved to >=90% under 5s: **14**
- old 15s >=90% falling below90 under 5s: **1**

## Side split

LONG, N=64:
- median uplift: **+5.25 pp**
- aggregate uplift: **+4.13 pp**
- >=90 share: **+15.63 pp**
- <80 reduction: **12.50 pp**
- P10: **+6.96 pp**

SHORT, N=35:
- median uplift: **+6.25 pp**
- aggregate uplift: **+3.92 pp**
- >=90 share: **+8.57 pp**
- <80 reduction: **2.86 pp**
- P10: **+2.33 pp**

5s helps both sides, but SHORT retains the weaker lower tail.

## Chronological stability

EARLY, N=33:
- aggregate: **+3.14 pp**
- >=90: **+12.12 pp**
- <80 reduction: **6.06 pp**

MID, N=33:
- aggregate: **+3.63 pp**
- >=90: **+15.15 pp**
- <80 reduction: **6.06 pp**

LATE, N=33:
- aggregate: **+5.17 pp**
- >=90: **+12.12 pp**
- <80 reduction: **15.15 pp**
- P10: **+19.38 pp**
- P25: **+14.32 pp**

There is no late-cohort collapse.

## Preregistered gate diagnostic

Cohort:
- >=100 strict closed matched trades: **PASS** (189)
- >=50 clean MFE >=0.30% trades: **PASS** (99)

V4-2:
- median capture uplift >=+3 pp: **PASS** (+5.27 pp)
- aggregate capture uplift >=+3 pp: **PASS** (+4.05 pp)

V4-3:
- >=90 share uplift >=+5 pp: **PASS** (+13.13 pp)
- <80 share reduction >=5 pp: **PASS** (9.09 pp)
- P10 uplift >=+5 pp: **PASS** (+8.08 pp)
- P25 uplift >=+3 pp: **PASS** (+10.49 pp)
- LATE >=90 share non-decrease: **PASS** (+12.12 pp)
- LATE <80 share non-increase: **PASS** (-15.15 pp)

Therefore the **clean-label V4-2 and V4-3 historical diagnostics PASS**.

This does **not** grant protection/trading authority. It only proves the information layer improved materially.

## Decision

1. Keep the 5s prospective V4 observer.
2. Runtime Stage12 must use the entry-clipped MFE/MAE boundary.
3. Do not return to contaminated historical MFE labels.
4. Protection engineering remains blocked.
5. Next research stage should isolate the remaining **clean 5s low tail** (24.24% of eligible trades), especially SHORT, and test whether sub-5s/event-driven observation materially compresses it.

## Frozen artifacts

- runtime fix: `market_radar/position_lifecycle.py`
- clean-label evaluator: `research/profit_protection_v4/stage1j_clean_mfe_rebuild.py`
- frozen evidence: `research/profit_protection_v4/results/stage1j_clean_post_entry_mfe_evidence.json`
- frozen result: `research/profit_protection_v4/results/stage1j_clean_mfe_rebuild.json`

## Stage1J production activation

- merged runtime commit: `84e2f65df4e6065f0deca595253e4ff1a77e5309`
- clean runtime boundary freeze: `1791088148534`
- control at boundary: `PAUSE_ENTRIES`
- open positions at boundary: **0**
- deployed lifecycle version: `stage12-v3.1-entry-boundary`
- post-deploy boundary probe: PASS
- app container health: healthy
- V4 5s observer remained enabled at 5s with no trading authority
- control resumed to `RUN` at `1791088208713`
- live trading remained disabled/disarmed

Any prospective clean-MFE runtime cohort must use positions opened **after `1791088148534`**. Because there were zero open positions at the freeze, no pre-fix position state crosses the boundary.
