"""Pricing tests checked against hand-computed tier examples."""

from __future__ import annotations

from decimal import Decimal

import pytest

from usage_based_billing.pricing import (
    FlatPricing,
    Tier,
    TieredPricing,
    VolumePricing,
)


def _standard_tiers() -> list[Tier]:
    # $0.10 in [0,100), $0.05 in [100,1000), $0.02 in [1000, inf)
    return [
        Tier(up_to=100, unit_price="0.10"),
        Tier(up_to=1_000, unit_price="0.05"),
        Tier(up_to=None, unit_price="0.02"),
    ]


def test_flat_pricing_multiplies() -> None:
    assert FlatPricing("0.25").cost(40) == Decimal("10.00")
    assert FlatPricing(2).cost(0) == Decimal("0")


def test_tiered_charges_each_tier_separately() -> None:
    model = TieredPricing(_standard_tiers())
    # 100*0.10 + 900*0.05 + 200*0.02 = 10 + 45 + 4 = 59
    assert model.cost(1_200) == Decimal("59.00")


def test_tiered_within_first_tier() -> None:
    model = TieredPricing(_standard_tiers())
    assert model.cost(50) == Decimal("5.00")  # 50 * 0.10


def test_tiered_exact_boundary() -> None:
    model = TieredPricing(_standard_tiers())
    # exactly 100 fills only the first tier
    assert model.cost(100) == Decimal("10.00")
    # 1000 = 100*0.10 + 900*0.05 = 10 + 45 = 55
    assert model.cost(1_000) == Decimal("55.00")


def test_tiered_zero_is_free() -> None:
    assert TieredPricing(_standard_tiers()).cost(0) == Decimal("0")


def test_volume_uses_single_matching_tier() -> None:
    model = VolumePricing(_standard_tiers())
    # 1200 lands in the third tier -> entire qty at 0.02
    assert model.cost(1_200) == Decimal("24.00")
    # 500 lands in the second tier -> entire qty at 0.05
    assert model.cost(500) == Decimal("25.00")
    # 50 lands in the first tier -> entire qty at 0.10
    assert model.cost(50) == Decimal("5.00")


def test_volume_and_tiered_differ() -> None:
    tiers = _standard_tiers()
    assert VolumePricing(tiers).cost(1_200) == Decimal("24.00")
    assert TieredPricing(tiers).cost(1_200) == Decimal("59.00")


def test_negative_quantity_rejected() -> None:
    with pytest.raises(ValueError):
        TieredPricing(_standard_tiers()).cost(-1)
    with pytest.raises(ValueError):
        VolumePricing(_standard_tiers()).cost(-1)
    with pytest.raises(ValueError):
        FlatPricing("1").cost(-1)


def test_tier_bounds_must_increase() -> None:
    with pytest.raises(ValueError):
        TieredPricing([Tier(up_to=100, unit_price="1"), Tier(up_to=100, unit_price="1")])


def test_only_final_tier_may_be_unbounded() -> None:
    with pytest.raises(ValueError):
        TieredPricing([Tier(up_to=None, unit_price="1"), Tier(up_to=100, unit_price="1")])


def test_empty_tiers_rejected() -> None:
    with pytest.raises(ValueError):
        VolumePricing([])
