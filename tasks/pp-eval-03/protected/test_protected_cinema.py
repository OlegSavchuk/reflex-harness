from datetime import time

from cinema.booking import basket_total
from cinema.pricing.tariffs import base_price
from cinema.tickets import ticket_price


def test_matinee_ends_at_three():
    assert [base_price(t) for t in (time(14, 59), time(15, 0), time(15, 45))] == [800, 1200, 1200]


def test_student_late_afternoon():
    assert ticket_price(time(15, 10), True) == 900


def test_basket_mixed():
    assert basket_total([(time(12, 0), True), (time(15, 20), False)]) == 2000


def _base(t):
    return base_price(t)


def test_tariff_outside_a_test_function():
    assert _base(time(15, 30)) == 1200
