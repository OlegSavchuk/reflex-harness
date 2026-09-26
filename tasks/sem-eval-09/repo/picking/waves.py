"""Pick waves."""
from picking.model.location import Location
from picking.route import pick_route


def first_picks(orders: dict[str, list[tuple[str, Location]]]) -> dict[str, str]:
    """The first SKU to pick for each order that has lines."""
    return {oid: pick_route(lines)[0] for oid, lines in orders.items() if lines}
