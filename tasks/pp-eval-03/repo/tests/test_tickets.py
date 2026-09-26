from datetime import time

from cinema.app import price_label
from cinema.booking import basket_total
from cinema.reports import revenue
from cinema.tickets import ticket_price


def test_student_at_a_matinee():
    assert ticket_price(time(11, 0), True) == 800


def test_late_afternoon_adult():
    got = ticket_price(time(15, 30), False)
    assert got == 1200, "prices are wrong for some screenings"


def test_evening_student():
    assert ticket_price(time(20, 0), True) == 900


def test_morning_adult():
    assert ticket_price(time(10, 30), False) == 800


def test_basket():
    assert basket_total([(time(19, 0), False), (time(19, 0), True)]) == 2100


def test_label():
    assert price_label(time(21, 15), False) == "12.00"


def test_revenue():
    assert revenue([(time(18, 0), False, 10)]) == 12000
