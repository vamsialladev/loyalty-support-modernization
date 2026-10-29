"""Mock customer API: a synthetic loyalty platform + PMS for the hotel group (spec B.3). SYNTHETIC data only.

A separate service with its own database. It speaks the customer's upstream field names (ADR-0035), requires an
idempotency key for adjustments and commits each adjustment with its idempotency record in one transaction (ADR-0039),
and can inject deterministic failures for tests and the benchmark (ADR-0038).
"""

CONTRACT_VERSION = "1.0.0"
