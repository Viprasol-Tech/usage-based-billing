"""Example price plans wiring metrics to pricing models.

Kept separate from the CLI so both the demo and tests can share one canonical
plan definition.

Part of Usage-Based Billing by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from usage_based_billing.invoice import PricePlan
from usage_based_billing.pricing import (
    FlatPricing,
    PricingModel,
    Tier,
    TieredPricing,
    VolumePricing,
)


def demo_plan() -> PricePlan:
    """A representative SaaS plan: graduated API calls, volume storage, flat seats.

    * ``api_calls`` — graduated: ``$0.0010`` up to 1k, ``$0.0005`` up to 10k,
      ``$0.0002`` beyond.
    * ``storage_gb`` — volume: ``$0.10`` under 1k GB, ``$0.06`` under 5k GB,
      ``$0.04`` beyond (whole quantity at the matching rate).
    * ``seats`` — flat ``$8.00`` per seat.
    """
    models: dict[str, PricingModel] = {
        "api_calls": TieredPricing(
            [
                Tier(up_to=1_000, unit_price="0.0010"),
                Tier(up_to=10_000, unit_price="0.0005"),
                Tier(up_to=None, unit_price="0.0002"),
            ]
        ),
        "storage_gb": VolumePricing(
            [
                Tier(up_to=1_000, unit_price="0.10"),
                Tier(up_to=5_000, unit_price="0.06"),
                Tier(up_to=None, unit_price="0.04"),
            ]
        ),
        "seats": FlatPricing("8.00"),
    }
    return PricePlan(name="Growth", currency="USD", models=models)
