"""Replenishment rules."""
from stockroom.models import Item


def needs_reorder(item: Item) -> bool:
    """An item needs reordering when its stock has fallen below its minimum level."""
    return item.qty < item.max_level
