"""Arm A, the legacy baseline (spec B.8): credible and competent, limited only by the pre-registered defects.

- `rules.py` + `config/legacy/`: the legacy rules configuration (D03, D04, D08, D09, D15, D21).
- `checklist.py`: the deterministic rules checklist over the evidence the agent attached by hand.
- `screens.py`: member, stay and ledger screens (D01, D02, D05, D06, D07, D13, D14, D17, D18, D25).
- `keyword_index.py`: keyword policy search over the frozen 2026-03-15 index (D09, D12, D15).
- `intake.py`: keyword routing to the billing queue (D20).

The full map from defect ID to behaviour is in `docs/legacy-discovery.md`.
"""
