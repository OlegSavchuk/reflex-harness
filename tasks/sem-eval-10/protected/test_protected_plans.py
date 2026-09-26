from datetime import date

from plans.dates import add_months
from plans.reminders import reminder_dates


def test_add_months_clamps_to_the_month_end():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 5, 31), 1) == date(2026, 6, 30)


def test_add_months_keeps_late_days():
    assert add_months(date(2026, 1, 29), 2) == date(2026, 3, 29)
    assert add_months(date(2025, 12, 31), 1) == date(2026, 1, 31)


def test_reminders_from_a_late_day():
    assert reminder_dates(date(2026, 1, 31), 1, 2) == [date(2026, 2, 25), date(2026, 3, 28)]


def _add(d, n):
    return add_months(d, n)


def test_add_outside_a_test_function():
    assert _add(date(2026, 8, 30), 1) == date(2026, 9, 30)
