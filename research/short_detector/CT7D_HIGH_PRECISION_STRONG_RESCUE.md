# SHORT-CT7D — High-Precision Strong Rescue Override

Status: **PASS research-only / clean positive rescue / modest coverage**

## Objective

CT-7D tests the architecture hypothesis:

> Low-MFE detector should remain the negative-selection kill engine, while temporal T confirmation should be used only as a positive-selection rescue override for strong winners.

The CT-7C kill set remains frozen.

CT-7D does **not** weaken CT-7C thresholds.

It only asks:

> among CT-7C flagged trades, can a later strong temporal pattern justify rescuing a small subset without re-admitting BAD/GRAY trades?

No runtime or paper-entry change is authorized.

## Critical methodology point

There are only 10 strong trades inside the CT-7C kill set: 1 Research and 9 Fresh. Therefore CT-7D does **not** fit a rescue rule directly on those 10 trades.

Instead:

1. temporal strong-vs-BAD separation is studied on the full SHORT universe;
2. thresholds are fitted only from **Research Discovery strong trades**;
3. Research Validation/Reserve and Fresh are used as transport checks;
4. only then is the frozen rule applied inside the CT-7C kill set;
5. rescued trades are replayed with delayed T3 entry and the same V4.3 SHORT-LS4 + BE0.10 execution contract.

## Temporal strong signal

The full-universe anatomy confirms the user's earlier architecture hypothesis. T1 is too weak for a high-precision strong rescue. T2 improves materially. T3 is strongest.

Examples from full strong-vs-BAD separation:

- T1 observed MFE separation: ~0.63
- T2 side-return separation: ~0.77
- T3 side-return separation: ~0.84
- T3 observed MFE separation: ~0.82

So temporal confirmation is substantially better suited to **positive strong selection** than to global low-MFE killing.

# Rejected broad rescue

The first CT-7D attempt used a clean T2 rescue rule and then a T3 clean fallback.

Classification inside CT-7C:

- 7 strong rescued
- 10 BAD re-admitted
- 7 GRAY re-admitted

Exact delayed-entry replay:

- strong rescued PnL: **+$15.94**
- BAD + GRAY re-admitted PnL: approximately **-$39.15**
- net rescue PnL: **-$23.21**

Combined system:

> -$138.40 -> **-$161.61**

Verdict: **REJECT**.

This is a critical CT-7D finding: rescuing more strong trades is not automatically better if the positive selector is still too broad.

# Precision rescue frontier

| Variant | Strong rescued | BAD reintroduced | GRAY reintroduced | Exact delayed PnL | Verdict |
|---|---:|---:|---:|---:|---|
| Broad T2->T3 | 7 | 10 | 7 | **-$23.21** | REJECT |
| P4 3-of-4 | 4 | 0 | 6 | **-$0.18** | REJECT |
| BAL3 | 3 | 0 | 2 | **+$1.77** | Positive, dominated |
| AGG4 | 4 | 1 | 2 | **+$0.60** | Positive, dominated |
| **CLEAN2** | **2** | **0** | **0** | **+$2.09** | **PRIMARY** |

CLEAN2 is the best economic and safety point. It rescues fewer strong trades, but it has zero collateral and the largest positive incremental PnL among the tested precision frontier.

# Final CT-7D rule — CLEAN2

Scope:

> only trades already flagged by CT-7C

Timing:

> **T3 rescue only**

Thresholds are Research Discovery strong Q60 values.

Rescue if **both** are true:

1. t3_delta_f_coin_minus_market_15m >= **0.2216341411**
2. d3_confirm_trades >= **417.2**

Interpretation:

> the coin materially strengthens relative to the market into T3 AND trade participation expands strongly from T2 to T3.

This is exactly the kind of positive temporal development that the T architecture is good at detecting.

## Full-universe transport

Before applying the rule to CT-7C, the same CLEAN2 rule is checked on the full strong-vs-BAD universe.

### Research Discovery

- selected: 13
- strong: **11**
- BAD: 2

### Research Validation + Reserve

- selected: 8
- strong: **7**
- BAD: 1

### Fresh

- selected: 54
- strong: **48**
- BAD: 6

The rule therefore preserves a strong-positive orientation across Research Discovery, Research holdout, and Fresh.

# CT-7C kill-set result

Inside the 125 CT-7C flagged trades, CLEAN2 selects exactly:

1. **ZAMAUSDT**
2. **SPXUSDT**

Both are TARGET-MFE >=1%, strong, executable, and Fresh Oct 1.

Collateral:

- BAD: **0**
- GRAY: **0**
- other non-strong: **0**

Classification precision inside kill-set:

> **2 / 2 strong = 100%**

# Exact delayed-entry replay

Both trades are entered only after the complete T3 confirmation bar.

Same frozen execution contract:

- exact Binance 1m open after T3 target
- exact aggTrade path
- V4.3 SHORT-LS4
- BE0.10
- same fee/slippage/notional
- same historical close boundary

## ZAMAUSDT

Delayed T3 protected PnL:

> **+$1.0201**

Reason: FULL_CLOSE_050

## SPXUSDT

Delayed T3 protected PnL:

> **+$1.0651**

Reason: FULL_CLOSE_050

Total CT-7D incremental PnL:

> **+$2.0852**

Both remain profitable despite waiting until T3.

No missing kline or aggTrade data occurs for the final rescue cohort.

# Combined system result

Before CT-7D:

> CT-5B + CT-6C + CT-7C = **-$138.4021**

After CLEAN2 rescue:

> **-$136.3170**

Incremental improvement:

> **+$2.0852**

Combined executable trades: **794**

Combined wins: **292**

Combined WR: **36.78%**

Combined executable strong: **238 / 246**

Strong retention versus CT4 baseline:

> **96.75%**

CT-7C alone had 236 / 246 executable strong retained. CT-7D therefore rescues **2 of the 10 strong trades lost by CT-7C** without reintroducing any BAD or GRAY trade.

# CT-7D verdict

> **PASS as a narrow, high-precision strong rescue override.**

The economic improvement is small, but the architecture result is important.

CT-7D demonstrates:

> **T temporal confirmation is useful as a strong-winner rescue layer, but only when used very selectively.**

Trying to rescue 7/10 strong was economically harmful.

The best tested point rescues only 2/10, but:

- 100% kill-set rescue precision;
- 0 BAD re-admitted;
- 0 GRAY re-admitted;
- exact delayed-entry PnL positive;
- full-universe strong orientation transports across Research and Fresh.

Therefore CLEAN2 is frozen as the current CT-7D research candidate.

It should remain:

> **CT-7C KILL -> T3 CLEAN2 override -> RESCUE**

not broad T rescue for every CT-7C kill.

# Remaining problem

Even after CT-7D, full system PnL remains **-$136.32**, and 8 of the original 10 CT-7C-collateral strong trades remain killed.

A future CT-7E should evaluate the remaining post-kill loss anatomy after CT-5B + CT-6C + CT-7C + CT-7D, including which MFE buckets still dominate, whether remaining loss is concentrated in BAD trades outside A1/A2/A3, whether GRAY is now material, and whether a second independent low-MFE archetype family is needed.

No runtime promotion is authorized.