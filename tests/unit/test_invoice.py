"""Invoice assembly tests with hand-computed totals."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from usage_based_billing.invoice import PricePlan, build_invoice
from usage_based_billing.meter import Meter
from usage_based_billing.pricing import (
    FlatPricing,
    PricingModel,
    Tier,
    TieredPricing,
    VolumePricing,
)

START = datetime(2025, 1, 1)
END = datetime(2025, 2, 1)


def _plan() -> PricePlan:
    models: dict[str, PricingModel] = {
        "api_calls": TieredPricing(
            [
                Tier(up_to=100, unit_price="0.10"),
                Tier(up_to=1_000, unit_price="0.05"),
                Tier(up_to=None, unit_price="0.02"),
            ]
        ),
        "storage_gb": VolumePricing(
            [
                Tier(up_to=1_000, unit_price="0.10"),
                Tier(up_to=None, unit_price="0.04"),
            ]
        ),
        "seats": FlatPricing("8.00"),
    }
    return PricePlan(name="Test", currency="USD", models=models)


def test_invoice_total_combines_all_models() -> None:
    meter = Meter()
    meter.record("acme", "api_calls", 1_200, datetime(2025, 1, 10))
    meter.record("acme", "storage_gb", 1_200, datetime(2025, 1, 11))
    meter.record("acme", "seats", 5, datetime(2025, 1, 1))

    invoice = build_invoice(meter, _plan(), "acme", START, END)

    # api_calls (graduated): 100*0.10 + 900*0.05 + 200*0.02 = 59.00
    # storage_gb (volume):   1200 lands in 2nd tier -> 1200*0.04 = 48.00
    # seats (flat):          5 * 8.00 = 40.00
    amounts = {li.metric: li.amount for li in invoice.line_items}
    assert amounts["api_calls"] == Decimal("59.00")
    assert amounts["storage_gb"] == Decimal("48.00")
    assert amounts["seats"] == Decimal("40.00")
    assert invoice.total == Decimal("147.00")


def test_line_items_sorted_and_per_customer() -> None:
    meter = Meter()
    meter.record("acme", "seats", 1, START)
    meter.record("acme", "api_calls", 50, START)
    meter.record("other", "seats", 99, START)

    invoice = build_invoice(meter, _plan(), "acme", START, END)
    metrics = [li.metric for li in invoice.line_items]
    assert metrics == sorted(metrics)
    assert "other" not in {li.metric for li in invoice.line_items}
    # acme seats=1 -> 8.00, api_calls=50 -> 5.00; other customer excluded
    assert invoice.total == Decimal("13.00")


def test_unpriced_metric_is_skipped() -> None:
    meter = Meter()
    meter.record("acme", "seats", 2, START)
    meter.record("acme", "unknown_metric", 1000, START)
    invoice = build_invoice(meter, _plan(), "acme", START, END)
    assert {li.metric for li in invoice.line_items} == {"seats"}
    assert invoice.total == Decimal("16.00")


def test_empty_usage_yields_zero_total() -> None:
    invoice = build_invoice(Meter(), _plan(), "acme", START, END)
    assert invoice.line_items == ()
    assert invoice.total == Decimal("0.00")


def test_plan_price_unknown_metric_raises() -> None:
    with pytest.raises(KeyError):
        _plan().price("nope", Decimal("1"))
