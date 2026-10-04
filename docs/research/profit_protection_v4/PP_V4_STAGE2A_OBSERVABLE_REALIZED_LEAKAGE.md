# PP V4-2A — Observable Peak → Realized Leakage Anatomy

Status: **COMPLETE — RESEARCH ONLY**

## Executive result

The dominant bottleneck has shifted.

Across the frozen **99-trade Stage1J clean cohort**:

- mean remaining positive observability gap: **0.138 percentage points**;
- mean net observable-peak → realized leakage: **0.717 percentage points**;
- leakage is therefore about **5.21x larger** than the remaining observability gap on the mean comparison;
- the positive-sum comparison is **5.23x**.

The same conclusion holds after removing the 25 trades that had already REDUCED before their observed 5s peak:

- N=74;
- mean leakage: **0.796 pp**;
- mean remaining observability gap: **0.160 pp**;
- ratio: **4.98x**.

Therefore Stage2A concludes that the main current bottleneck is **profit retention after observable profit is already known**, not the remaining 5s peak-detection gap.

## Population

Frozen Stage1J clean cohort:

- clean post-entry MFE >= +0.30%: **99 trades**;
- positive executable-net observable peak: **84**;
- executable-net observable peak >= +0.30%: **53**;
- executable-net observable peak >= +0.50%: **42**;
- observed peak occurred after a prior REDUCE: **25**.

No trade was selected by realized result.

## Net observable peak proxy

The archived 5s `current_pnl_pct` is gross mark-to-entry, while actual realized PnL is net of paper fees/slippage.

Stage2A therefore reconstructs a fee/slippage-aware observable peak proxy.

If a REDUCE happened before the eventual observed peak, the already-realized portion is preserved and only the remaining quantity is hypothetically closed at the observed 5s market price.

This prevents Stage2A from pretending that 100% of the original position was still available at peak.

The observable net peak is an **ex-post benchmark upper bound**, not a causal protection strategy. V4-2B must determine rules that can act without knowing in advance which observation will become the terminal peak.

## Overall leakage

All 99 trades:

- mean executable-net observed peak: **+0.697%**;
- median: **+0.347%**;
- mean actual realized: **-0.020%**;
- median actual realized: **-0.037%**;
- mean leakage: **0.717 pp**;
- median leakage: **0.543 pp**.

Across the historical $500 paper positions:

- summed observable-net peak benchmark: **+$344.81**;
- actual summed realized PnL: **-$10.02**;
- benchmark-to-realized leakage: **$354.84**.

This does not mean +$344.81 was causally achievable. It quantifies how much favorable information was visible before the actual exits.

## Protectable observable-profit cohort

### Observable net peak >= +0.30%

N=53:

- median observable net peak: **+0.764%**;
- median realized: **+0.216%**;
- median retention: **25.12%**;
- mean leakage: **0.941 pp**;
- **20/53** ended <=0% realized.

### Observable net peak >= +0.50%

N=42:

- mean observable net peak: **+1.431%**;
- median observable net peak: **+0.940%**;
- mean realized: **+0.389%**;
- median realized: **+0.378%**;
- median retention: **29.29%**;
- mean leakage: **1.042 pp**;
- median leakage: **0.752 pp**.

Retention:

- >=90%: **0 / 42**
- >=80%: **1 / 42**
- 50–80%: **6 / 42**
- 0–50%: **25 / 42**
- negative retention: **10 / 42**

Severity:

- **41 / 42** retained <80%;
- **35 / 42** retained <50%;
- **10 / 42** turned an observable >=+0.50% net opportunity into <=0% realized.

This is the strongest Stage2A evidence for moving to protection-frontier research.

## Runner leakage

### Observable net peak >= +1.00%

N=20:

- median observable peak: **+1.889%**;
- median realized: **+0.634%**;
- median retention: **36.37%**;
- mean leakage: **1.558 pp**;
- >=80% retention: **1 / 20**;
- negative retention: **2 / 20**.

### Observable net peak >= +2.00%

N=9:

- median observable peak: **+2.761%**;
- median realized: **+1.031%**;
- median retention: **37.17%**;
- mean leakage: **2.252 pp**;
- >=80% retention: **0 / 9**;
- negative retention: **1 / 9**.

