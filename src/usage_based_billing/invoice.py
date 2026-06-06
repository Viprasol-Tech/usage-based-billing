"""Invoice assembly — turn metered usage and a price plan into line items.

A :class:`PricePlan` maps each metric to a :class:`~usage_based_billing.pricing.PricingModel`.
:func:`build_invoice` aggregates a meter over a period, prices each metered metric,
and produces an :class:`Invoice` with one :class:`LineItem` per metric plus a total.

Part of Usage-Based Billing by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

from usage_based_billing.meter import Meter
from usage_based_billing.pricing import PricingModel

_CENTS = Decimal("0.01")


def _round_money(value: Decimal) -> Decimal:
    """Round to two decimal places using banker-safe half-up rounding."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


class PricePlan(BaseModel):
    """A named plan binding each metric to a pricing model.

    Attributes:
        name: Human-readable plan name shown on the invoice.
        currency: ISO-4217 currency code (informational; no FX is performed).
        models: Mapping of metric name to its :class:`PricingModel`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    name: str = Field(min_length=1)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    models: dict[str, PricingModel]

    def price(self, metric: str, quantity: Decimal) -> Decimal:
        """Cost for ``quantity`` of ``metric`` under this plan.

        Raises:
            KeyError: If the metric has no configured pricing model.
        """
        if metric not in self.models:
            raise KeyError(f"no pricing model configured for metric {metric!r}")
        return self.models[metric].cost(quantity)


class LineItem(BaseModel):
    """One priced metric on an invoice."""

    model_config = ConfigDict(frozen=True)

    metric: str
    quantity: Decimal
    amount: Decimal


class Invoice(BaseModel):
    """A customer invoice for a single billing period."""

    model_config = ConfigDict(frozen=True)

    customer: str
    currency: str
    period_start: datetime
    period_end: datetime
    line_items: tuple[LineItem, ...]
    total: Decimal


def build_invoice(
    meter: Meter,
    plan: PricePlan,
    customer: str,
    period_start: datetime,
    period_end: datetime,
) -> Invoice:
    """Build an :class:`Invoice` for one customer over ``[start, end)``.

    Aggregates the meter for the customer, prices each metered metric with the
    plan, and sums the (rounded) line amounts into the invoice total. Metrics are
    emitted in sorted order for deterministic output.

    Args:
        meter: Source of recorded usage events.
        plan: Pricing plan binding metrics to pricing models.
        customer: Account to invoice.
        period_start: Inclusive start of the billing window.
        period_end: Exclusive end of the billing window.

    Returns:
        A fully-priced :class:`Invoice` with line items and a total.
    """
    totals = meter.aggregate(period_start, period_end, customer=customer)
    line_items: list[LineItem] = []
    running_total = Decimal(0)

    for (_, metric), quantity in sorted(totals.items(), key=lambda kv: kv[0][1]):
        if metric not in plan.models:
            # Skip metrics this plan does not price (e.g. internal/diagnostic).
            continue
        amount = _round_money(plan.price(metric, quantity))
        line_items.append(LineItem(metric=metric, quantity=quantity, amount=amount))
        running_total += amount

    return Invoice(
        customer=customer,
        currency=plan.currency,
        period_start=period_start,
        period_end=period_end,
        line_items=tuple(line_items),
        total=_round_money(running_total),
    )
