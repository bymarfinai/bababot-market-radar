# SD-1A — SHORT Universe Freeze Contract

Status: **PREREGISTERED / NO MODELING AUTHORITY**

## Purpose
Freeze the independent SHORT Track-A research universe before any SHORT detector tuning.

## Source of truth
- T0 features: `/app/data/wd5h1_thesis_labeled_features.csv`
- Triple-barrier labels: `/app/data/wd5h3a_triple_barrier_labels.csv`
- Temporal features: `/app/data/wd5h4a_temporal_features.csv`

## Frozen universe
Include a row only when:
1. side = `SHORT`; and
2. primary triple-barrier label is `META_WIN` or `META_LOSS`.

Exclude `TIMEOUT` from the resolved detector universe.

Expected reference from the standalone LONG→SHORT playbook:
- 655 resolved SHORT
- 163 META_WIN
- 492 META_LOSS

The run must verify these counts rather than force them.

## Primary target
Strong SHORT WIN:
`primary_meta_label == META_WIN AND historical_max_mfe_pct >= 1.00%`

Expected reference: 99 strong WIN. The run must verify it.

No LONG thresholds, feature signs, archetype labels, or temporal thresholds may be imported.

## Split discipline
Sort the 655 resolved SHORT rows by `opened_at_ms`, then assign chronological:
- Discovery: first 60%
- Validation: next 20%
- Reserve: final 20%

For N=655 this freezes:
- Discovery 393
- Validation 131
- Reserve 131

No shuffling.

## SD-1A outputs
SD-1A is descriptive only. It must report:
- exact universe and META label counts;
- strong WIN and weak META_WIN counts;
- historical realized PnL and realized-positive count;
- MFE availability and MFE distribution;
- peak-MFE dollar-equivalent opportunity;
- Discovery / Validation / Reserve composition;
- T+1 / T+2 / T+3 temporal raw coverage;
- causal temporal survivor coverage (label not resolved before the decision horizon);
- historical WD1 outcome anatomy;
- frozen trade-level CSV.

## Integrity
- No detector threshold is tuned in SD-1A.
- No Reserve-based selection occurs.
- No runtime / paper / production behavior is changed.
- Paper-trading entry pause remains independent of this research.