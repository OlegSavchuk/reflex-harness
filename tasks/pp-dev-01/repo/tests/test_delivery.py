from datetime import date

import pytest

from courier.promises import promise_line
from courier.sla import delivery_date


def test_negative_days_rejected():
    with pytest.raises(ValueError):
        delivery_date(date(2026, 3, 2), -1)


def test_skips_company_holidays():
    got = delivery_date(date(2026, 6, 11), 1)
    assert got == date(2026, 6, 15), "deliveries must skip company holidays"


def test_weekday_delivery():
    assert delivery_date(date(2026, 3, 2), 2) == date(2026, 3, 4)


def test_skips_weekend():
    assert delivery_date(date(2026, 3, 6), 1) == date(2026, 3, 9)


def test_same_day():
    assert delivery_date(date(2026, 3, 7), 0) == date(2026, 3, 7)


def test_promise_line():
    assert promise_line("A1", date(2026, 3, 10), 1) == "A1: arrives 2026-03-11"
