"""Pricing models — flat per-unit, graduated (tiered), and volume pricing.

Three classic usage-pricing schemes, each implementing the same
:class:`PricingModel` interface (``cost(quantity) -> Decimal``):

* **Flat** — every unit costs the same ``unit_price``.
* **Tiered (graduated)** — units are split across tiers and *each slice* is
  charged at its own tier rate. The marginal price steps down (or up) as volume
  crosses tier boundaries. This is how Stripe "graduated" pricing works.
* **Volume** — the *entire* quantity is charged at the single rate of the tier
  the total lands in. This is Stripe "volume" pricing.

All money math uses :class:`~decimal.Decimal` to avoid binary float drift.

Part of Usage-Based Billing by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from itertools import pairwise

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _to_decimal(value: object) -> Decimal:
    """Coerce a number-like value to an exact :class:`~decimal.Decimal`."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise TypeError(f"expected a number, got {type(value).__name__}")


class Tier(BaseModel):
    """A single pricing tier.

    A tier covers the half-open quantity band ``[start, up_to)`` where
    ``up_to is None`` means "unbounded" (the final tier). ``unit_price`` is the
    per-unit rate that applies within the tier.
    """

    model_config = ConfigDict(frozen=True)

    up_to: Decimal | None = Field(
        default=None, description="Exclusive upper bound; None means unbounded."
    )
    unit_price: Decimal = Field(ge=0)

    @field_validator("up_to", "unit_price", mode="before")
    @classmethod
    def _coerce(cls, value: object) -> object:
        return value if value is None else _to_decimal(value)

    @field_validator("up_to")
    @classmethod
    def _positive_bound(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value <= 0:
            raise ValueError("up_to must be positive")
        return value


class PricingModel(ABC):
    """Interface every pricing scheme implements."""

    @abstractmethod
    def cost(self, quantity: Decimal | int | float | str) -> Decimal:
        """Return the total cost for ``quantity`` units."""
        raise NotImplementedError


class FlatPricing(PricingModel):
    """Charge ``unit_price`` for every unit, with no tiers."""

    def __init__(self, unit_price: Decimal | int | float | str) -> None:
        self.unit_price = _to_decimal(unit_price)
        if self.unit_price < 0:
            raise ValueError("unit_price must be non-negative")

    def cost(self, quantity: Decimal | int | float | str) -> Decimal:
        """Return ``unit_price * quantity``."""
        qty = _to_decimal(quantity)
        if qty < 0:
            raise ValueError("quantity must be non-negative")
        return self.unit_price * qty


class _TieredPlan(BaseModel):
    """Validated, ordered list of tiers shared by graduated/volume pricing."""

    model_config = ConfigDict(frozen=True)

    tiers: tuple[Tier, ...]

    @model_validator(mode="after")
    def _check_tiers(self) -> _TieredPlan:
        if not self.tiers:
            raise ValueError("at least one tier is required")
        bounds = [t.up_to for t in self.tiers]
        # Only the last tier may be unbounded.
        for bound in bounds[:-1]:
            if bound is None:
                raise ValueError("only the final tier may be unbounded (up_to=None)")
        # Finite bounds must be strictly increasing.
        finite = [b for b in bounds if b is not None]
        if any(a >= b for a, b in pairwise(finite)):
            raise ValueError("tier up_to bounds must be strictly increasing")
        return self


class TieredPricing(PricingModel):
    """Graduated pricing: each quantity slice is billed at its own tier rate.

    Example:
        Tiers ``[0, 100) @ $0.10``, ``[100, 1000) @ $0.05``, ``[1000, inf) @ $0.02``.
        A quantity of ``1200`` costs::

            100  * 0.10  = 10.00   (first tier filled)
            900  * 0.05  = 45.00   (second tier filled)
            200  * 0.02  =  4.00   (remainder in third tier)
            ----------------------
            total        = 59.00
    """

    def __init__(self, tiers: list[Tier]) -> None:
        self._plan = _TieredPlan(tiers=tuple(tiers))

    @property
    def tiers(self) -> tuple[Tier, ...]:
        return self._plan.tiers

    def cost(self, quantity: Decimal | int | float | str) -> Decimal:
        """Sum each tier slice at its own rate."""
        remaining = _to_decimal(quantity)
        if remaining < 0:
            raise ValueError("quantity must be non-negative")

        total = Decimal(0)
        lower = Decimal(0)
        for tier in self._plan.tiers:
            if remaining <= 0:
                break
            if tier.up_to is None:
                width = remaining
            else:
                width = min(remaining, tier.up_to - lower)
                lower = tier.up_to
            total += width * tier.unit_price
            remaining -= width
        return total


class VolumePricing(PricingModel):
    """Volume pricing: the whole quantity is billed at one matching tier's rate.

    The matching tier is the first whose ``up_to`` bound the *total* quantity
    falls under (or the final unbounded tier).

    Example:
        Tiers ``[0, 100) @ $0.10``, ``[100, 1000) @ $0.05``, ``[1000, inf) @ $0.02``.
        A quantity of ``1200`` lands in the third tier, so the cost is
        ``1200 * 0.02 = 24.00`` — every unit at the same rate.
    """

    def __init__(self, tiers: list[Tier]) -> None:
        self._plan = _TieredPlan(tiers=tuple(tiers))

    @property
    def tiers(self) -> tuple[Tier, ...]:
        return self._plan.tiers

    def _rate_for(self, quantity: Decimal) -> Decimal:
        for tier in self._plan.tiers:
            if tier.up_to is None or quantity < tier.up_to:
                return tier.unit_price
        # Unreachable when a final unbounded tier exists; fall back to last rate.
        return self._plan.tiers[-1].unit_price

    def cost(self, quantity: Decimal | int | float | str) -> Decimal:
        """Charge the entire quantity at the single matching tier rate."""
        qty = _to_decimal(quantity)
        if qty < 0:
            raise ValueError("quantity must be non-negative")
        return qty * self._rate_for(qty)
