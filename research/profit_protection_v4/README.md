# Profit Protection V4 Research Namespace

Status: **V4-1 READY FOR ACTIVATION**

This directory is reserved for the PP V4 High-Frequency Peak Capture research line.

Source of truth:
- `PP_DECISION_V4.md`
- `docs/research/profit_protection_v4/PP_V4_HIGH_FREQUENCY_PEAK_CAPTURE_CONTRACT.md`

## Current state

V4-1 now has one research-only canonical observer implementation and an offline matched-trade evaluator.

Prospective start boundary: `1791079128949`\n\nRuntime components:
- observer: `market_radar/profit_protection_v4_observer.py`
- audit: `GET /pp-v4/stage1/summary`
- evaluator: `stage1_observability_benchmark.py`

The observer has no paper/live trading authority and does not alter Stage 12.

## Planned order

1. V4-1 High-Frequency Observability Benchmark
2. V4-2 Matched 15s vs high-frequency comparison
3. V4-3 Lower-Tail Compression Gate
4. V4-4 Protection + Runner Engineering, only after V4-3 passes

Do not skip directly to V4-4.
