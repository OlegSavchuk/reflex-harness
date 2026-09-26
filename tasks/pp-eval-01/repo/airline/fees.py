"""Baggage fees."""
from airline.allowance import free_bags, weight_allowance


def baggage_fee(cabin: str, bag_weights_kg: list[float]) -> int:
    """Fee in cents: 6000 for each bag beyond the cabin's free bags, plus 7500 for each bag
    heavier than the cabin's weight allowance (a bag exactly at the allowance is fine)."""
    extra = max(len(bag_weights_kg) - free_bags(cabin), 0) * 6000
    heavy = sum(7500 for w in bag_weights_kg if w >= weight_allowance(cabin))
    return extra + heavy
