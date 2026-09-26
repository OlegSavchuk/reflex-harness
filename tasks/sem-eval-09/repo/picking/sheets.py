"""Printed pick sheets."""
from picking.model.location import Location
from picking.route import pick_route


def pick_sheet(order_id: str, lines: list[tuple[str, Location]]) -> str:
    return f"{order_id}: " + " > ".join(pick_route(lines))
