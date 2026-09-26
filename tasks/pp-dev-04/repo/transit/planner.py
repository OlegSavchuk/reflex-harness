"""Journey planner."""
from transit.fares import fare


def cheapest(options: list[tuple[str, str]], age: int) -> tuple[str, str]:
    """The (origin, destination) option with the lowest fare."""
    return min(options, key=lambda o: fare(o[0], o[1], age))
