from datetime import date

import pytest

from plans.forecast import renewals_in_year
from plans.invoices import invoice_schedule
from plans.reminders import reminder_dates
from plans.renewals import renewal_dates


def test_monthly_from_the_30th():
    assert renewal_dates(date(2026, 1, 30), 1, 3) == [date(2026, 2, 28), date(2026, 3, 30), date(2026, 4, 30)]


def test_quarterly_invoices_from_the_31st():
    assert invoice_schedule(date(2026, 3, 31), 3, 2, 999) == [("2026-06-30", 999), ("2026-09-30", 999)]


def test_early_day():
    assert renewal_dates(date(2026, 1, 15), 1, 2) == [date(2026, 2, 15), date(2026, 3, 15)]


def test_reminders():
    assert reminder_dates(date(2026, 5, 10), 12, 1) == [date(2027, 5, 7)]


def test_forecast():
    assert renewals_in_year(date(2026, 1, 5), 6, 2027) == 2


def test_rejects_zero_period():
    with pytest.raises(ValueError):
        renewal_dates(date(2026, 1, 1), 0, 1)
