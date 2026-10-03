# Stage 2B.1 5s Shadow Archive

Status: **RETIRED / CLOSED / FROZEN**

Retired on: **2026-10-03**

Final recorded snapshot:

- start boundary: `1791030303648`
- first observation: `1791030389337`
- last observation: `1791043570111`
- rows: **54,940**
- distinct positions: **208**
- threshold-crossed rows: **30,386**
- research cadence: about **5 seconds**
- Stage 12 fast guard stayed at **15 seconds**

The historical table `pp_v3_fast_peak_observations` is preserved for audit and research.

This retired lane has no active startup hook, read API endpoint, or runtime configuration. Reuse requires a new explicit research stage and must not silently reactivate Stage 2B.1.

Archived artifacts:

- observer implementation: `profit_protection_v3_fast_observer.py`
- tests: `tests/test_fast_peak_observer.py`
- contract: `docs/research/profit_protection_v3/archive/stage2b1_5s_shadow/PP_V3_STAGE2B1_FAST_PEAK_OBSERVATION.md`
