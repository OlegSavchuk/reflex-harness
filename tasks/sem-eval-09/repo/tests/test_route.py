from picking.model.location import Location
from picking.route import pick_route
from picking.sheets import pick_sheet
from picking.waves import first_picks


def test_aisle_ten_after_aisle_nine():
    assert pick_route([("A", Location("10-1")), ("B", Location("9-2"))]) == ["B", "A"]


def test_sheet_orders_shelves_numerically():
    assert pick_sheet("O1", [("X", Location("2-12")), ("Y", Location("2-3"))]) == "O1: Y > X"


def test_single_digit_aisles():
    assert pick_route([("A", Location("3-1")), ("B", Location("1-5")), ("C", Location("1-2"))]) == ["C", "B", "A"]


def test_first_picks():
    assert first_picks({"o1": [("P", Location("4-4")), ("Q", Location("2-9"))], "o2": []}) == {"o1": "Q"}


def test_same_spot_keeps_order():
    assert pick_route([("A", Location("5-5")), ("B", Location("5-5"))]) == ["A", "B"]
