from datetime import date

from library.fees import overdue_fee
from library.models import Loan
from library.notices import overdue_notice


def test_due_date():
    assert Loan("A", date(2026, 1, 30), loan_days=3).due_on == date(2026, 2, 2)


def test_fee_capped():
    assert overdue_fee(Loan("B", date(2026, 1, 1)), date(2026, 6, 1)) == 10.0


def test_fee_one_day_late():
    assert overdue_fee(Loan("C", date(2026, 3, 1), loan_days=21), date(2026, 3, 23)) == 0.25


def test_notice_text():
    assert overdue_notice(Loan("D", date(2026, 9, 1), loan_days=10), date(2026, 9, 15)) == "D: 1.00 due"
