"""Builds the customer-systems adapter for a read time. The console and the worker share it, so both read the same."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.adapters.mock_customer_api import MockCustomerApiAdapter
from app.ports.customer_systems import CustomerSystems
from app.settings import AppSettings
from customer_shapes import CustomerShape

SystemsFactory = Callable[[str | None], CustomerSystems]


def mock_systems_factory(settings: AppSettings) -> SystemsFactory:
    """One shared HTTP client; each case's reads use its own read time when the simulated clock is on (ADR-0037)."""
    shape = CustomerShape.load(settings.customer_id)
    client = httpx.Client(base_url=settings.mock_api_url, timeout=2.0)

    def make(sim_time: str | None) -> CustomerSystems:
        return MockCustomerApiAdapter(
            settings.mock_api_url,
            settings.mock_api_token,
            shape,
            client=client,
            sim_time=sim_time if settings.sim_clock else None,
        )

    return make
