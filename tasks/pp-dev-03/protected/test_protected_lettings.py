from datetime import date

from lettings.calc.proration import prorate
from lettings.rent import first_invoice


def test_september_has_30_days():
    assert prorate(90000, date(2026, 9, 1)) == 90000
    assert prorate(30000, date(2026, 9, 30)) == 1000


def test_leap_february():
    assert prorate(29000, date(2028, 2, 1)) == 29000
    assert prorate(29000, date(2028, 2, 29)) == 1000


def test_cap_and_proration():
    assert first_invoice(date(2026, 9, 11), 180000) == 270000


def _pro(amount, start):
    return prorate(amount, start)


def test_proration_outside_a_test_function():
    assert _pro(60000, date(2027, 9, 21)) == 20000
