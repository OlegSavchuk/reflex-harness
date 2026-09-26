"""Pick routes."""
from picking.model.location import Location


def pick_route(lines: list[tuple[str, Location]]) -> list[str]:
    """SKUs in walking order (aisle, then shelf); SKUs at the same spot keep their order."""
    return [sku for sku, _ in sorted(lines, key=lambda line: line[1].walk_key())]
