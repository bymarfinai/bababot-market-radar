# Low-Tail 15s Research Archive

Status: **CLOSED / REJECTED / FROZEN**

Closed on: **2026-10-03**

This archive contains the completed Low-Tail 15-second research track (Stages A, B, and C).

## Why this track is closed

The frozen evidence established that:

- Stage A: 306 / 307 trades below 80% capture were dominated by intrapoll favorable excursions;
- Stage B: early low-tail risk was partially predictable, but universal trailing destroyed future runners;
- Stage C: across 1,536 selective-protection combinations, **0** reduced the <80% tail and **0** passed all gates;
- untouched LATE testing also degraded the distribution;
- Stage D was therefore blocked.

This branch must **not** be continued by retuning thresholds, adding another static trailing grid, or re-running the same 15s mechanism under a new stage name.

Reopening requires a materially different information or execution mechanism, such as sub-15-second/event-driven state, earlier exchange-side arming, or richer tick/order-book evidence.

## Frozen checkpoints

- Stage A merge: `9ff74d8585ae4114b682a8787d1d8f33030315dd`
- Stage B merge: `572b321834cca6501bc5deadbb035b4d4ae6850b`
- Stage C merge: `334b1e6c14d93adc9cafdfe41760b8498bd359be`

## Archived scripts

- `stage_a_low_tail_anatomy.py`
- `stage_b_low_tail_prearm_exchange.py`
- `stage_c_selective_protection.py`

## Archived frozen results

- `results/stage_a_low_tail_anatomy_1791021852690.json`
- `results/stage_b_low_tail_prearm_exchange_1791021852690.json`
- `results/stage_c_selective_protection_1791021852690.json`

## Archived tests

- `tests/test_stage_a.py`
- `tests/test_stage_b.py`
- `tests/test_stage_c.py`

## Archived reports

See:

- `docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_A.md`
- `docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_B.md`
- `docs/research/profit_protection_v3/archive/low_tail_15s/PP_V3_LOW_TAIL_STAGE_C.md`

## Authority

None of the code in this archive has paper/live production authority.

It exists only for reproducibility, audit, and to prevent repeated experimentation on a path that has already been rejected.