Large runners are not being preserved well enough. The system often realizes only about one-third of already-observed executable-net opportunity.

## Giveback timing

After the archived 5s observer sees the eventual observed gross peak:

### Falls below 90% of peak
- **94 / 99 trades**
- median: **9.995 seconds after peak**
- actual close still occurs median **233.1 seconds later**

### Falls below 80% of peak
- **94 / 99 trades**
- median: **15.032 seconds after peak**
- actual close still occurs median **229.6 seconds later**

### Falls below 70% of peak
- **93 / 99 trades**
- median: **25.027 seconds after peak**
- close still median **183.3 seconds later**

### Falls below 50% of peak
- **91 / 99 trades**
- median: **74.984 seconds after peak**
- close still median **123.3 seconds later**

### Reaches breakeven or worse
- **45 / 99 trades**
- median: **110.0 seconds after peak**
- close still median **73.0 seconds later**

Overall observed-peak → actual-close duration:

- median: **234.5 seconds**
- P25: **100.9 seconds**
- P75: **703.9 seconds**

The key operational finding is that giveback becomes visible very quickly, but actual exits usually happen much later.

## LONG vs SHORT

LONG, N=64:

- mean leakage: **0.674 pp**
- median leakage: **0.543 pp**
- median retention among positive-net-peak trades: **-3.74%**
- negative retention share: **55.36%**

SHORT, N=35:

- mean leakage: **0.796 pp**
- median leakage: **0.418 pp**
- median retention among positive-net-peak trades: **-19.78%**
- negative retention share: **64.29%**

SHORT remains weaker, although the leakage problem is material on both sides.

## Largest real leakage cases

1. **UAIUSDT LONG**
   - clean MFE: +6.382%
   - observed gross peak: +6.382%
   - executable-net observable peak: **+6.206%**
   - actual realized: **+1.664%**
   - leakage: **4.542 pp**
   - retention: **26.82%**

2. **USUSDT SHORT**
   - clean MFE: +7.663%
   - observed gross peak: +7.451%
   - one REDUCE had already happened before peak
   - executable-net observable peak after preserving that prior reduce: **+3.826%**
   - actual realized: **-0.296%**
   - leakage: **4.122 pp**
   - retention: **-7.74%**

3. **AVAAIUSDT SHORT**
   - executable-net observable peak: **+3.944%**
   - realized: **+1.397%**
   - leakage: **2.548 pp**

4. **BRUSDT SHORT**
   - executable-net observable peak: **+3.267%**
   - realized: **+0.835%**
   - leakage: **2.432 pp**

5. **RIVERUSDT SHORT**
   - executable-net observable peak: **+1.171%**
   - realized: **-0.615%**
   - leakage: **1.786 pp**

## Stage2A decision

1. **Yes — realized leakage is materially larger than the remaining observability gap.**
2. Leakage becomes severe once observable net profit reaches roughly the >=0.50% region, and remains severe for runners.
3. Giveback usually begins within seconds:
   - 90% retention boundary around 10s median;
   - 80% boundary around 15s median.
4. SHORT is weaker, but both sides have a material problem.
5. There is sufficient evidence to proceed to:

> **V4-2B — Optimal Protection Frontier**

Stage2A does **not** choose a REDUCE/CLOSE threshold.

V4-2B must replay causal rules using only information known at each observation and must explicitly preserve runners.

## Runtime decision

- no runtime changes;
- no protection authority;
- no new exit rule;
- V4 5s observer remains research-only;
- live remains disabled/disarmed.

## Frozen artifacts

- preregistration:
  `docs/research/profit_protection_v4/PP_V4_STAGE2A_OBSERVABLE_REALIZED_LEAKAGE_CONTRACT.md`
- evidence builder:
  `research/profit_protection_v4/stage2a_build_evidence.py`
- evaluator:
  `research/profit_protection_v4/stage2a_observable_realized_leakage.py`
- frozen trade-level evidence:
  `research/profit_protection_v4/results/stage2a_observable_realized_leakage_evidence.json`
- frozen result:
  `research/profit_protection_v4/results/stage2a_observable_realized_leakage.json`
