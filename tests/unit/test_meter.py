"""Metering and aggregation tests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from usage_based_billing.meter import Meter


def test_aggregate_sums_per_customer_and_metric() -> None:
    meter = Meter()
    start, end = datetime(2025, 1, 1), datetime(2025, 2, 1)
    meter.record("a", "api", 10, datetime(2025, 1, 2))
    meter.record("a", "api", 5, datetime(2025, 1, 3))
    meter.record("a", "storage", 100, datetime(2025, 1, 4))
    meter.record("b", "api", 7, datetime(2025, 1, 5))

    totals = meter.aggregate(start, end)
    assert totals[("a", "api")] == Decimal("15")
    assert totals[("a", "storage")] == Decimal("100")
    assert totals[("b", "api")] == Decimal("7")


def test_aggregate_excludes_events_outside_period() -> None:
    meter = Meter()
    meter.record("a", "api", 10, datetime(2024, 12, 31))  # before
    meter.record("a", "api", 20, datetime(2025, 1, 15))  # inside
    meter.record("a", "api", 30, datetime(2025, 2, 1))  # on exclusive end
    totals = meter.aggregate(datetime(2025, 1, 1), datetime(2025, 2, 1))
    assert totals[("a", "api")] == Decimal("20")


def test_total_for_filters_to_one_pair() -> None:
    meter = Meter()
    meter.record("a", "api", 3, datetime(2025, 1, 10))
    meter.record("a", "api", 4, datetime(2025, 1, 11))
    meter.record("b", "api", 99, datetime(2025, 1, 12))
    total = meter.total_for("a", "api", datetime(2025, 1, 1), datetime(2025, 2, 1))
    assert total == Decimal("7")


def test_total_for_missing_pair_is_zero() -> None:
    meter = Meter()
    assert meter.total_for("x", "y", datetime(2025, 1, 1), datetime(2025, 2, 1)) == Decimal("0")


def test_float_quantity_is_exact() -> None:
    meter = Meter()
    meter.record("a", "gb", 0.1, datetime(2025, 1, 1))
    meter.record("a", "gb", 0.2, datetime(2025, 1, 2))
    assert meter.total_for("a", "gb", datetime(2025, 1, 1), datetime(2025, 2, 1)) == Decimal("0.3")


def test_invalid_period_rejected() -> None:
    meter = Meter()
    with pytest.raises(ValueError):
        meter.aggregate(datetime(2025, 2, 1), datetime(2025, 1, 1))
