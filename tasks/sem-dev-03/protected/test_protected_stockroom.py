from stockroom.models import Item
from stockroom.reorder import reorder_list
from stockroom.reports import reorder_summary
from stockroom.rules import needs_reorder


def test_below_minimum_needs_reorder():
    assert needs_reorder(Item("P", 4, 5, 10)) is True


def test_at_or_above_minimum_does_not():
    assert needs_reorder(Item("Q", 5, 5, 10)) is False
    assert needs_reorder(Item("R", 9, 5, 10)) is False


def test_reorder_other_items():
    assert reorder_list([Item("K", 0, 1, 6), Item("L", 3, 2, 8)]) == [("K", 6)]


def test_summary_other_items():
    assert reorder_summary([Item("M", 2, 4, 12), Item("N", 1, 3, 5)]) == "2 to reorder, 14 units"


def _check(item):
    return needs_reorder(item)


def test_rule_outside_a_test_function():
    assert _check(Item("S", 7, 5, 10)) is False
