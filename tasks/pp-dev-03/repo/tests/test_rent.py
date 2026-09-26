from datetime import date

from lettings.rent import first_invoice
from lettings.statements import welcome_statement


def test_deposit_is_capped():
    assert first_invoice(date(2026, 3, 1), 200000) == 350000


def test_mid_month_move_in():
    got = first_invoice(date(2026, 9, 16), 90000)
    assert got == 135000, "prorated rent is wrong for some move-in dates"


def test_full_month():
    assert first_invoice(date(2026, 4, 1), 100000) == 200000


def test_late_june():
    assert first_invoice(date(2026, 6, 21), 60000) == 80000


def test_statement():
    assert welcome_statement("Kim", date(2026, 3, 17), 62000) == "Kim: first invoice 920.00"
