# Archived Profit-Protection Experiments

This directory preserves historical profit-protection research that is no longer part of the production runtime.

Archived here:
- generic Stage 6 prospective shadow harness;
- PP-ADAPTIVE V1 / S5-A, S5-B, S5-C lanes;
- STATIC_NET / STATIC_BALANCED / STATIC_CAPTURE lanes;
- PP-DECISION V1 development-lane replay infrastructure;
- their historical regression tests.

These files are retained for audit/reproducibility only. Do not import them from `market_radar` production code.

The only frozen V1 logic still required by current V2 production/shadow code is isolated in:

`market_radar/profit_protection_v1.py`

Current active V2 components remain under `market_radar/`:
- `profit_protection_v2.py`
- `profit_discriminator_v2.py`
- `profit_discriminator_stage6.py`
- `profit_discriminator_stage7.py`

Historical database tables from the retired harness are intentionally not dropped by this cleanup so prior evidence remains auditable.
