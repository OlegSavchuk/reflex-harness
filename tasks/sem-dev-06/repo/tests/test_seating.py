import pytest

from venue.availability import free_seats
from venue.checkout import confirm
from venue.seating import seat_code
from venue.tickets import ticket_line


def test_seat_codes_past_row_z():
    assert [seat_code(26, 0), seat_code(27, 9)] == ["AA1", "AB10"]


def test_ticket_in_a_back_row():
    assert ticket_line("Gala", 30, 4) == "Gala | seat AE5"


def test_front_rows():
    assert [seat_code(0, 0), seat_code(25, 11)] == ["A1", "Z12"]


def test_free_seats_small_hall():
    assert free_seats(2, 2, {"A1"}) == ["A2", "B1", "B2"]


def test_confirm():
    assert confirm("X1", [(1, 2), (2, 0)]) == "Order X1: B3, C1"


def test_negative_rejected():
    with pytest.raises(ValueError):
        seat_code(-1, 0)
