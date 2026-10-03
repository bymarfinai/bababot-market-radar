# Profit Protection V4 Research Namespace

Status: **NOT ACTIVE**

This directory is reserved for the PP V4 High-Frequency Peak Capture research line.

Source of truth:
- `PP_DECISION_V4.md`
- `docs/research/profit_protection_v4/PP_V4_HIGH_FREQUENCY_PEAK_CAPTURE_CONTRACT.md`

## Current state

Only the namespace and research contract exist.

There is intentionally:
- no runtime module;
- no collector loop;
- no read API endpoint;
- no PP_V4 environment variable;
- no database table created by V4;
- no paper/live authority.

## Planned order

1. V4-1 High-Frequency Observability Benchmark
2. V4-2 Matched 15s vs high-frequency comparison
3. V4-3 Lower-Tail Compression Gate
4. V4-4 Protection + Runner Engineering, only after V4-3 passes

Do not skip directly to V4-4.
