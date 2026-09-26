"""Reorder planning."""
from stockroom.models import Item
from stockroom.rules import needs_reorder


def reorder_list(items: list[Item]) -> list[tuple[str, int]]:
    """(sku, quantity to order up to the maximum level) for items that need reordering."""
    return sorted((i.sku, i.max_level - i.qty) for i in items if needs_reorder(i))
