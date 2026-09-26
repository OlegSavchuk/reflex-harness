"""Stock reports."""
from stockroom.models import Item
from stockroom.reorder import reorder_list


def reorder_summary(items: list[Item]) -> str:
    lines = reorder_list(items)
    return f"{len(lines)} to reorder, {sum(q for _, q in lines)} units"
