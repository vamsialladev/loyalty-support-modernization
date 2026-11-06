"""Arm B, the improved conventional workflow: no generative AI (spec B.8; `docs/legacy-defect-catalog.md`).

Pure logic, like arm A's legacy layer: it reads the customer systems only through the port, and nothing here imports
web, database, HTTP or model code. Orchestration and storage live in `app/services/conventional.py`. Arm B is also the
manual fallback when the model is unavailable, so it must never depend on one.
"""
