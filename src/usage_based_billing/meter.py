"""Usage metering — record usage events and aggregate them per billing period.

A :class:`UsageEvent` is a single observation: customer ``A`` consumed ``q`` units
of ``metric`` at timestamp ``ts``. The :class:`Meter` stores events and aggregates
them by ``(customer, metric)`` over a closed-open time window, which is exactly the
quantity a price plan needs to compute a charge.

Part of Usage-Based Billing by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UsageEvent(BaseModel):
    """A single metered usage observation.

    Attributes:
        customer: Stable identifier for the billed account.
        metric: Name of the metered dimension (e.g. ``"api_calls"``).
        quantity: Non-negative amount consumed by this event.
        ts: When the usage occurred (used for period filtering).
    """

    model_config = ConfigDict(frozen=True)

    customer: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    quantity: Decimal = Field(ge=0)
    ts: datetime

    @field_validator("quantity", mode="before")
    @classmethod
    def _coerce_quantity(cls, value: object) -> Decimal:
        """Coerce ints/floats/strings to :class:`~decimal.Decimal` exactly."""
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            # Route floats through ``str`` so 0.1 does not become 0.1000000000000000055.
            return Decimal(str(value))
        if isinstance(value, (int, str)):
            return Decimal(value)
        raise TypeError(f"quantity must be a number, got {type(value).__name__}")


class Meter:
    """In-memory store of usage events with period aggregation.

    The meter is deliberately backend-agnostic: it holds events in a list so the
    demo and tests run fully offline, but the public surface (``record`` /
    ``aggregate``) is what any durable backend would expose.
    """

    def __init__(self) -> None:
        self._events: list[UsageEvent] = []

    def record(
        self,
        customer: str,
        metric: str,
        quantity: Decimal | int | float | str,
        ts: datetime,
    ) -> UsageEvent:
        """Record a usage event and return the stored, validated event."""
        event = UsageEvent(customer=customer, metric=metric, quantity=quantity, ts=ts)
        self._events.append(event)
        return event

    @property
    def events(self) -> tuple[UsageEvent, ...]:
        """All recorded events, in insertion order."""
        return tuple(self._events)

    def aggregate(
        self,
        period_start: datetime,
        period_end: datetime,
        *,
        customer: str | None = None,
        metric: str | None = None,
    ) -> dict[tuple[str, str], Decimal]:
        """Sum quantities per ``(customer, metric)`` over ``[start, end)``.

        Args:
            period_start: Inclusive lower bound of the billing window.
            period_end: Exclusive upper bound of the billing window.
            customer: If given, restrict to this customer.
            metric: If given, restrict to this metric.

        Returns:
            Mapping of ``(customer, metric)`` to the total metered quantity.
            Pairs with zero matching events are omitted.

        Raises:
            ValueError: If ``period_end`` is not strictly after ``period_start``.
        """
        if period_end <= period_start:
            raise ValueError("period_end must be after period_start")

        totals: dict[tuple[str, str], Decimal] = defaultdict(lambda: Decimal(0))
        for event in self._events:
            if not (period_start <= event.ts < period_end):
                continue
            if customer is not None and event.customer != customer:
                continue
            if metric is not None and event.metric != metric:
                continue
            totals[(event.customer, event.metric)] += event.quantity
        return dict(totals)

    def total_for(
        self,
        customer: str,
        metric: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Decimal:
        """Convenience: aggregated quantity for one ``(customer, metric)`` pair."""
        totals = self.aggregate(period_start, period_end, customer=customer, metric=metric)
        return totals.get((customer, metric), Decimal(0))
