from venue.availability import free_seats
from venue.checkout import confirm
from venue.labels import row_label


def test_row_labels():
    assert [row_label(i) for i in (0, 25, 26, 51, 52, 701, 702)] == ["A", "Z", "AA", "AZ", "BA", "ZZ", "AAA"]


def test_back_rows_in_a_large_hall():
    assert free_seats(28, 1, set())[-3:] == ["Z1", "AA1", "AB1"]


def test_confirm_back_rows():
    assert confirm("Q9", [(26, 0), (53, 1)]) == "Order Q9: AA1, BB2"


def _label(i):
    return row_label(i)


def test_label_outside_a_test_function():
    assert _label(27) == "AB"
