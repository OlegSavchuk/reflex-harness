"""Checked-baggage rules. Free bags: economy 1, premium 2, business 2.
Weight allowance per bag: economy 20 kg, premium 25 kg, business 35 kg."""

FREE_BAGS = {"economy": 1, "premium": 2, "business": 2}
WEIGHT_KG = {"economy": 20, "premium": 25, "business": 25}


def free_bags(cabin: str) -> int:
    return FREE_BAGS[cabin]


def weight_allowance(cabin: str) -> int:
    return WEIGHT_KG[cabin]
