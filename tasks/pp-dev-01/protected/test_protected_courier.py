from datetime import date

import pytest

from courier.calendar import is_business_day
from courier.sla import delivery_date


def test_founders_day_is_a_holiday():
    assert is_business_day(date(2026, 6, 12)) is False
    assert is_business_day(date(2027, 6, 21)) is True


def test_delivery_around_founders_day_other_year():
    assert delivery_date(date(2027, 6, 18), 1) == date(2027, 6, 21)


def test_negative_rejected():
    with pytest.raises(ValueError):
        delivery_date(date(2026, 1, 5), -3)


def _biz(d):
    return is_business_day(d)


def test_business_day_outside_a_test_function():
    assert _biz(date(2026, 6, 12)) is False
