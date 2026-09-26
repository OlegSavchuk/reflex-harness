from stockroom.models import Item
from stockroom.reorder import reorder_list
from stockroom.reports import reorder_summary


def test_only_items_below_minimum():
    items = [Item("A", 2, 5, 20), Item("B", 10, 5, 20), Item("C", 5, 5, 20)]
    assert reorder_list(items) == [("A", 18)]


def test_summary():
    assert reorder_summary([Item("X", 1, 3, 9), Item("Y", 8, 3, 9)]) == "1 to reorder, 8 units"


def test_full_stock():
    assert reorder_list([Item("Z", 20, 5, 20)]) == []
